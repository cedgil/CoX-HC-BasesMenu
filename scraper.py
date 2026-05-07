import csv
import requests
import re
import os
import time
import random
from datetime import datetime, timezone, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

print("Secrets chargés OK")

BASES = {}
NOW = datetime.now(timezone.utc)

SPREADSHEET_ID = "14DqavAx6ov60d92rhvwy2sNEW_909MCHp421GM4q-Yk"
BASE_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"

SHEET_GIDS = [
    "2014365553",
    "1746205606"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

ENABLE_REDDIT = os.environ.get("ENABLE_REDDIT", "true").lower() == "true"
DEBUG_ROWS = int(os.environ.get("DEBUG_ROWS", "10"))


def make_session():
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST", "PATCH", "DELETE"]),
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


def add_base(server, name, code, style, source):
    if not code:
        return

    code = code.strip().upper()

    if code not in BASES:
        BASES[code] = {
            "code": code,
            "server": clean(server) or "Unknown",
            "name": clean(name) or "Unknown",
            "style": clean(style),
            "sources": []
        }

    if source not in BASES[code]["sources"]:
        BASES[code]["sources"].append(source)


def find_real_header_row(lines):
    reader = csv.reader(lines)
    rows = list(reader)

    for idx, row in enumerate(rows):
        normalized = [clean(col) for col in row]
        if "Base Code" in normalized and "Venue" in normalized:
            return idx, rows

    raise ValueError("Impossible de trouver la vraie ligne d'en-têtes (Base Code / Venue)")


def load_sheet(gid):
    url = f"{BASE_SHEET_URL}/export?format=csv&gid={gid}"
    print(f"Loading sheet {gid}")

    try:
        r = session.get(url, timeout=30)
        r.raise_for_status()

        lines = r.text.splitlines()
        header_idx, rows = find_real_header_row(lines)

        print(f"Header row detected at line {header_idx + 1}")

        header = rows[header_idx]
        data_rows = rows[header_idx + 1:]
        csv_text = "\n".join([",".join(row) for row in [header] + data_rows])
        reader = csv.DictReader(csv_text.splitlines())

        print("CSV headers:", reader.fieldnames)

        for i, row in enumerate(reader, start=1):
            code = clean(row.get("Base Code"))
            name = clean(row.get("Base Name (SG / VG)"))
            venue = clean(row.get("Venue"))
            server = clean(row.get("Shard") or row.get("Server")) or "Unknown"

            if i <= DEBUG_ROWS:
                style_preview = "TEST" if gid == "1746205606" else (venue if venue else "Check Yourself")
                print(f"ROW {i} | code={code} | venue={venue} | style={style_preview}")

            if not code:
                continue

            if not is_valid_code(code):
                codes = find_codes(code)
                if not codes:
                    continue
            else:
                codes = [code]

            style = "TEST" if gid == "1746205606" else (venue if venue else "Check Yourself")

            for c in codes:
                add_base(server, name or "Unknown", c, style, "google")

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


def chunk_list(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def supabase_headers(prefer=None):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def push_batch(batch, batch_num, attempt_limit=3):
    url = f"{SUPABASE_URL}?on_conflict=code"
    headers = supabase_headers("resolution=merge-duplicates")

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

        if r.status_code == 503 and "PGRST002" in r.text and attempt < attempt_limit:
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
            "updated_at": NOW.isoformat(),
            "last_seen_at": NOW.isoformat(),
            "missing_since": None,
            "is_missing": False
        })

    print(f"Pushing {len(data)} bases to Supabase")

    batch_size = 100
    for idx, batch in enumerate(chunk_list(data, batch_size), start=1):
        print(f"Pushing batch {idx} ({len(batch)} rows)")
        push_batch(batch, idx)


def fetch_existing_bases():
    all_rows = []
    offset = 0
    limit = 1000

    while True:
        url = f"{SUPABASE_URL}?select=code,style,last_seen_at,missing_since,is_missing&offset={offset}&limit={limit}"
        r = session.get(url, headers=supabase_headers(), timeout=60)
        r.raise_for_status()
        rows = r.json()
        all_rows.extend(rows)
        if len(rows) < limit:
            break
        offset += limit

    print(f"Existing bases in DB: {len(all_rows)}")
    return all_rows


def patch_base(code, payload):
    url = f"{SUPABASE_URL}?code=eq.{code}"
    headers = supabase_headers("return=minimal")
    r = session.patch(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()


def delete_base(code):
    url = f"{SUPABASE_URL}?code=eq.{code}"
    headers = supabase_headers("return=minimal")
    r = session.delete(url, headers=headers, json={}, timeout=60)
    r.raise_for_status()


def apply_missing_rules():
    existing = fetch_existing_bases()
    found_codes = set(BASES.keys())

    no_action_count = 0
    dead_or_not_count = 0
    deleted_count = 0
    newly_missing_count = 0
    restored_count = 0

    for row in existing:
        code = row.get("code")
        if not code:
            continue

        if code in found_codes:
            if row.get("is_missing") or row.get("missing_since"):
                patch_base(code, {
                    "is_missing": False,
                    "missing_since": None,
                    "last_seen_at": NOW.isoformat()
                })
                restored_count += 1
            continue

        missing_since_raw = row.get("missing_since")

        if not missing_since_raw:
            patch_base(code, {
                "is_missing": True,
                "missing_since": NOW.isoformat()
            })
            newly_missing_count += 1
            continue

        missing_since = datetime.fromisoformat(missing_since_raw.replace("Z", "+00:00"))
        missing_days = (NOW - missing_since).days

        if missing_days <= 5:
            no_action_count += 1
            continue

        if 5 < missing_days < 30:
            if row.get("style") != "DEAD-OR-NOT":
                patch_base(code, {
                    "is_missing": True,
                    "style": "DEAD-OR-NOT"
                })
            dead_or_not_count += 1
            continue

        if missing_days >= 30:
            delete_base(code)
            deleted_count += 1

    print(
        f"Missing tracking: newly_missing={newly_missing_count}, "
        f"no_action={no_action_count}, dead_or_not={dead_or_not_count}, "
        f"restored={restored_count}, deleted={deleted_count}"
    )


def main():
    load_google()
    load_reddit()
    print(f"Total bases found in sources: {len(BASES)}")
    push_bases()
    apply_missing_rules()


if __name__ == "__main__":
    main()
