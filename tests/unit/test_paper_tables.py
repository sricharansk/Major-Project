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


CAL_RECORD = {
    "rule": {"dot_link_id": "4456494", "target_speed_mph": 10.95, "tolerance_mph": 1.5, "seeds": [101, 102], "max_cycle_s": 120},
    "selected_green_factor": None,
    "reason": "closest admissible factor 2.0 gives 8.0 mph, -2.95 mph from the target, beyond the 1.5 mph tolerance",
    "per_factor": [
        {"green_factor": 1.0, "speed_mean_mph": 5.8, "unfinished_trips": [568, 531], "admissible": False,
         "program": {"per_tls": {"a": {"cycle_after_s": 102.0}, "b": {"cycle_after_s": 21.0}}}},
        {"green_factor": 2.0, "speed_mean_mph": 8.0, "unfinished_trips": [0, 0], "admissible": True,
         "program": {"per_tls": {"a": {"cycle_after_s": 119.0}, "b": {"cycle_after_s": 37.0}}}},
    ],
}


def test_split_calibration_table_not_run_without_record(tmp_path, monkeypatch):
    monkeypatch.setattr(paper, "R", tmp_path)
    monkeypatch.setattr(paper, "T", tmp_path / "tables")
    paper.split_calibration_table()
    body = (tmp_path / "tables" / "split_calibration.tex").read_text()
    assert "NOT RUN" in body and "tab:splitcal" in body


def test_split_calibration_table_from_record(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(paper, "R", tmp_path)
    monkeypatch.setattr(paper, "T", tmp_path / "tables")
    sc = tmp_path / "simulation" / "scenarios"
    sc.mkdir(parents=True)
    (sc / "split_calibration_v5_counts2025_calibrated_splits.json").write_text(json.dumps(CAL_RECORD))
    paper.split_calibration_table()
    body = (tmp_path / "tables" / "split_calibration.tex").read_text()
    assert "NOT RUN" not in body and "tab:splitcal" in body
    assert "1.0 & 5.80 & -5.15 & 568/531 & 102 & no \\\\" in body
    assert "2.0 & 8.00 & -2.95 & 0/0 & 119 & yes \\\\" in body
    assert "no factor selected" in body and "10.95" in body


CAL6_RECORD = {
    "rule": {"dot_link_id": "4456494", "target_speed_mph": 10.95, "tolerance_mph": 1.5, "seeds": [101, 102]},
    "progression_direction": "southbound",
    "selected_cell": {"green_factor": 2.5, "common_cycle_s": 120.0, "progression_speed_mph": 25.0},
    "reason": "closest admissible cell within tolerance (factor 2.5, 120 s common cycle, 25.0 mph offsets)",
    "per_factor": [
        {"common_cycle_s": None, "green_factor": 1.0, "progression_speed_mph": 0.0, "speed_mean_mph": 5.8,
         "unfinished_trips": [568, 531], "admissible": False},
        {"common_cycle_s": 120.0, "green_factor": 2.5, "progression_speed_mph": 25.0, "speed_mean_mph": 10.2,
         "unfinished_trips": [0, 0], "admissible": True},
    ],
}


def test_split_calibration_v6_table_not_run_without_record(tmp_path, monkeypatch):
    monkeypatch.setattr(paper, "R", tmp_path)
    monkeypatch.setattr(paper, "T", tmp_path / "tables")
    paper.split_calibration_v6_table()
    body = (tmp_path / "tables" / "split_calibration_v6.tex").read_text()
    assert "NOT RUN" in body and "tab:splitcal6" in body


def test_split_calibration_v6_table_from_record(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(paper, "R", tmp_path)
    monkeypatch.setattr(paper, "T", tmp_path / "tables")
    sc = tmp_path / "simulation" / "scenarios"
    sc.mkdir(parents=True)
    (sc / "split_calibration_v6_counts2025_cycle_splits_offsets.json").write_text(json.dumps(CAL6_RECORD))
    paper.split_calibration_v6_table()
    body = (tmp_path / "tables" / "split_calibration_v6.tex").read_text()
    assert "NOT RUN" not in body and "tab:splitcal6" in body
    assert "Webster & 1.0 & none & 5.80 & -5.15 & 568/531 & no \\\\" in body
    assert "120 & 2.5 & 25\\,mph & 10.20 & -0.75 & 0/0 & yes \\\\" in body
    assert "selected cell: factor 2.5, 120\\,s common cycle, 25\\,mph offsets" in body and "southbound" in body


def test_live_table_not_run_without_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(paper, "R", tmp_path)
    monkeypatch.setattr(paper, "T", tmp_path / "tables")
    paper.live_table()
    body = (tmp_path / "tables" / "live.tex").read_text()
    assert "NOT RUN" in body and "tab:live" in body


def test_live_table_from_summary(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(paper, "R", tmp_path)
    monkeypatch.setattr(paper, "T", tmp_path / "tables")
    (tmp_path / "artifacts" / "live").mkdir(parents=True)
    (tmp_path / "reports" / "experiments").mkdir(parents=True)
    (tmp_path / "artifacts" / "live" / "live_summary.json").write_text(json.dumps(
        {"status": "OK", "n_scored": 30, "n_batches": 12, "n_links": 16, "n_pending": 10, "n_late": 0,
         "first_origin_utc": "2026-10-29T13:00:00+00:00", "last_origin_utc": "2026-10-29T13:55:00+00:00"}))
    (tmp_path / "reports" / "experiments" / "live_metrics.csv").write_text(
        "mode,horizon_minutes,n_forecast,n_scored,n_pending,n_target_unobserved,n_late,mae_mph,rmse_mph,coverage,"
        "mean_interval_width_mph,persistence_mae_mph,n_scored_eligible,mae_eligible_mph\n"
        "LIVE,15,16,12,4,0,0,4.1,5.0,0.917,24.3,4.8,10,4.0\n"
        "LIVE,30,16,10,6,0,0,5.2,6.1,0.9,26.9,5.9,9,5.1\n"
        "LIVE,60,16,8,8,0,0,6.3,7.2,0.875,29.5,7.4,7,6.2\n")
    paper.live_table()
    body = (tmp_path / "tables" / "live.tex").read_text()
    assert "NOT RUN" not in body and "tab:live" in body and "12 five-minute batches" in body
    assert "15 & 12 & 4.10 & 4.80 & 0.917 & 24.3 \\\\" in body
