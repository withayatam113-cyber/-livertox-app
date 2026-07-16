"""
Phase 0 — deterministic extraction for the 559-drug bulk import.

Reads the "ใช้ในไทย (สรุปเฉพาะ)" sheet of รายชื่อยาที่ยังไม่ได้นำเข้า_LiverTox.xlsx,
resolves each drug name to its .nxml source file under
Medication_Data/livertox_Medication/, extracts the sections needed for Thai
clinical authoring (Hepatotoxicity/Mechanism/Outcome/Case report/Product info),
and computes the deterministic schema fields (id, type, thai_herb_source,
rucam_score_bonus, source, livertox_url, source_review_date).

Output:
  archive/extract/livertox_extraction_2026-07-15.json
  archive/extract/extraction_manifest_2026-07-15.csv
"""
import csv
import difflib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
XLSX_PATH = ROOT / "รายชื่อยาที่ยังไม่ได้นำเข้า_LiverTox.xlsx"
NXML_DIR = ROOT / "Medication_Data" / "livertox_Medication"
OUT_DIR = ROOT / "archive" / "extract"
DATE_TAG = "2026-07-15"

XLSX_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

GROUP_TO_TYPE = {
    "สมุนไพร/เสริมอาหาร": "สมุนไพร/อาหารเสริม",
    "ยาชีวภาพ": "ยาชีวภาพ",
    "ยาแผนปัจจุบัน": "ยาแผนปัจจุบัน",
}

GRADE_TO_BONUS = {
    "A": 2, "B": 2,
    "C": 1, "D": 1,
    "E": 0, "E*": 0,
}

MANUAL_OVERRIDES = {
    "Interferon Alfa / Peginterferon Alfa": "Alpha_Peginterferon.nxml",
}


def parse_xlsx_sheet(path, sheet_num):
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read(f"xl/worksheets/sheet{sheet_num}.xml"))
    rows = []
    for row in root.find("m:sheetData", XLSX_NS):
        cells = {}
        for c in row.findall("m:c", XLSX_NS):
            col = re.match(r"([A-Z]+)", c.get("r")).group(1)
            if c.get("t") == "inlineStr":
                is_el = c.find("m:is", XLSX_NS)
                text = "".join(t.text or "" for t in is_el.findall(".//m:t", XLSX_NS))
            else:
                v = c.find("m:v", XLSX_NS)
                text = v.text if v is not None else ""
            cells[col] = text
        rows.append(cells)
    return rows[1:]  # drop header row


def normalize(name):
    return re.sub(r"[^A-Za-z0-9]", "", name).lower()


def build_file_index():
    index = {}
    for f in NXML_DIR.glob("*.nxml"):
        index.setdefault(normalize(f.stem), []).append(f.name)
    return index


def resolve_file(name_en, file_index, all_stems):
    if name_en in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[name_en], "manual_override"

    norm = normalize(name_en)
    if norm in file_index:
        candidates = file_index[norm]
        return candidates[0], "exact"

    # strip parenthetical qualifiers, e.g. "Diazepam (Oral)" -> "Diazepam"
    stripped = re.sub(r"\([^)]*\)", "", name_en)
    norm2 = normalize(stripped)
    if norm2 in file_index:
        return file_index[norm2][0], "exact_stripped_parens"

    # fuzzy match against all filenames
    match = difflib.get_close_matches(norm, all_stems, n=1, cutoff=0.72)
    if match:
        return file_index[match[0]][0], "fuzzy"

    return None, "unresolved"


NS_STRIP = re.compile(r"\{[^}]*\}")


def local_tag(el):
    return NS_STRIP.sub("", el.tag)


def find_sec(root, id_suffix):
    for sec in root.iter():
        if local_tag(sec) == "sec" and sec.get("id", "").endswith(id_suffix):
            return sec
    return None


def sec_text(sec):
    if sec is None:
        return ""
    return re.sub(r"\s+", " ", "".join(sec.itertext())).strip()


def extract_grade(hepatotoxicity_text):
    m = re.search(r"Likelihood score:\s*([A-Z]\*?)\s*\(([^)]*)\)", hepatotoxicity_text)
    if m:
        return m.group(1), m.group(2).strip()
    return "-", "-"


def extract_case_report(root, drug_id_prefix):
    case_sec = find_sec(root, ".CASE_REPORT")
    if case_sec is None:
        return "", {}
    full_text = sec_text(case_sec)
    key_points = {}
    for sec in case_sec.iter():
        if local_tag(sec) == "sec" and sec.get("id", "").endswith(".Key_Points"):
            for tr in sec.iter():
                if local_tag(tr) == "tr":
                    cells = list(tr)
                    if len(cells) >= 2:
                        label = re.sub(r"\s+", " ", "".join(cells[0].itertext())).strip().rstrip(":")
                        value = re.sub(r"\s+", " ", "".join(cells[1].itertext())).strip()
                        key_points[label] = value
            break  # only first case's key points table
    return full_text, key_points


