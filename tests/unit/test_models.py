"""Shape / masking tests on small deterministic fixtures (software checks, not project evidence)."""

import numpy as np
import torch

from smartcity.models.deep import AvailabilityGate, ContextGatedGraphTransformer, GRUForecaster, masked_huber

SLICES = {"traffic": [0, 3], "calendar": [3, 5], "weather": [5, 7]}


def _inputs(B=2, L=6, N=4, F=7, G=3):
    torch.manual_seed(0)
    x = torch.randn(B, L, N, F)
    m = torch.ones(B, L, N, G, dtype=torch.bool)
    ei = torch.tensor([[0, 1, 2], [1, 2, 3]])
    return x, m, ei


def test_proposed_output_shape():
    x, m, ei = _inputs()
    model = ContextGatedGraphTransformer(SLICES, n_horizons=3, lookback=6, hidden_dim=16, graph_heads=2,
                                         temporal_heads=2, feedforward_dim=32)
    out = model(x, m, ei)
    assert out.shape == (2, 3, 4)


def test_temporal_only_and_gru_shapes():
    x, m, ei = _inputs()
    t = ContextGatedGraphTransformer(SLICES, 3, 6, hidden_dim=16, graph_heads=2, temporal_heads=2,
                                     feedforward_dim=32, use_graph=False)
    assert t(x, m, ei).shape == (2, 3, 4)
    g = GRUForecaster(7, 3, hidden_dim=16)
    assert g(x, m, ei).shape == (2, 3, 4)


def test_gate_masks_unavailable_groups():
    gate = AvailabilityGate(SLICES, 8)
    x = torch.randn(1, 1, 1, 7)
    m = torch.tensor([[[[True, False, True]]]])
    gate(x, m)
    w = gate.last_weights
    assert w[..., 1].item() == 0.0
    assert abs(w.sum().item() - 1.0) < 1e-5


def test_gate_all_unavailable_returns_unavailable_state():
    gate = AvailabilityGate(SLICES, 8)
    x = torch.randn(1, 1, 2, 7)
    m = torch.zeros(1, 1, 2, 3, dtype=torch.bool)
    fused, all_off = gate(x, m)
    assert all_off.all()
    assert torch.allclose(fused, gate.unavailable.expand_as(fused))


def test_masked_huber_ignores_unobserved_and_skips_empty():
    p = torch.zeros(1, 2, 2)
    y = torch.tensor([[[1.0, 100.0], [1.0, 100.0]]])
    mask = torch.tensor([[[True, False], [True, False]]])
    loss = masked_huber(p, y, mask)
    assert abs(loss.item() - 0.5) < 1e-6  # huber(1) = 0.5, the 100s are masked
    assert masked_huber(p, y, torch.zeros_like(mask)) is None


def test_graph_changes_output_only_via_edges():
    x, m, ei = _inputs()
    model = ContextGatedGraphTransformer(SLICES, 3, 6, hidden_dim=16, graph_heads=2, temporal_heads=2,
                                         feedforward_dim=32, dropout=0.0).eval()
    a = model(x, m, ei)
    b = model(x, m, torch.zeros((2, 0), dtype=torch.long))
    assert not torch.allclose(a, b)
