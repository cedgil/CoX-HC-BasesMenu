import csv
import requests
import re
import os
import random
from datetime import datetime, timezone

# =========================================================
# CONFIG
# =========================================================

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

NOW = datetime.now(timezone.utc)

SPREADSHEET_ID = "14DqavAx6ov60d92rhvwy2sNEW_909MCHp421GM4q-Yk"

BASE_SHEET_URL = (
    f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
)

# =========================================================
# SHEETS
# =========================================================

SHEETS = {
    "2014365553": "verified",
    "1746205606": "test",
    "1332493366": "pending"
}

ENABLE_REDDIT = False

# =========================================================
# STORAGE
# =========================================================

BASES = {}

# =========================================================
# CONSTANTS
# =========================================================

VALID_SERVERS = [
    "Everlasting",
    "Excelsior",
    "Torchbearer",
    "Indomitable",
    "Victory",
    "Reunion"
]

STYLE_SCORES = {
    "Transit Hub": 5,
    "RP": 5,
    "Arcane": 5,
    "Tech": 5,
    "Maze": 5,
    "Utilities": 5,
    "Check Yourself": 2,
    "TEST": 1,
    "Pending": 1
}

HUB_KEYWORDS = [
    "hub",
    "travel",
    "teleport",
    "teleporter",
    "portal",
    "transit",
    "tp"
]

BAD_WORDS = [
    "nazi",
    "hitler",
    "porn",
    "rape",
    "racist"
]

# =========================================================
# HELPERS
# =========================================================

def clean(v):
    return (v or "").strip()


def is_valid_code(code):
    return bool(re.match(r"^[A-Z0-9]{2,}-\d+$", code.upper()))


def find_codes(text):
    return re.findall(
        r"\b[A-Z0-9]{2,}-\d+\b",
        (text or "").upper()
    )


def contains_keyword(text, keywords):
    t = (text or "").lower()
    return any(k in t for k in keywords)


# =========================================================
# BASE STORAGE
# =========================================================

def add_base(
    server,
    name,
    code,
    style,
    category,
    source,
    venue="",
    tag1="",
    tag2=""
):

    if not code:
        return False

    code = clean(code).upper()

    if not is_valid_code(code):
        return False

    if code not in BASES:

        BASES[code] = {

            "code": code,

            "server": clean(server) or "Unknown",

            "name": clean(name) or "Unknown",

            "style": clean(style) or "Check Yourself",

            "category": category,

            "venue": clean(venue),
            "tag1": clean(tag1),
            "tag2": clean(tag2),

            "sources": [],

            "score": 0
        }

    if source not in BASES[code]["sources"]:
        BASES[code]["sources"].append(source)

    return True


# =========================================================
# HEADER DETECTION
# =========================================================

def find_header(rows):

    for idx, row in enumerate(rows):

        normalized = [clean(c) for c in row]

        upper = [c.upper() for c in normalized]

        # VERIFIED / TEST
        if (
            "BASE CODE" in upper
            and (
                "BASE NAME (SG / VG)" in upper
                or "VENUE" in upper
            )
        ):
            return idx

        # PENDING
        if (
            "CODE" in upper
            and "NAME" in upper
            and "SHARD" in upper
        ):
            return idx

    return -1


# =========================================================
# GOOGLE PARSER
# =========================================================

def load_google_sheet(gid, category):

    print("================================")
    print(f"LOADING SHEET {gid}")
    print(f"CATEGORY: {category}")
    print("================================")

    url = (
        f"{BASE_SHEET_URL}"
        f"/export?format=csv&gid={gid}"
    )

    try:

        r = requests.get(url, timeout=30)

        r.raise_for_status()

        lines = r.text.splitlines()

        rows = list(csv.reader(lines))

        header_index = find_header(rows)

        if header_index < 0:

            print(f"HEADER NOT FOUND FOR {gid}")
            return

        header = rows[header_index]

        data_rows = rows[header_index + 1:]

        print("HEADER FOUND:")
        print(header)

        print("FIRST ROWS:")

        for preview in data_rows[:3]:

            try:
                row_preview = dict(zip(header, preview))
                print(row_preview)
            except:
                pass

        print(f"TOTAL ROWS: {len(data_rows)}")

        csv_text = "\n".join([
            ",".join(r)
            for r in [header] + data_rows
        ])

        reader = csv.DictReader(csv_text.splitlines())

        added_count = 0

        for row in reader:

            upper_keys = {
                (k or "").upper(): v
                for k, v in row.items()
            }

            # =================================================
            # VERIFIED / TEST
            # =================================================

            if category in ["verified", "test"]:

                raw_code = clean(
                    upper_keys.get("BASE CODE")
                )

                name = clean(
                    upper_keys.get("BASE NAME (SG / VG)")
                )

                venue = clean(
                    upper_keys.get("VENUE")
                )

                tag1 = clean(
                    upper_keys.get("DESCRIPTION TAG1")
                )

                tag2 = clean(
                    upper_keys.get("DESCRIPTION TAG2")
                )

                server = clean(
                    upper_keys.get("SHARD")
                    or upper_keys.get("SERVER")
                )

                if not raw_code:
                    continue

                codes = find_codes(raw_code)

                if not codes:
                    continue

                style = venue if venue else "Check Yourself"

                if category == "test":
                    style = "TEST"

                for code in codes:

                    added = add_base(
                        server=server,
                        name=name,
                        code=code,
                        style=style,
                        category=category,
                        source="google",
                        venue=venue,
                        tag1=tag1,
                        tag2=tag2
                    )

                    if added:
                        added_count += 1

            # =================================================
            # PENDING
            # =================================================

            elif category == "pending":

                raw_code = clean(
                    upper_keys.get("CODE")
                )

                name = clean(
                    upper_keys.get("NAME")
                )

                server = clean(
                    upper_keys.get("SHARD")
                )

                if not raw_code:
                    continue

                codes = find_codes(raw_code)

                if not codes:
                    continue

                for code in codes:

                    added = add_base(
                        server=server,
                        name=name,
                        code=code,
                        style="Pending",
                        category="pending",
                        source="google"
                    )

                    if added:
                        added_count += 1

        print(f"ADDED {added_count} BASES FROM {gid}")

    except Exception as e:

        print(f"GOOGLE SHEET ERROR {gid}: {e}")


