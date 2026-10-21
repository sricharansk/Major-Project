"""The multi-seed paper table is generated from the summary CSV and reads NOT RUN without it."""

from smartcity.reporting import paper

HEADER = ("model,track,n_seeds,seeds,evaluation_period_utc,n_valid_targets_60m,"
          "mae_15m_mean,mae_15m_sd,mae_15m_min,mae_15m_max,mae_30m_mean,mae_30m_sd,mae_30m_min,mae_30m_max,"
          "mae_60m_mean,mae_60m_sd,mae_60m_min,mae_60m_max,"
          "diff_vs_proposed_15m,diff_vs_proposed_15m_ci95,n_days,diff_vs_proposed_30m,diff_vs_proposed_30m_ci95,"
          "diff_vs_proposed_60m,diff_vs_proposed_60m_ci95\n")


def test_multi_seed_table_not_run_without_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(paper, "R", tmp_path)
    monkeypatch.setattr(paper, "T", tmp_path / "tables")
    paper.multi_seed_table()
    body = (tmp_path / "tables" / "multi_seed.tex").read_text()
    assert "NOT RUN" in body and "tab:multiseed" in body


def test_multi_seed_table_from_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(paper, "R", tmp_path)
    monkeypatch.setattr(paper, "T", tmp_path / "tables")
    exp = tmp_path / "reports" / "experiments"
    exp.mkdir(parents=True)
    (exp / "multi_seed_summary.csv").write_text(
        HEADER
        + "gru,operational,3,1;2;42,P,144205,4.71,0.012,4.70,4.72,5.37,0.02,5.35,5.39,6.17,0.03,6.14,6.20,"
          "-0.058,\"[-0.07, -0.04]\",44,0.042,\"[0.02, 0.06]\",0.02,\"[0.0, 0.04]\"\n"
        + "proposed,operational,3,1;2;42,P,144205,4.77,0.01,4.76,4.78,5.33,0.01,5.32,5.34,6.15,0.02,6.13,6.17,,,,,,,\n")
    paper.multi_seed_table()
    body = (tmp_path / "tables" / "multi_seed.tex").read_text()
    assert "NOT RUN" not in body and "tab:multiseed" in body
    assert body.index("proposed (3 seeds)") < body.index("gru (3 seeds)")
    assert "gru (3 seeds) & 4.710 $\\pm$ 0.012 [4.700, 4.720]" in body
    assert "\\quad minus proposed & $\\Delta$ -0.058 [-0.070, -0.040]" in body
    assert "proposed (3 seeds) & 4.770 $\\pm$ 0.010 [4.760, 4.780] & 5.330 $\\pm$ 0.010 [5.320, 5.340] & 6.150 $\\pm$ 0.020 [6.130, 6.170] \\\\" in body
