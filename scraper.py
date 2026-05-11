import csv
import requests
import re
import os
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

# =========================================================
# HELPERS
# =========================================================

def clean(v):
    return (v or "").strip()


def normalize_header(v):
    return clean(v).lower()


def is_valid_code(code):

    return bool(
        re.match(
            r"^[A-Z0-9]{2,}-\d+$",
            code.upper()
        )
    )


def find_codes(text):

    return re.findall(
        r"\b[A-Z0-9]{2,}-\d+\b",
        (text or "").upper()
    )

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
# HEADER DETECTION
# =========================================================

def find_header(rows):

    for idx, row in enumerate(rows):

        normalized = [
            normalize_header(c)
            for c in row
        ]

        joined = " | ".join(normalized)

        # VERIFIED / TEST
        if (
            "base code" in joined
            or "passcode" in joined
        ):
            return idx

        # PENDING
        if (
            "shard" in joined
            and "code" in joined
            and "name" in joined
        ):
            return idx

    return -1

# =========================================================
# COLUMN FINDERS
# =========================================================

def find_value(row, possible_keys):

    normalized = {
        normalize_header(k): v
        for k, v in row.items()
    }

    for key in possible_keys:

        if key in normalized:

            return clean(normalized[key])

    return ""

# =========================================================
# GOOGLE PARSER
# =========================================================

def load_google_sheet(gid, sheet_category):

    url = (
        f"{BASE_SHEET_URL}"
        f"/export?format=csv&gid={gid}"
    )

    print("================================")
    print(f"LOADING SHEET {gid}")
    print(f"CATEGORY: {sheet_category}")
    print("================================")

    try:

        r = requests.get(url, timeout=60)

        r.raise_for_status()

        lines = r.text.splitlines()

        rows = list(csv.reader(lines))

        header_index = find_header(rows)

        if header_index < 0:

            print(
                f"SKIPPING EMPTY SHEET {gid}"
            )

            return

        header = rows[header_index]

        print("HEADER FOUND:")
        print(header)

        data_rows = rows[header_index + 1:]

        csv_text = "\n".join([
            ",".join(r)
            for r in [header] + data_rows
        ])

        reader = list(
            csv.DictReader(csv_text.splitlines())
        )

        print("FIRST ROWS:")

        for x in reader[:3]:
            print(x)

        print(f"TOTAL ROWS: {len(reader)}")

        added = 0

        for row in reader:

            # =============================================
            # PENDING FORMAT
            # =============================================

            if sheet_category == "pending":

                raw_code = find_value(row, [
                    "code",
                    "base code",
                    "passcode"
                ])

                name = find_value(row, [
                    "name",
                    "base name"
                ])

                server = find_value(row, [
                    "shard",
                    "server"
                ])

                venue = ""

                tag1 = ""

                tag2 = ""

                style = "Pending"

            # =============================================
            # VERIFIED / TEST FORMAT
            # =============================================

            else:

                raw_code = find_value(row, [
                    "base code",
                    "passcode",
                    "code"
                ])

                name = find_value(row, [
                    "base name (sg / vg)",
                    "base name",
                    "sg name",
                    "name"
                ])

                venue = find_value(row, [
                    "venue",
                    "style",
                    "type"
                ])

                tag1 = find_value(row, [
                    "description tag1",
                    "tag1"
                ])

                tag2 = find_value(row, [
                    "description tag2",
                    "tag2"
                ])

                server = find_value(row, [
                    "shard",
                    "server"
                ])

                if sheet_category == "test":

                    style = "TEST"

                else:

                    style = (
                        venue
                        if venue
                        else "Check Yourself"
                    )

            # =============================================
            # VALIDATION
            # =============================================

            if not raw_code:
                continue

            codes = find_codes(raw_code)

            if not codes:
                continue

            # =============================================
            # INSERT
            # =============================================

            for code in codes:

                print(
                    f"ADDING {code} | "
                    f"{sheet_category}"
                )

                add_base(

                    server=server,

                    name=name,

                    code=code,

                    style=style,

                    category=sheet_category,

                    source="google",

                    venue=venue,

                    tag1=tag1,

                    tag2=tag2
                )

                added += 1

        print(
            f"ADDED {added} BASES "
            f"FROM {gid}"
        )

    except Exception as e:

        print(f"GOOGLE SHEET ERROR {gid}:")
        print(e)

# =========================================================
# LOAD GOOGLE
# =========================================================

def load_google():

    print(
        f"{len(SHEETS)} SHEETS CONFIGURED"
    )

    for gid, category in SHEETS.items():

        load_google_sheet(gid, category)

# =========================================================
# SCORING
# =========================================================

def compute_score(base):

    score = 0

    if base["server"] in VALID_SERVERS:
        score += 5

    if base["name"]:
        score += 5

    if base["style"]:
        score += 5

    if is_valid_code(base["code"]):
        score += 5

    if "google" in base["sources"]:
        score += 20

    score += STYLE_SCORES.get(
        base["style"],
        0
    )

    return max(score, 0)

# =========================================================
# NORMALIZE SCORES
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

        "Authorization":
            f"Bearer {SUPABASE_KEY}",

        "Content-Type": "application/json",

        "Prefer":
            "resolution=merge-duplicates"
    }

# =========================================================
# CHUNKER
# =========================================================

def chunk_list(items, size):

    for i in range(0, len(items), size):

        yield items[i:i + size]

# =========================================================
# PUSH
# =========================================================

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

    print(f"PUSHING {len(payload)} BASES")

    for idx, batch in enumerate(
        chunk_list(payload, 100),
        start=1
    ):

        print(
            f"BATCH {idx} "
            f"({len(batch)} rows)"
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

    print("================================")
    print("SCRAPER START")
    print("================================")

    load_google()

    normalize_scores()

    print(
        f"TOTAL BASES: {len(BASES)}"
    )

    push_bases()

    print("================================")
    print("DONE")
    print("================================")

if __name__ == "__main__":

    main()
