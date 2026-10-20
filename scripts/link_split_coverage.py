"""Regenerate reports/data_audit/link_split_coverage.csv from the per-track coverage audit and the link list.

The first version of this table was written ad hoc during the run before the eligibility rule changed; this script
derives it from `link_coverage_operational.csv` (written by `features build`) and `manhattan_links.csv` (written by
`graph build`), so the `in_features` column always reflects the rule that produced the trained models.

    python scripts/link_split_coverage.py
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUD = ROOT / "reports" / "data_audit"


def main() -> None:
    with open(AUD / "link_coverage_operational.csv", encoding="utf-8") as fh:
        cov = {r["link_id"]: r for r in csv.DictReader(fh)}
    with open(AUD / "manhattan_links.csv", encoding="utf-8") as fh:
        links = list(csv.DictReader(fh))
    rows = []
    for lk in links:
        c = cov.get(lk["link_id"])
        rows.append({"link_id": lk["link_id"], "link_name": lk["link_name"], "in_grid": c is not None,
                     "in_features": (c or {}).get("kept") == "True",
                     "train": c["coverage_train"] if c else "", "val": c["coverage_val"] if c else "",
                     "calib": c["coverage_calib"] if c else "", "test": c["coverage_test"] if c else "",
                     "all": c["coverage_all"] if c else "", "rule": (c or {}).get("rule", "no valid observation in 2026")})
    out = AUD / "link_split_coverage.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{out.relative_to(ROOT)}: {len(rows)} links, in_grid={sum(r['in_grid'] for r in rows)}, "
          f"in_features={sum(r['in_features'] for r in rows)}")


if __name__ == "__main__":
    main()
