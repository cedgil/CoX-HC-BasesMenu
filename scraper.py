import csv
import requests
import re
import os
import time
import random
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

print("Secrets chargés OK")

BASES = {}

SPREADSHEET_ID = "14DqavAx6ov60d92rhvwy2sNEW_909MCHp421GM4q-Yk"
BASE_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"

SHEET_GIDS = [
    "2014365553",
    "1746205606"
]

KNOWN_SERVERS = {
    "Everlasting",
    "Excelsior",
    "Torchbearer",
    "Indomitable",
    "Reunion"
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

ENABLE_REDDIT = os.environ.get("ENABLE_REDDIT", "true").lower() == "true"


def make_session():
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s = requests.Session()
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


session = make_session()


def clean(v):
    return (v or "").strip()


def find_codes(text):
    return re.findall(r"\b[A-Z0-9]{2,}-\d+\b", text.upper())


def is_valid_code(code):
    return bool(re.match(r"^[A-Z0-9]{2,}-\d+$", code))


def load_sheet(gid):
    url = f"{BASE_SHEET_URL}/export?format=csv&gid={gid}"
    print(f"Loading sheet {gid}")

    try:
        r = session.get(url, timeout=30)
        r.raise_for_status()
        reader = csv.reader(r.text.splitlines())

        for row in reader:
            row = [clean(x) for x in row]

            if not any(row):
                continue

            server = next((c for c in row if c in KNOWN_SERVERS), None)
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
                add_base(server, name, code, style, "google")

    except Exception as e:
        print(f"Sheet error {gid}: {e}")


def load_google():
    print(f"{len(SHEET_GIDS)} sheets configured")
    for gid in SHEET_GIDS:
        load_sheet(gid)


def load_reddit():
    if not ENABLE_REDDIT:
        print("Reddit disabled by config")
        return

    url = "https://www.reddit.com/r/Cityofheroes/.json?limit=100"

    for attempt in range(1, 4):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*"
        }

        try:
            r = session.get(url, headers=headers, timeout=30)

            if r.status_code == 403:
                print(f"Reddit blocked (403) on attempt {attempt}, skipping source")
                return

            r.raise_for_status()

            matches = find_codes(r.text)
            for code in matches:
                add_base("Unknown", "Reddit Found", code, "", "reddit")

            print(f"Reddit loaded: {len(matches)} codes found")
            return

        except Exception as e:
            print(f"Reddit attempt {attempt} failed: {e}")
            if attempt < 3:
                time.sleep(attempt * 2)

    print("Reddit skipped after retries")


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


def chunk_list(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def push_batch(batch, batch_num, attempt_limit=3):
    url = f"{SUPABASE_URL}?on_conflict=code"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    for attempt in range(1, attempt_limit + 1):
        try:
            r = session.post(url, headers=headers, json=batch, timeout=60)
        except requests.RequestException as e:
            print(f"Batch {batch_num} HTTP error attempt {attempt}: {e}")
            if attempt < attempt_limit:
                time.sleep(attempt * 10)
                continue
            raise

        print(f"Batch {batch_num} status: {r.status_code}")
        if r.text:
            print(r.text[:300])

        if r.ok:
            return

        if r.status_code == 503 and "PGRST002" in r.text:
            if attempt < attempt_limit:
                wait_time = attempt * 15
                print(f"Batch {batch_num}: schema cache indisponible, retry dans {wait_time}s")
                time.sleep(wait_time)
                continue

        r.raise_for_status()


def push_bases():
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

    batch_size = 100
    for idx, batch in enumerate(chunk_list(data, batch_size), start=1):
        print(f"Pushing batch {idx} ({len(batch)} rows)")
        push_batch(batch, idx)


def main():
    load_google()
    load_reddit()
    print(f"Total bases: {len(BASES)}")
    push_bases()


if __name__ == "__main__":
    main()