def extract_trade_names(root):
    sec = find_sec(root, ".PRODUCT_INFORMATION")
    if sec is None:
        return []
    text = sec_text(sec)
    names = re.findall(r"([A-Za-z0-9,\- ]+?)\s*[–-]\s*([A-Za-z0-9® ]+®)", text)
    return [f"{a.strip()} - {b.strip()}" for a, b in names][:10]


def extract_drug_class(root):
    classes = []
    for el in root.iter():
        if local_tag(el) == "related-object" and el.text:
            classes.append(el.text.strip())
    seen = []
    for c in classes:
        if c and c not in seen:
            seen.append(c)
    return seen


def extract_pub_date(root):
    for el in root.iter():
        if local_tag(el) == "pub-history":
            day = month = year = None
            for d in el.iter():
                tag = local_tag(d)
                if tag == "day":
                    day = d.text
                elif tag == "month":
                    month = d.text
                elif tag == "year":
                    year = d.text
            if year and month and day:
                return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return "-"


def extract_record(nxml_path, row_id, type_th, thai_herb_source):
    tree = ET.parse(nxml_path)
    root = tree.getroot()

    title_el = None
    for el in root.iter():
        if local_tag(el) == "title-group":
            for t in el:
                if local_tag(t) == "title":
                    title_el = t
            break
    name_en_title = "".join(title_el.itertext()).strip() if title_el is not None else nxml_path.stem

    hepatotox_sec = find_sec(root, ".Hepatotoxicity")
    mechanism_sec = find_sec(root, ".Mechanism_of_Injury")
    outcome_sec = find_sec(root, ".Outcome_and_Management")

    hepatotox_text = sec_text(hepatotox_sec)
    grade, grade_explanation = extract_grade(hepatotox_text)
    case_report_text, key_points = extract_case_report(root, nxml_path.stem)

    grade_key = grade if grade in GRADE_TO_BONUS else "-"
    bonus = GRADE_TO_BONUS.get(grade_key, "-")

    record = {
        "id": row_id,
        "name_en": name_en_title,
        "type": type_th,
        "thai_herb_source": thai_herb_source,
        "livertox_grade": grade,
        "grade_explanation_en": grade_explanation,
        "rucam_score_bonus": bonus,
        "source": f"LiverTox (NIDDK, NIH): {nxml_path.name}",
        "livertox_url": f"https://www.ncbi.nlm.nih.gov/books/n/livertox/{nxml_path.stem}/",
        "source_review_date": extract_pub_date(root),
        "last_updated": DATE_TAG,
        # raw English material for the Thai-authoring step (not final schema fields)
        "raw_hepatotoxicity_text": hepatotox_text,
        "raw_mechanism_text": sec_text(mechanism_sec),
        "raw_outcome_text": sec_text(outcome_sec),
        "raw_case_report_text": case_report_text,
        "raw_case_report_key_points": key_points,
        "raw_trade_names": extract_trade_names(root),
        "raw_drug_class": extract_drug_class(root),
        "source_nxml_file": nxml_path.name,
    }
    return record


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = parse_xlsx_sheet(XLSX_PATH, 5)
    file_index = build_file_index()
    all_stems = list(file_index.keys())

    records = []
    manifest_rows = []
    unresolved = []

    for i, row in enumerate(rows, start=1):
        name_en = row.get("B", "").strip()
        group = row.get("C", "").strip()
        if not name_en:
            continue

        filename, method = resolve_file(name_en, file_index, all_stems)
        row_id = 254 + i
        type_th = GROUP_TO_TYPE.get(group, "-")
        thai_herb_source = False if type_th == "สมุนไพร/อาหารเสริม" else None

        if filename is None:
            unresolved.append((row_id, name_en, group))
            manifest_rows.append([row_id, name_en, group, "", method, "", ""])
            continue

        nxml_path = NXML_DIR / filename
        try:
            record = extract_record(nxml_path, row_id, type_th, thai_herb_source)
        except Exception as e:
            unresolved.append((row_id, name_en, group))
            manifest_rows.append([row_id, name_en, group, filename, f"parse_error:{e}", "", ""])
            continue

        records.append(record)
        manifest_rows.append([
            row_id, name_en, group, filename, method,
            record["livertox_grade"], "yes" if record["raw_case_report_text"] else "no",
        ])

    out_json = OUT_DIR / f"livertox_extraction_{DATE_TAG}.json"
    out_json.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    out_csv = OUT_DIR / f"extraction_manifest_{DATE_TAG}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "name_en", "group", "resolved_file", "match_method", "grade", "has_case_report"])
        w.writerows(manifest_rows)

    print(f"rows read: {len(rows)}")
    print(f"records extracted: {len(records)}")
    print(f"unresolved: {len(unresolved)}")
    for row_id, name_en, group in unresolved:
        print(f"  UNRESOLVED id={row_id} name={name_en!r} group={group!r}")
    print(f"wrote {out_json}")
    print(f"wrote {out_csv}")


if __name__ == "__main__":
    main()
