import csv
import requests
from collections import defaultdict

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

    output = []
    for row in rows[header_idx:]:
        output.append(row)

    from io import StringIO
    sio = StringIO()
    writer = csv.writer(sio)
    for row in output:
        writer.writerow(row)
    sio.seek(0)

    reader = csv.DictReader(sio)

    result = []
    for row in reader:
        code = clean(row.get("Base Code"))
        if not code:
            continue

        server = clean(row.get("Shard") or row.get("Server") or row.get("Venue") or "Unknown")
        name = clean(row.get("Base Name (SG / VG)") or row.get("Base Name") or "")
        result.append({
            "sheet": sheet_name,
            "code": code.upper(),
            "server": server,
            "name": name,
        })
    return result

all_rows = []
for s in SHEETS:
    all_rows.extend(parse_sheet(s["name"], s["gid"]))

by_code = defaultdict(list)
for row in all_rows:
    by_code[row["code"]].append(row)

duplicates = []
for code, rows in by_code.items():
    servers = {r["server"] for r in rows if r["server"]}
    if len(servers) >= 2:
        duplicates.append({
            "code": code,
            "servers": sorted(servers),
            "count_servers": len(servers),
            "count_rows": len(rows),
        })

duplicates.sort(key=lambda x: (x["count_servers"], x["code"]))

print(f"Passcodes présents sur plusieurs serveurs : {len(duplicates)}")
for d in duplicates:
    print(d["code"], "=>", ", ".join(d["servers"]))
