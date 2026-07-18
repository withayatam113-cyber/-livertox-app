"""
Phase 9 — merge the third wave of class-page drug records (batch H) into
production. These are the remaining Thailand-used drugs that LiverTox covers
only on class pages: Ethinylestradiol (A), Cinnarizine (D), Domperidone,
Penicillin G, Penicillin V, Thiopental (E). Confirmed by the domain expert.

After this wave the class-page mining is essentially exhausted: every remaining
candidate is either not covered by LiverTox at all (Vildagliptin, Betahistine,
Tolperisone, Drospirenone, ...) or not used in Thailand / obsolete.

Usage: python scripts/sync_classpage_batchH.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "livertox_th_db.json"
HTML_PATH = ROOT / "index.html"
BATCH_PATH = ROOT / "archive" / "extract" / "classpage_batchH.json"


def norm(s):
    return (s or "").strip().lower()


def main():
    db = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert len(db) == 933, f"expected 933 existing records, got {len(db)}"
    ref_keys = set(db[0].keys()) - {"id"}

    dbtok = set()
    for r in db:
        dbtok.add(norm(r.get("name_en")))
        for s in (r.get("synonyms") or []):
            dbtok.add(norm(s))

    kept = []
    for r in json.loads(BATCH_PATH.read_text(encoding="utf-8")):
        names = {norm(r.get("name_en"))} | {norm(s) for s in (r.get("synonyms") or [])}
        if names & dbtok:
            print(f"  skip (already in DB): {r.get('name_en')}")
            continue
        assert not (ref_keys - set(r.keys())), f"{r.get('name_en')}: missing keys"
        assert not (set(r.keys()) - ref_keys - {"id"}), f"{r.get('name_en')}: extra keys"
        kept.append(r)

    max_id = max(d["id"] for d in db)
    next_id = max_id + 1
    for r in kept:
        r["id"] = next_id
        next_id += 1
    print(f"Assigned ids {max_id + 1}-{next_id - 1} to {len(kept)} new records")

    combined = list(db) + kept
    combined.sort(key=lambda d: d["id"])
    assert [d["id"] for d in combined] == list(range(1, len(combined) + 1)), "ids not contiguous"

    JSON_PATH.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
