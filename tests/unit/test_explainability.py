"""Software checks for the explanation pipeline's selection and sensitivity mechanics (not project evidence)."""

from types import SimpleNamespace

import numpy as np
import torch

from smartcity.explainability.deep import RECENT_STEPS, eligible_alert_mask, select_alert_points
from smartcity.models.deep import ContextGatedGraphTransformer

SLICES = {"traffic": [0, 3], "calendar": [3, 5], "weather": [5, 7]}


def _fake_data(T=40, N=3, H=2):
    rng = np.random.default_rng(0)
    speed = rng.uniform(20, 50, size=(T, N))
    speed[25:, 1] = np.nan                      # link 1 goes dark from step 25 (stale feed)
    speed[30, 0] = np.nan                       # link 0 has one missing recent input around step 30
    Y = np.stack([np.roll(speed, -h, axis=0) for h in (1, 2)], axis=1)  # [T, H, N]
    Y[-2:] = np.nan
    Y[33, 0, 2] = np.nan                        # link 2: unobserved target at origin 33 / horizon 0
    return SimpleNamespace(speed=speed, Y=Y, mu=np.nanmean(speed[:20], axis=0))


def test_eligible_alert_mask_excludes_stale_inputs_and_missing_targets():
    data = _fake_data()
    test = np.arange(28, 38)
    elig = eligible_alert_mask(data, test, h_idx=0)
    assert elig.shape == (10, 3)
    assert not elig[:, 1].any()                                  # dark link never eligible
    bad0 = {t for t in test if t - RECENT_STEPS + 1 <= 30 <= t}  # windows containing the missing step
    bad0.add(29)                                                  # its 1-step target IS the missing step
    for i, t in enumerate(test):
        assert elig[i, 0] == (t not in bad0)
    assert not elig[list(test).index(33), 2]                     # missing target
    assert elig[list(test).index(29), 2]


def test_select_alert_points_prefers_largest_eligible_drop_and_fills_randomly():
    data = _fake_data()
    test = np.arange(28, 38)
    P = np.repeat(data.mu[None, None, :], len(test), axis=0).repeat(2, axis=1).astype(float)
    P[:, 0, 1] = 0.0            # huge predicted drop on the dark link: must be ignored
    P[3, 0, 2] = 1.0            # largest eligible drop: origin 31, link 2
    alerts, info = select_alert_points(data, P, test, h_idx=0, n_alerts=6, rng=np.random.default_rng(1))
    assert alerts[0] == (31, 2)
    assert all(n != 1 for _, n in alerts)
    assert len(alerts) == 6 and info["n_eligible_pairs"] == int(eligible_alert_mask(data, test, 0).sum())
    assert info["n_random"] == 6 - info["n_top_drop"]


def test_node_drop_changes_prediction_and_cache_is_not_stale():
    torch.manual_seed(0)
    B, L, N, F = 1, 6, 5, 7
    x = torch.randn(B, L, N, F)
    m = torch.ones(B, L, N, 3, dtype=torch.bool)
    # two disjoint pairs (0-1) and (3-4), node 2 isolated; dropping node 1 or node 4 removes exactly two edges
    ei = torch.tensor([[0, 1, 3, 4], [1, 0, 4, 3]])
    model = ContextGatedGraphTransformer(SLICES, n_horizons=2, lookback=L, hidden_dim=16, graph_heads=2,
                                         temporal_heads=2, feedforward_dim=32, dropout=0.0).eval()
    with torch.no_grad():
        base = model(x, m, ei)
        d1 = torch.zeros(N, dtype=torch.bool); d1[1] = True
        out1 = model(x, m, ei, node_drop=d1)
        d4 = torch.zeros(N, dtype=torch.bool); d4[4] = True
        out4 = model(x, m, ei, node_drop=d4)       # same edge count as the previous call
        again = model(x, m, ei)
    assert not torch.allclose(out1[..., 0], base[..., 0])      # node 0 lost its neighbour
    assert torch.allclose(out1[..., 3], base[..., 3])           # pair (3,4) untouched
    assert not torch.allclose(out4[..., 3], base[..., 3])      # node 3 lost its neighbour (stale cache would keep it)
    assert torch.allclose(out4[..., 0], base[..., 0])
    assert torch.allclose(again, base)
