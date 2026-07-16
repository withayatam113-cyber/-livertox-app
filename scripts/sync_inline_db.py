"""
Phase 6 — merge the validated 559-record draft into production.

1. Fix the 5 known chronic_risk/source drifts between livertox_th_db.json and
   DRUG_DB_INLINE (resolved against the original .nxml source text).
2. Append the 559 validated records (ids 255-813) to livertox_th_db.json.
3. Regenerate DRUG_DB_INLINE in index.html from the now-canonical JSON, so the
   inline block becomes a pure function of the JSON going forward instead of a
   second, independently-maintained copy.

Usage: python scripts/sync_inline_db.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "livertox_th_db.json"
HTML_PATH = ROOT / "index.html"
DRAFT_PATH = ROOT / "archive" / "livertox_th_db_update_draft_2026-07-15.json"

# chronic_risk corrections confirmed against the original .nxml source text
# (all 4 sources explicitly say no chronic injury/hepatitis has been reported
# for that specific drug)
CHRONIC_RISK_FIXES = {85: False, 108: False, 218: False, 238: False}
SOURCE_FIX = {1: "LiverTox (NIDDK, NIH): Acetaminophen.nxml"}


def main():
    existing = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert len(existing) == 254, f"expected 254 existing records, got {len(existing)}"

    by_id = {d["id"]: d for d in existing}
    for rid, val in CHRONIC_RISK_FIXES.items():
        by_id[rid]["chronic_risk"] = val
        by_id[rid]["last_updated"] = "2026-07-16"
    for rid, val in SOURCE_FIX.items():
        by_id[rid]["source"] = val
        by_id[rid]["last_updated"] = "2026-07-16"

    new_records = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))
    assert len(new_records) == 559, f"expected 559 new records, got {len(new_records)}"

    combined = list(existing) + new_records
    combined.sort(key=lambda d: d["id"])
    ids = [d["id"] for d in combined]
    assert ids == list(range(1, 814)), "id sequence is not contiguous 1-813"

    JSON_PATH.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {JSON_PATH} with {len(combined)} records")

    html = HTML_PATH.read_text(encoding="utf-8")
    start_marker = "const DRUG_DB_INLINE =["
    end_marker = "function loadDrugDatabase()"
    start = html.index(start_marker)
    end = html.index(end_marker)

    # find the end of the array literal (the closing "]" right before end_marker,
    # no trailing semicolon in the original source)
    array_end = html.rindex("]", start, end) + 1

    new_array = "const DRUG_DB_INLINE =" + json.dumps(combined, ensure_ascii=False, indent=0)
    new_html = html[:start] + new_array + "\n" + html[array_end:]
    HTML_PATH.write_text(new_html, encoding="utf-8")
    print(f"Regenerated DRUG_DB_INLINE in {HTML_PATH} with {len(combined)} records")


if __name__ == "__main__":
    main()
