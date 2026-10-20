import numpy as np

from smartcity.uncertainty.conformal import conformal_quantile


def test_conformal_quantile_finite_sample():
    r = np.arange(1, 10, dtype=float)  # n=9, alpha=0.1 -> k=ceil(10*0.9)=9 -> 9th smallest
    assert conformal_quantile(r, 0.1) == 9.0
    assert conformal_quantile(r, 0.5) == 5.0


def test_conformal_infinite_when_too_few():
    assert conformal_quantile(np.array([1.0, 2.0]), 0.1) == float("inf")
