"""The multi-seed study must skip runs whose prediction arrays are not on this machine and resume cleanly."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("multi_seed_study", ROOT / "scripts" / "multi_seed_study.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _entry(variant, seed, run_id, artifact_dir):
    return {"variant": variant, "seed": seed, "track": "operational", "run_id": run_id, "artifact_dir": artifact_dir}


def test_pending_pairs_skips_only_runs_with_predictions(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod.settings, "ROOT", tmp_path)
    done_dir = tmp_path / "artifacts" / "models" / "ms-gru-s42-x"
    done_dir.mkdir(parents=True)
    (done_dir / "predictions_test.npz").write_bytes(b"")
    man = {"runs": [_entry("gru", 42, "ms-gru-s42-x", "artifacts/models/ms-gru-s42-x"),
                    _entry("proposed", 42, "ms-proposed-s42-y", "/other/machine/ms-proposed-s42-y")],
           "runs_without_predictions": []}
    todo = mod.pending_pairs(["proposed", "gru"], [42, 1], "operational", man)
    assert todo == [(42, "proposed"), (1, "proposed"), (1, "gru")]  # seed-major; the missing-npz run is redone


def test_run_dir_falls_back_to_run_id_folder(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod.settings, "ROOT", tmp_path)
    (tmp_path / "artifacts" / "models" / "ms-proposed-s1-z").mkdir(parents=True)
    r = _entry("proposed", 1, "ms-proposed-s1-z", "/home/elsewhere/artifacts/models/ms-proposed-s1-z")
    assert mod._run_dir(r) == tmp_path / "artifacts" / "models" / "ms-proposed-s1-z"


def test_committed_manifest_has_no_analysable_cpu_runs():
    man = json.loads((ROOT / "artifacts" / "models" / "multi_seed_runs.json").read_text())
    assert all(r.get("train_device") != "cpu" for r in man["runs"])
    assert all("note" in r for r in man["runs_without_predictions"])
