"""
Phase 5 — consolidate the 559 authored records (herbs + biologics + conventional)
into one draft file and validate against the schema before any merge into
livertox_th_db.json / index.html.

Usage: python scripts/validate_and_merge_drafts.py
"""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "archive"
DATE_TAG = "2026-07-15"

REQUIRED_KEYS = set("""id name_en name_th type livertox_grade rucam_score_bonus description_th synonyms
hepatotoxicity_pattern scientific_name part_used source hepatotox_mechanism injury_pattern severity_max
fatal_cases_reported onset_days_min onset_days_max recovery_days_min recovery_days_max chronic_risk
rechallenge_data incidence_rate risk_factors_th interacting_drugs_th monitoring_note_th thai_herb_source
evidence_level case_count_reported livertox_url source_review_date last_updated""".split())

INJURY_ENUM = {"-", "Cholestatic", "Cholestatic/Mixed", "Hepatocellular", "Hepatocellular/Cholestatic",
    "Hepatocellular/Cholestatic/Mixed", "Hepatocellular/Mixed", "Mixed"}
SEVERITY_ENUM = {"-", "Mild", "Moderate", "Severe", "Fatal"}
GRADE_ENUM = {"-", "A", "B", "C", "D", "E", "E*"}
TYPE_ENUM = {"ยาแผนปัจจุบัน", "สมุนไพร/อาหารเสริม", "ยาชีวภาพ"}

LEAK_PATTERNS = [
    r"\bOutcome and Management\b", r"\bMechanism of Injury\b",
    r"\bHepatotoxicity\b\s+In\b", r"\bLikelihood score\b",
]


def load_category(pattern):
    files = sorted(ARCHIVE.glob(pattern))
    records = []
    for f in files:
        records.extend(json.loads(f.read_text(encoding="utf-8")))
    return records, files


def validate(records):
    issues = []
    for d in records:
        keys = set(d.keys())
        if keys != REQUIRED_KEYS:
            issues.append((d.get("id"), "KEY_MISMATCH", sorted(keys ^ REQUIRED_KEYS)))
            continue
        if d["injury_pattern"] not in INJURY_ENUM:
            issues.append((d["id"], "injury_pattern", d["injury_pattern"]))
        if d["severity_max"] not in SEVERITY_ENUM:
            issues.append((d["id"], "severity_max", d["severity_max"]))
        if d["livertox_grade"] not in GRADE_ENUM:
            issues.append((d["id"], "livertox_grade", d["livertox_grade"]))
        if d["type"] not in TYPE_ENUM:
            issues.append((d["id"], "type", d["type"]))
        if not isinstance(d["risk_factors_th"], list):
            issues.append((d["id"], "risk_factors_th_not_array", type(d["risk_factors_th"]).__name__))
        if not isinstance(d["interacting_drugs_th"], list):
            issues.append((d["id"], "interacting_drugs_th_not_array", type(d["interacting_drugs_th"]).__name__))
        if not isinstance(d["synonyms"], list):
            issues.append((d["id"], "synonyms_not_array", type(d["synonyms"]).__name__))
        for f in ["description_th", "hepatotox_mechanism", "risk_factors_th", "interacting_drugs_th", "monitoring_note_th"]:
            val = d[f]
            text = " ".join(val) if isinstance(val, list) else str(val)
            for pat in LEAK_PATTERNS:
                if re.search(pat, text):
                    issues.append((d["id"], f"ENGLISH_LEAK_{f}", pat))
    return issues


def main():
    herbs, herb_files = load_category("livertox_th_db_update_draft_pilot_herbs_*.json")
    herbs_rest, herbs_rest_files = load_category("livertox_th_db_update_draft_herbs_2026-07-15.json")
    bio, bio_files = load_category("livertox_th_db_update_draft_biologics_2026-07-15.json")
    conv, conv_files = load_category("livertox_th_db_update_draft_conventional_2026-07-15.json")

    combined = herbs + herbs_rest + bio + conv
    combined.sort(key=lambda d: d["id"])

    ids = [d["id"] for d in combined]
    gaps = sorted(set(range(255, 814)) - set(ids))
    dupes = sorted({i for i in ids if ids.count(i) > 1})

    issues = validate(combined)

    print(f"Total records: {len(combined)} (expected 559)")
    print(f"ID range: {min(ids)}-{max(ids)}")
    print(f"Gaps: {gaps if gaps else 'none'}")
    print(f"Duplicate ids: {dupes if dupes else 'none'}")
    print(f"Type distribution: {dict(Counter(d['type'] for d in combined))}")
    print(f"Grade distribution: {dict(Counter(d['livertox_grade'] for d in combined))}")
    print()
    if issues:
        print(f"VALIDATION ISSUES ({len(issues)}):")
        for i in issues:
            print(" ", i)
    else:
        print("NO VALIDATION ISSUES FOUND.")

    out = ARCHIVE / f"livertox_th_db_update_draft_{DATE_TAG}.json"
    out.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"Wrote consolidated draft: {out} ({len(combined)} records)")


if __name__ == "__main__":
    main()
