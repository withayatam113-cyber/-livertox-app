"""
Phase 8 — merge the second wave of class-page drug records (batch G) into
production. These are Thailand-used drugs that appear only on LiverTox *class*
pages (PPIs, triptans, amide local anesthetics, additional NSAIDs, SGLT-2
inhibitors, Carbimazole, Favipiravir, Valganciclovir, Flucloxacillin,
Dolasetron), confirmed by the domain expert.

Steps:
1. Load current livertox_th_db.json (907 records).
2. Load archive/extract/classpage_batchG.json (27 records).
3. Drop any record already covered in the DB by name_en or synonym
   (auto-drops Valaciclovir -> already id 792 "Valacyclovir", US spelling).
4. Enhance id 792 synonyms with the INN/British spelling + Thai name so the
   drug is findable either way.
5. Assign contiguous ids 908+ and append.
6. Regenerate DRUG_DB_INLINE in index.html from the canonical JSON.

Usage: python scripts/sync_classpage_batchG.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "livertox_th_db.json"
HTML_PATH = ROOT / "index.html"
BATCH_PATH = ROOT / "archive" / "extract" / "classpage_batchG.json"


def norm(s):
    return (s or "").strip().lower()


def main():
    db = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert len(db) == 907, f"expected 907 existing records, got {len(db)}"
    ref_keys = set(db[0].keys()) - {"id"}
    by_id = {d["id"]: d for d in db}

    # searchable token set (name_en + synonyms)
    dbtok = set()
    for r in db:
        dbtok.add(norm(r.get("name_en")))
        for s in (r.get("synonyms") or []):
            dbtok.add(norm(s))

    new_records = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    kept = []
    for r in new_records:
        names = {norm(r.get("name_en"))} | {norm(s) for s in (r.get("synonyms") or [])}
        if names & dbtok:
            print(f"  skip (already in DB): {r.get('name_en')}")
            continue
        missing = ref_keys - set(r.keys())
        extra = set(r.keys()) - ref_keys - {"id"}
        assert not missing, f"{r.get('name_en')}: missing {missing}"
        assert not extra, f"{r.get('name_en')}: extra {extra}"
        kept.append(r)

    # searchability enhancement: add INN/British spelling + Thai name to id 792
    val = by_id[792]
    assert val["name_en"] == "Valacyclovir", val["name_en"]
    for extra_syn in ["Valaciclovir", "วาลาไซโคลเวียร์"]:
        if extra_syn not in val["synonyms"]:
            val["synonyms"].append(extra_syn)
    val["last_updated"] = "2026-07-19"

    max_id = max(d["id"] for d in db)
    next_id = max_id + 1
    for r in kept:
        r["id"] = next_id
        next_id += 1
    print(f"Assigned ids {max_id + 1}-{next_id - 1} to {len(kept)} new records")

    combined = list(db) + kept
    combined.sort(key=lambda d: d["id"])
    ids = [d["id"] for d in combined]
    assert ids == list(range(1, len(combined) + 1)), "id sequence is not contiguous"

    JSON_PATH.write_text(
        json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {JSON_PATH} with {len(combined)} records")

    html = HTML_PATH.read_text(encoding="utf-8")
    start = html.index("const DRUG_DB_INLINE =[")
    end = html.index("function loadDrugDatabase()")
    array_end = html.rindex("]", start, end) + 1
    new_array = "const DRUG_DB_INLINE =" + json.dumps(combined, ensure_ascii=False, indent=0)
    HTML_PATH.write_text(html[:start] + new_array + "\n" + html[array_end:], encoding="utf-8")
    print(f"Regenerated DRUG_DB_INLINE in {HTML_PATH} with {len(combined)} records")


if __name__ == "__main__":
    main()
