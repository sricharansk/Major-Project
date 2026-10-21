"""The multi-seed paper table is generated from the summary CSV and reads NOT RUN without it."""

from smartcity.reporting import paper


def test_multi_seed_table_not_run_without_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(paper, "R", tmp_path)
    monkeypatch.setattr(paper, "T", tmp_path / "tables")
    paper.multi_seed_table()
    body = (tmp_path / "tables" / "multi_seed.tex").read_text()
    assert "NOT RUN" in body and "tab:seeds" in body


def test_multi_seed_table_from_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(paper, "R", tmp_path)
    monkeypatch.setattr(paper, "T", tmp_path / "tables")
    exp = tmp_path / "reports" / "experiments"
    exp.mkdir(parents=True)
    (exp / "multi_seed_summary.csv").write_text(
        "model,n_seeds,seeds,mae_15m_mean,mae_15m_sd,mae_30m_mean,mae_30m_sd,mae_60m_mean,mae_60m_sd,"
        "diff_vs_proposed_15m,diff_vs_proposed_15m_ci95,diff_vs_proposed_30m,diff_vs_proposed_30m_ci95,"
        "diff_vs_proposed_60m,diff_vs_proposed_60m_ci95,n_days\n"
        "gru,3,1;2;42,4.71,0.012,5.37,0.02,6.17,0.03,-0.058,\"[-0.07, -0.04]\",0.042,\"[0.02, 0.06]\",0.02,\"[0.0, 0.04]\",44\n"
        "proposed,3,1;2;42,4.77,0.01,5.33,0.01,6.15,0.02,,,,,,,\n")
    paper.multi_seed_table()
    body = (tmp_path / "tables" / "multi_seed.tex").read_text()
    assert "NOT RUN" not in body
    assert "gru & 1;2;42 & 4.71 $\\pm$ 0.012" in body
    assert "-0.058 [-0.07, -0.04]" in body
    assert "proposed & 1;2;42 & 4.77 $\\pm$ 0.010 & 5.33 $\\pm$ 0.010 & 6.15 $\\pm$ 0.020 & ref. & ref. & ref." in body