def load_google():

    print("================================")
    print("SCRAPER START")
    print("================================")

    print(f"{len(SHEETS)} SHEETS CONFIGURED")

    for gid, category in SHEETS.items():

        load_google_sheet(gid, category)


# =========================================================
# REDDIT
# =========================================================

def load_reddit():

    if not ENABLE_REDDIT:

        print("REDDIT DISABLED")
        return

    url = (
        "https://www.reddit.com/"
        "r/Cityofheroes/.json?limit=100"
    )

    headers = {
        "User-Agent": random.choice([
            "Mozilla/5.0",
            "Chrome/125",
            "Firefox/126"
        ])
    }

    try:

        r = requests.get(
            url,
            headers=headers,
            timeout=30
        )

        if r.status_code == 403:

            print("REDDIT BLOCKED")
            return

        matches = find_codes(r.text)

        for code in matches:

            add_base(
                server="Unknown",
                name="Reddit Found",
                code=code,
                style="Check Yourself",
                category="verified",
                source="reddit"
            )

        print(f"REDDIT: {len(matches)} CODES")

    except Exception as e:

        print(f"REDDIT ERROR: {e}")


# =========================================================
# SCORING
# =========================================================

def compute_score(base):

    score = 0

    if base["server"] in VALID_SERVERS:
        score += 5
    else:
        score -= 5

    if base["name"]:
        score += 5

    if base["style"]:
        score += 5

    if is_valid_code(base["code"]):
        score += 5

    if "google" in base["sources"]:
        score += 20

    if "reddit" in base["sources"]:
        score += 6

    search_text = " ".join([
        base["name"],
        base["venue"],
        base["tag1"],
        base["tag2"]
    ]).lower()

    if contains_keyword(search_text, HUB_KEYWORDS):
        score += 7

    score += STYLE_SCORES.get(
        base["style"],
        0
    )

    text = (
        f'{base["name"]} {base["code"]}'
    ).lower()

    if any(w in text for w in BAD_WORDS):
        score -= 20

    return max(score, 0)


def normalize_scores():

    if not BASES:
        return

    raw_scores = []

    for base in BASES.values():

        raw = compute_score(base)

        base["_raw_score"] = raw

        raw_scores.append(raw)

    max_score = max(raw_scores)

    if max_score <= 0:
        max_score = 1

    for base in BASES.values():

        normalized = round(
            (base["_raw_score"] / max_score) * 100
        )

        base["score"] = normalized


# =========================================================
# SUPABASE
# =========================================================

def supabase_headers():

    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }


def chunk_list(items, size):

    for i in range(0, len(items), size):

        yield items[i:i + size]


def push_bases():

    url = (
        f"{SUPABASE_URL}"
        f"?on_conflict=code"
    )

    payload = []

    for base in BASES.values():

        payload.append({

            "code": base["code"],

            "server": base["server"],
            "name": base["name"],
            "style": base["style"],
            "category": base["category"],

            "venue": base["venue"],
            "tag1": base["tag1"],
            "tag2": base["tag2"],

            "sources": base["sources"],

            "score": base["score"],

            "updated_at": NOW.isoformat(),
            "last_seen_at": NOW.isoformat(),

            "missing_since": None,
            "is_missing": False
        })

    print(f"TOTAL BASES: {len(payload)}")
    print(f"PUSHING {len(payload)} BASES")

    batch_size = 100

    for idx, batch in enumerate(
        chunk_list(payload, batch_size),
        start=1
    ):

        print(
            f"PUSHING BATCH {idx} "
            f"({len(batch)} ROWS)"
        )

        r = requests.post(
            url,
            headers=supabase_headers(),
            json=batch,
            timeout=60
        )

        print(r.status_code)

        if r.text:
            print(r.text[:300])


# =========================================================
# MAIN
# =========================================================

def main():

    load_google()

    load_reddit()

    normalize_scores()

    push_bases()

    print("================================")
    print("SCRAPER DONE")
    print("================================")


if __name__ == "__main__":

    main()
