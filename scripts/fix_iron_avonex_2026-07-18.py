"""
One-off data fixes after the class-page import (2026-07-18), confirmed by the
domain expert:

1. id 309 "Iron": grade "-"/bonus "-" -> "A"/2, to match the iron salts imported
   from the class page (id 893 Ferrous Fumarate, id 894 Ferrous Gluconate, both
   grade A). Iron overdose is a well-known cause of acute liver injury.
2. id 360 "Alpha Interferon": drop the incorrect synonym "Avonex" — Avonex is
   interferon beta-1a (id 867), not an alpha interferon. Keep the alpha synonyms.

Then regenerate DRUG_DB_INLINE in index.html from the canonical JSON.

Usage: python scripts/fix_iron_avonex_2026-07-18.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "livertox_th_db.json"
HTML_PATH = ROOT / "index.html"
TODAY = "2026-07-18"


def main():
    db = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    by_id = {d["id"]: d for d in db}

    # Fix 1 — Iron grade
    iron = by_id[309]
    assert iron["name_en"] == "Iron", iron["name_en"]
    assert iron["livertox_grade"] == "-", iron["livertox_grade"]
    iron["livertox_grade"] = "A"
    iron["rucam_score_bonus"] = 2
    iron["last_updated"] = TODAY

    # Fix 2 — remove wrong Avonex synonym from Alpha Interferon
    alpha = by_id[360]
    assert alpha["name_en"] == "Alpha Interferon", alpha["name_en"]
    assert "Avonex" in alpha["synonyms"], alpha["synonyms"]
    alpha["synonyms"] = [s for s in alpha["synonyms"] if s != "Avonex"]
    alpha["last_updated"] = TODAY

    JSON_PATH.write_text(
        json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {JSON_PATH} ({len(db)} records)")
    print(f"  id309 Iron -> grade {iron['livertox_grade']} bonus {iron['rucam_score_bonus']}")
    print(f"  id360 Alpha Interferon -> synonyms {alpha['synonyms']}")

    html = HTML_PATH.read_text(encoding="utf-8")
    start = html.index("const DRUG_DB_INLINE =[")
    end = html.index("function loadDrugDatabase()")
    array_end = html.rindex("]", start, end) + 1
    new_array = "const DRUG_DB_INLINE =" + json.dumps(db, ensure_ascii=False, indent=0)
    HTML_PATH.write_text(html[:start] + new_array + "\n" + html[array_end:], encoding="utf-8")
    print(f"Regenerated DRUG_DB_INLINE in {HTML_PATH}")


if __name__ == "__main__":
    main()
