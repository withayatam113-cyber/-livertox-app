"""
Phase 7 — merge the validated class-page drug drafts into production.

These records come from LiverTox *class* overview pages (e.g. Sulfonylureas.nxml,
AnabolicSteroids.nxml) which list individual agents used in Thailand that have no
standalone .nxml file, so they were missed by the 559-record .nxml import.

Steps:
1. Load the current canonical livertox_th_db.json (813 records, ids 1-813).
2. Load archive/extract/classpage_batch{A..F}.json (97 records total).
3. Drop 3 records that already exist in the DB as synonyms of a consolidated
   record (Ferrous Sulfate -> id 309 Iron; Icosapent Ethyl / Omega-3 Carboxylic
   Acids -> id 332 Omega-3 Fatty Acids).
4. Assign contiguous ids 814+ (batch order A,B,C,D,E,F) and append.
5. Regenerate DRUG_DB_INLINE in index.html from the now-canonical JSON.

Usage: python scripts/sync_classpage_import.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "livertox_th_db.json"
HTML_PATH = ROOT / "index.html"
EXTRACT_DIR = ROOT / "archive" / "extract"
BATCHES = ["A", "B", "C", "D", "E", "F"]

# Records to skip: name_en already covered by an existing consolidated record's
# synonym list (exact match). Kept case-insensitive.
SKIP_NAMES = {
    "ferrous sulfate",          # -> id 309 Iron (synonym "Ferrous Sulfate")
    "icosapent ethyl",          # -> id 332 Omega-3 Fatty Acids (synonym)
    "omega-3 carboxylic acids", # -> id 332 Omega-3 Fatty Acids (synonym)
}


def main():
    existing = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert len(existing) == 813, f"expected 813 existing records, got {len(existing)}"
    ref_keys = set(existing[0].keys()) - {"id"}
    max_id = max(d["id"] for d in existing)

    new_records = []
    for b in BATCHES:
        path = EXTRACT_DIR / f"classpage_batch{b}.json"
        recs = json.loads(path.read_text(encoding="utf-8"))
        for r in recs:
            if r.get("name_en", "").strip().lower() in SKIP_NAMES:
                print(f"  skip (already in DB): {r.get('name_en')}")
                continue
            missing = ref_keys - set(r.keys())
            extra = set(r.keys()) - ref_keys - {"id"}
            assert not missing, f"{r.get('name_en')}: missing keys {missing}"
            assert not extra, f"{r.get('name_en')}: unexpected keys {extra}"
            new_records.append(r)

    next_id = max_id + 1
    for r in new_records:
        r["id"] = next_id
        next_id += 1
    print(f"Assigned ids {max_id + 1}-{next_id - 1} to {len(new_records)} new records")

    combined = list(existing) + new_records
    combined.sort(key=lambda d: d["id"])
    ids = [d["id"] for d in combined]
    assert ids == list(range(1, len(combined) + 1)), "id sequence is not contiguous"

    JSON_PATH.write_text(
        json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {JSON_PATH} with {len(combined)} records")

    html = HTML_PATH.read_text(encoding="utf-8")
    start_marker = "const DRUG_DB_INLINE =["
    end_marker = "function loadDrugDatabase()"
    start = html.index(start_marker)
    end = html.index(end_marker)
    array_end = html.rindex("]", start, end) + 1

    new_array = "const DRUG_DB_INLINE =" + json.dumps(combined, ensure_ascii=False, indent=0)
    new_html = html[:start] + new_array + "\n" + html[array_end:]
    HTML_PATH.write_text(new_html, encoding="utf-8")
    print(f"Regenerated DRUG_DB_INLINE in {HTML_PATH} with {len(combined)} records")


if __name__ == "__main__":
    main()
