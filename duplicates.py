import csv
import re
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


def norm(v):
    return re.sub(r"\s+", " ", clean(v)).strip().lower()


def fetch_sheet(gid):
    r = requests.get(BASE_URL + gid, timeout=30)
    r.raise_for_status()
    return r.text


def find_header_row(lines):
    rows = list(csv.reader(lines))
    for i, row in enumerate(rows):
        normalized = [norm(c) for c in row]
        has_code = any(c in normalized for c in ["base code", "passcode", "code"])
        has_server = any(c in normalized for c in ["shard", "server", "homecoming server"])
        if has_code and has_server:
            return i, rows
    raise ValueError("Header row not found")


def pick(row, *keys):
    for k in keys:
        if k in row and clean(row.get(k)):
            return clean(row.get(k))
    return ""


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
        code = pick(row, "Base Code", "Passcode", "Code")
        if not code:
            continue

        server = pick(row, "Shard", "Server", "Homecoming Server")
        if not server:
            server = "Unknown"

        result.append({
            "sheet": sheet_name,
            "code": code.upper(),
            "server": server,
        })

    return result


def main():
    all_rows = []

    for s in SHEETS:
        try:
            rows = parse_sheet(s["name"], s["gid"])
            all_rows.extend(rows)
            print(f"{s['name']}: {len(rows)} rows parsed")
        except Exception as e:
            print(f"{s['name']}: ERROR - {e}")

    by_code = defaultdict(list)
    for row in all_rows:
        by_code[row["code"]].append(row)

    cross_server = []
    total_same_code = 0

    for code in sorted(by_code.keys()):
        rows = by_code[code]
        servers = sorted({r["server"] for r in rows if r["server"]})

        if len(servers) >= 2:
            cross_server.append((code, servers, len(rows)))

        if len(rows) >= 2:
            total_same_code += 1

    test_codes = {row["code"] for row in all_rows if row["sheet"] == "TEST"}
    other_codes = {row["code"] for row in all_rows if row["sheet"] != "TEST"}
    unique_test_codes = test_codes - other_codes

    print()
    print("=== TEST 1 : mêmes passcodes sur des serveurs différents ===")
    print(f"Total: {len(cross_server)}")
    for code, servers, count_rows in cross_server:
        print(f"{code} => {', '.join(servers)} (rows={count_rows})")

    print()
    print("=== TEST 2 : mêmes passcodes, peu importe le serveur ===")
    print(f"Total: {total_same_code}")

    print()
    print("=== TEST 3 : bases dans TEST avec un passcode introuvable ailleurs ===")
    print(f"Total: {len(unique_test_codes)}")


if __name__ == "__main__":
    main()
