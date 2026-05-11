import csv
import requests
from collections import defaultdict
from io import StringIO

SPREADSHEET_ID = "14DqavAx6ov60d92rhvwy2sNEW_909MCHp421GM4q-Yk"

SHEETS = [
    {"name": "Pending", "gid": "1332493366"},
    {"name": "VERIFIED", "gid": "2014365553"},
    {"name": "TEST", "gid": "1746205606"},
]

BASE_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid="


def clean(v):
    return (v or "").strip()


def fetch_sheet(gid):
    url = BASE_URL + gid
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def find_header_row(lines):
    rows = list(csv.reader(lines))
    for i, row in enumerate(rows):
        norm = [clean(c) for c in row]
        if "Base Code" in norm and ("Shard" in norm or "Server" in norm):
            return i, rows
    raise ValueError("Header row not found")


def parse_sheet(sheet_name, gid):
    text = fetch_sheet(gid)
    lines = text.splitlines()
    header_idx, rows = find_header_row(lines)

    sio = StringIO()
    writer = csv.writer(sio)
    for row in rows[header_idx:]:
        writer.writerow(row)
    sio.seek(0)

    reader = csv.DictReader(sio)

    result = []
    for row in reader:
        code = clean(row.get("Base Code"))
        if not code:
            continue

        server = clean(row.get("Shard") or row.get("Server") or "Unknown")
        name = clean(row.get("Base Name (SG / VG)") or row.get("Base Name") or "")
        result.append({
            "sheet": sheet_name,
            "code": code.upper(),
            "server": server,
            "name": name,
        })
    return result


def main():
    all_rows = []
    for s in SHEETS:
        rows = parse_sheet(s["name"], s["gid"])
        all_rows.extend(rows)
        print(f"{s['name']}: {len(rows)} rows parsed")

    by_code = defaultdict(list)
    for row in all_rows:
        by_code[row["code"]].append(row)

    duplicates = []
    for code, rows in by_code.items():
        servers = sorted({r["server"] for r in rows if r["server"]})
        if len(servers) >= 2:
            duplicates.append({
                "code": code,
                "servers": servers,
                "count_servers": len(servers),
                "count_rows": len(rows),
            })

    duplicates.sort(key=lambda x: (-x["count_servers"], x["code"]))

    print()
    print(f"Passcodes présents sur plusieurs serveurs : {len(duplicates)}")
    print()

    for d in duplicates:
        print(f"{d['code']} => {', '.join(d['servers'])} (rows={d['count_rows']})")


if __name__ == "__main__":
    main()
