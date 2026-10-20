"""Deep forecasting models.

* ``ContextGatedGraphTransformer`` — the proposed context-gated GATv2 + Temporal Transformer.
  Flags give the ablations: ``use_graph=False`` is the temporal-only Transformer baseline,
  ``use_gate=False`` replaces the availability-aware gate by plain concatenation + projection.
* ``GRUForecaster`` — per-link recurrent baseline (shared weights, no graph).

Tensor contract
    x          [B, L, N, F]
    group_mask [B, L, N, G]  (bool)
    edge_index [2, E]
    output     [B, H, N]     standardised per-link speed (inverse-transformed by the caller)
"""

from __future__ import annotations

import torch
import torch.nn as nn
from torch_geometric.nn import GATv2Conv


def masked_huber(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor, delta: float = 1.0):
    """Mean Huber loss over observed targets only.  Returns None when the batch has no observed target."""
    m = mask.float()
    denom = m.sum()
    if denom.item() == 0:
        return None
    t = torch.where(mask, target, torch.zeros_like(target))
    loss = nn.functional.huber_loss(pred, t, reduction="none", delta=delta)
    return (loss * m).sum() / denom


class AvailabilityGate(nn.Module):
    """Project each feature group to D, masked-softmax over available groups, weighted sum.

    When every group is unavailable for a (node, time) the output is a learned 'unavailable' vector and
    ``all_unavailable`` is reported so callers can log it.
    """

    def __init__(self, group_slices: dict[str, list[int]], hidden: int, use_gate: bool = True):
        super().__init__()
        self.names = list(group_slices)
        self.slices = [tuple(group_slices[g]) for g in self.names]
        self.use_gate = use_gate
        self.proj = nn.ModuleList([nn.Linear(b - a, hidden) for a, b in self.slices])
        self.score = nn.Sequential(nn.Linear(hidden, hidden), nn.Tanh(), nn.Linear(hidden, 1, bias=False))
        self.unavailable = nn.Parameter(torch.zeros(hidden))
        self.concat_proj = nn.Linear(hidden * len(self.slices), hidden)
        self.last_weights: torch.Tensor | None = None

    def forward(self, x: torch.Tensor, gmask: torch.Tensor):
        hs = torch.stack([p(x[..., a:b]) for p, (a, b) in zip(self.proj, self.slices)], dim=-2)  # [...,G,D]
        hs = torch.relu(hs)
        if not self.use_gate:
            hs = hs * gmask.unsqueeze(-1).float()
            return self.concat_proj(hs.flatten(-2)), None
        scores = self.score(hs).squeeze(-1)  # [..., G]
        scores = scores.masked_fill(~gmask, float("-inf"))
        all_off = ~gmask.any(-1, keepdim=True)
        w = torch.softmax(torch.where(all_off, torch.zeros_like(scores), scores), dim=-1)
        w = torch.where(all_off, torch.zeros_like(w), w)
        self.last_weights = w.detach()
        fused = (w.unsqueeze(-1) * hs).sum(-2)
        fused = torch.where(all_off, self.unavailable.expand_as(fused), fused)
        return fused, all_off.squeeze(-1)


class ContextGatedGraphTransformer(nn.Module):
    def __init__(self, group_slices: dict, n_horizons: int, lookback: int, hidden_dim: int = 64,
                 graph_layers: int = 2, graph_heads: int = 4, temporal_layers: int = 2, temporal_heads: int = 4,
                 feedforward_dim: int = 128, dropout: float = 0.1, use_graph: bool = True, use_gate: bool = True,
                 **_):
        super().__init__()
        self.use_graph = use_graph
        self.fusion = AvailabilityGate(group_slices, hidden_dim, use_gate)
        self.gnn = nn.ModuleList([GATv2Conv(hidden_dim, hidden_dim, heads=graph_heads, concat=False,
                                            dropout=dropout, add_self_loops=True) for _ in range(graph_layers)])
        self.gnn_norm = nn.ModuleList([nn.LayerNorm(hidden_dim) for _ in range(graph_layers)])
        self.pos = nn.Parameter(torch.zeros(1, lookback, hidden_dim))
        nn.init.normal_(self.pos, std=0.02)
        layer = nn.TransformerEncoderLayer(hidden_dim, temporal_heads, feedforward_dim, dropout, batch_first=True)
        self.temporal = nn.TransformerEncoder(layer, temporal_layers, enable_nested_tensor=False)
        self.head = nn.Linear(hidden_dim, n_horizons)
        self.drop = nn.Dropout(dropout)
        self._ei_cache: dict = {}

    def _batched_edges(self, edge_index: torch.Tensor, copies: int, n: int) -> torch.Tensor:
        # The cache is validated against the edge tensor's *content*, not only its data pointer: a temporary
        # tensor (e.g. the reduced edge set of a node-drop sensitivity run) can be freed and the next one
        # allocated at the same address with the same length, which previously returned a stale batch.
        key = (copies, n, edge_index.shape[1])
        hit = self._ei_cache.get(key)
        if hit is not None and hit[0].device == edge_index.device and torch.equal(hit[0], edge_index):
            return hit[1]
        offs = (torch.arange(copies, device=edge_index.device) * n).view(1, -1, 1)
        big = (edge_index.unsqueeze(1) + offs).reshape(2, -1)
        self._ei_cache = {key: (edge_index.clone(), big)}
        return big

    def forward(self, x, group_mask, edge_index, node_drop: torch.Tensor | None = None):
        B, L, N, _ = x.shape
        h, _ = self.fusion(x, group_mask)  # [B, L, N, D]
        if self.use_graph and edge_index.numel() > 0:
            ei = edge_index
            if node_drop is not None:  # sensitivity analysis: remove edges touching dropped nodes
                keep = ~(node_drop[ei[0]] | node_drop[ei[1]])
                ei = ei[:, keep]
            D = h.shape[-1]
            flat = h.reshape(B * L * N, D)
            big = self._batched_edges(ei, B * L, N)
            for conv, norm in zip(self.gnn, self.gnn_norm):
                flat = norm(flat + self.drop(torch.relu(conv(flat, big))))
            h = flat.view(B, L, N, D)
        seq = h.permute(0, 2, 1, 3).reshape(B * N, L, -1) + self.pos[:, :L]
        enc = self.temporal(seq)
        out = self.head(enc[:, -1])  # [B*N, H]
        return out.view(B, N, -1).permute(0, 2, 1)


class GRUForecaster(nn.Module):
    def __init__(self, n_features: int, n_horizons: int, hidden_dim: int = 64, layers: int = 2,
                 dropout: float = 0.1, **_):
        super().__init__()
        self.gru = nn.GRU(n_features, hidden_dim, layers, batch_first=True, dropout=dropout)
        self.head = nn.Linear(hidden_dim, n_horizons)

    def forward(self, x, group_mask=None, edge_index=None, node_drop=None):
        B, L, N, F = x.shape
        seq = x.permute(0, 2, 1, 3).reshape(B * N, L, F)
        out, _ = self.gru(seq)
        return self.head(out[:, -1]).view(B, N, -1).permute(0, 2, 1)
