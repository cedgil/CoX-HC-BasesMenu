import csv, requests, re, json, os
from datetime import datetime

BASES = {}

SPREADSHEET_ID = "14DqavAx6ov60d92rhvwy2sNEW_909MCHp421GM4q-Yk"
BASE_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"

# GIDS FIXES
SHEET_GIDS = [
    "2014365553",  # MAIN
    "1746205606"   # TEST
]

KNOWN_SERVERS = {
    "Everlasting",
    "Excelsior",
    "Torchbearer",
    "Indomitable",
    "Reunion"
}

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# ---------------- UTILS ----------------
def clean(v):
    return (v or "").strip()

def find_codes(text):
    return re.findall(r'\b[A-Z0-9]{2,}-\d+\b', text.upper())

def is_valid_code(code):
    return bool(re.match(r'^[A-Z0-9]{2,}-\d+$', code))

# ---------------- GOOGLE ----------------
def load_sheet(gid):
    url = f"{BASE_SHEET_URL}/export?format=csv&gid={gid}"

    print(f"Loading sheet {gid}")

    try:
        r = requests.get(url)

        if r.status_code != 200:
            print(f"Failed sheet {gid}")
            return

        reader = csv.reader(r.text.splitlines())

        for row in reader:
            row = [clean(x) for x in row]

            if not any(row):
                continue

            server = next(
                (c for c in row if c in KNOWN_SERVERS),
                None
            )

            if not server:
                continue

            codes = find_codes(" ".join(row))

            if not codes:
                continue

            name = next((
                c for c in row
                if c
                and c not in KNOWN_SERVERS
                and not any(code in c for code in codes)
                and not c.startswith("@")
                and not is_valid_code(c)
            ), "Unknown")

            style = "TEST" if gid == "1746205606" else ""

            for code in codes:
                add_base(
                    server,
                    name,
                    code,
                    style,
                    "google"
                )

    except Exception as e:
        print("Sheet error:", e)

def load_google():
    print(f"{len(SHEET_GIDS)} sheets configured")

    for gid in SHEET_GIDS:
        load_sheet(gid)

# ---------------- REDDIT ----------------
def load_reddit():
    try:
        r = requests.get(
            "https://www.reddit.com/r/Cityofheroes/.json",
            headers={"User-Agent": "Mozilla"}
        )

        matches = find_codes(r.text)

        for code in matches:
            add_base(
                "Unknown",
                "Reddit Found",
                code,
                "",
                "reddit"
            )

    except:
        print("Reddit failed")

# ---------------- ADD BASE ----------------
def add_base(server, name, code, style, source):
    if not code:
        return

    code = code.strip().upper()

    if code not in BASES:
        BASES[code] = {
            "code": code,
            "server": clean(server) or "Unknown",
            "name": clean(name) or "Unknown",
            "style": style or "",
            "sources": []
        }

    if source not in BASES[code]["sources"]:
        BASES[code]["sources"].append(source)

# ---------------- PUSH SUPABASE ----------------
def push_bases():
    url = f"{SUPABASE_URL}?on_conflict=code"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    data = []

    for b in BASES.values():
        data.append({
            "code": b["code"],
            "server": b["server"],
            "name": b["name"],
            "style": b["style"],
            "sources": b["sources"],
            "updated_at": datetime.utcnow().isoformat()
        })

    print(f"Pushing {len(data)} bases to Supabase")

    r = requests.post(
        url,
        headers=headers,
        json=data
    )

    print(r.status_code)
    print(r.text)

# ---------------- MAIN ----------------
def main():
    load_google()
    load_reddit()

    print(f"Total bases: {len(BASES)}")

    push_bases()

if __name__ == "__main__":
    main()
