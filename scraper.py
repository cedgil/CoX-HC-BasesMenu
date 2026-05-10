import csv
import requests
import re
import os
import json
import time
import random

from datetime import datetime, timezone
from collections import defaultdict

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
# GOOGLE SHEETS
# =========================================================

SHEETS = {

    # VERIFIED
    "2014365553": {
        "name": "NORMAL",
        "category": "verified"
    },

    # TEST
    "1746205606": {
        "name": "TEST",
        "category": "test"
    },

    # REQUEST PENDING
    "1332493366": {
        "name": "PENDING",
        "category": "pending"
    }
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
    "Check Yourself": 2
}

CATEGORY_SCORES = {
    "verified": 10,
    "test": 2,
    "pending": 1
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
    return bool(
        re.match(r"^[A-Z0-9]{2,}-\d+$", code.upper())
    )


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
    source,
    category="verified",
    venue="",
    tag1="",
    tag2=""
):

    if not code:
        return

    code = clean(code).upper()

    if not is_valid_code(code):
        return

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

# =========================================================
# GOOGLE PARSER
# =========================================================

def find_header(rows):

    for idx, row in enumerate(rows):

        normalized = [clean(c) for c in row]

        if (
            "Base Code" in normalized
            and "Venue" in normalized
        ):
            return idx

    return -1


def load_google_sheet(gid, sheet_info):

    category = sheet_info["category"]

    url = (
        f"{BASE_SHEET_URL}"
        f"/export?format=csv&gid={gid}"
    )

    print(f"Loading Google Sheet {gid} ({category})")

    try:

        r = requests.get(url, timeout=30)

        r.raise_for_status()

        lines = r.text.splitlines()

        rows = list(csv.reader(lines))

        header_index = find_header(rows)

        if header_index < 0:

            print(f"Header not found for {gid}")
            return

        header = rows[header_index]

        data_rows = rows[header_index + 1:]

        csv_text = "\n".join([
            ",".join(r)
            for r in [header] + data_rows
        ])

        reader = csv.DictReader(csv_text.splitlines())

        for row in reader:

            raw_code = clean(
                row.get("Base Code")
            )

            name = clean(
                row.get("Base Name (SG / VG)")
            )

            venue = clean(
                row.get("Venue")
            )

            tag1 = clean(
                row.get("Description Tag1")
            )

            tag2 = clean(
                row.get("Description Tag2")
            )

            server = clean(
                row.get("Shard")
                or row.get("Server")
            )

            if not raw_code:
                continue

            codes = find_codes(raw_code)

            if not codes:
                continue

            style = venue if venue else "Check Yourself"

            for code in codes:

                add_base(
                    server=server,
                    name=name,
                    code=code,
                    style=style,
                    source="google",
                    category=category,
                    venue=venue,
                    tag1=tag1,
                    tag2=tag2
                )

    except Exception as e:

        print(f"Google sheet error {gid}: {e}")

# =========================================================
# GOOGLE LOAD
# =========================================================

def load_google():

    print(f"{len(SHEETS)} sheets configured")

    for gid, sheet_info in SHEETS.items():

        load_google_sheet(
            gid,
            sheet_info
        )

# =========================================================
# REDDIT
# =========================================================

def load_reddit():

    if not ENABLE_REDDIT:

        print("Reddit disabled")
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

            print("Reddit blocked")
            return

        matches = find_codes(r.text)

        for code in matches:

            add_base(
                server="Unknown",
                name="Reddit Found",
                code=code,
                style="Check Yourself",
                source="reddit",
                category="verified"
            )

        print(f"Reddit: {len(matches)} codes")

    except Exception as e:

        print(f"Reddit error: {e}")

# =========================================================
# SCORING
# =========================================================

def compute_score(base):

    score = 0

    # -------------------------
    # QUALITY
    # -------------------------

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

    # -------------------------
    # SOURCES
    # -------------------------

    if "google" in base["sources"]:
        score += 20

    if "reddit" in base["sources"]:
        score += 5

    # -------------------------
    # STYLE
    # -------------------------

    score += STYLE_SCORES.get(
        base["style"],
        0
    )

    # -------------------------
    # CATEGORY
    # -------------------------

    score += CATEGORY_SCORES.get(
        base["category"],
        0
    )

    # -------------------------
    # HUB DETECTION
    # -------------------------

    search_text = " ".join([

        base["name"],
        base["venue"],
        base["tag1"],
        base["tag2"]

    ]).lower()

    if contains_keyword(
        search_text,
        HUB_KEYWORDS
    ):
        score += 7

    return max(score, 0)

# =========================================================
# NORMALIZE
# =========================================================

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

    print(f"Pushing {len(payload)} bases")

    for batch in chunk_list(payload, 100):

        r = requests.post(
            url,
            headers=supabase_headers(),
            json=batch,
            timeout=60
        )

        print(r.status_code)

# =========================================================
# MAIN
# =========================================================

def main():

    load_google()

    load_reddit()

    normalize_scores()

    print(
        f"Total bases loaded: "
        f"{len(BASES)}"
    )

    push_bases()

    print("Done")

if __name__ == "__main__":

    main()
