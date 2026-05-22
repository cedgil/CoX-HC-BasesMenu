#!/usr/bin/env python3

import os
import re
import requests

from bs4 import BeautifulSoup

# =========================================================
# CONFIG
# =========================================================

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

SUPABASE_TABLE = "scraped_bases_forum"

# =========================================================
# FIX REST URL
# =========================================================

if "/rest/v1/" in SUPABASE_URL:
    REST_BASE_URL = SUPABASE_URL.split("/rest/v1")[0] + "/rest/v1"

elif SUPABASE_URL.endswith("/rest/v1"):
    REST_BASE_URL = SUPABASE_URL

else:
    REST_BASE_URL = SUPABASE_URL + "/rest/v1"

API_URL = f"{REST_BASE_URL}/{SUPABASE_TABLE}"

# =========================================================
# SOURCES
# =========================================================

SOURCES = [

    {
        "url": "https://forums.homecomingservers.com/topic/62785-list-your-base-for-the-noncompetitive-our-based-showcase/",
        "fields": {
            "supergroup_name": "Supergroup Name:",
            "shard": "Shard/Server:",
            "base_code": "Base Code:",
            "category": "Category to list base in:"
        }
    },

    {
        "url": "https://forums.homecomingservers.com/topic/56486-2025-homecoming-base-contest-rules-entries-thread/",
        "fields": {
            "supergroup_name": "Your base’s name:",
            "shard": "The shard it is located on:",
            "base_code": "The passcode for entry:",
            "category": "The category your base is entering under:"
        }
    }

]

# =========================================================
# HEADERS
# =========================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# =========================================================
# SHARD NORMALIZATION
# =========================================================

SHARD_ALIASES = {

    "torch": "Torchbearer",
    "torchbearer": "Torchbearer",

    "excel": "Excelsior",
    "excelsior": "Excelsior",

    "ever": "Everlasting",
    "everlasting": "Everlasting",

    "indo": "Indomitable",
    "indomitable": "Indomitable",

    "reunion": "Reunion",

    "victory": "Victory"
}

# =========================================================
# FIELD STOP LABELS
# =========================================================

STOP_LABELS = [

    "Contributing builders",
    "Any additional information",
    "Special or Hidden Features",
    "Is flight or teleportation useful",
    "Description",
    "Base Owner",
    "Base Builder",
    "Edited",
    "---"
]

# =========================================================
# SHARD DETECTION
# =========================================================

SHARD_PATTERNS = {

    "Torchbearer": [
        r"\btorch\b",
        r"\btorchbearer\b"
    ],

    "Excelsior": [
        r"\bexcel\b",
        r"\bexcelsior\b"
    ],

    "Everlasting": [
        r"\bever\b",
        r"\beverlasting\b"
    ],

    "Indomitable": [
        r"\bindo\b",
        r"\bindomitable\b"
    ],

    "Reunion": [
        r"\breunion\b"
    ],

    "Victory": [
        r"\bvictory\b"
    ]
}

# =========================================================
# HELPERS
# =========================================================

def clean(text):

    if not text:
        return ""

    text = text.replace("\u00a0", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_shard(shard):

    shard = clean(shard).lower()

    for alias, proper in SHARD_ALIASES.items():

        if shard.startswith(alias):
            return proper

    return shard.title()


def detect_shard_from_text(text):

    t = text.lower()

    for shard, patterns in SHARD_PATTERNS.items():

        for pattern in patterns:

            if re.search(pattern, t):
                return shard

    return None


def remove_forum_garbage(text):

    lines = []

    for line in text.splitlines():

        line = clean(line)

        if not line:
            continue

        if line.startswith("Posted"):
            continue

        if line.startswith("Edited"):
            continue

        if re.match(r"^January \d+", line):
            continue

        if line in ["(edited)"]:
            continue

        if "Give me money to draw your characters" in line:
            continue

        if "Visit one of the public RP spaces" in line:
            continue

        if "AE arc" in line:
            continue

        lines.append(line)

    return "\n".join(lines)


def split_base_blocks(text):

    pattern = re.compile(
        r"(Supergroup Name:|Your base’s name:)",
        re.IGNORECASE
    )

    matches = list(pattern.finditer(text))

    blocks = []

    for i, match in enumerate(matches):

        start = match.start()

        end = (
            matches[i + 1].start()
            if i + 1 < len(matches)
            else len(text)
        )

        block = text[start:end].strip()

        if block:
            blocks.append(block)

    return blocks


def extract_field(block, label, all_labels):

    start = block.lower().find(label.lower())

    if start == -1:
        return None

    start += len(label)

    next_positions = []

    for other in all_labels:

        if other == label:
            continue

        pos = block.lower().find(other.lower(), start)

        if pos != -1:
            next_positions.append(pos)

    for stop in STOP_LABELS:

        pos = block.lower().find(stop.lower(), start)

        if pos != -1:
            next_positions.append(pos)

    end = min(next_positions) if next_positions else len(block)

    value = block[start:end]

    value = clean(value)

    return value


def extract_fields(block, fields):

    labels = list(fields.values())

    data = {}

    for key, label in fields.items():

        value = extract_field(
            block,
            label,
            labels
        )

        if value:
            data[key] = value

    return data


def extract_description(block):

    labels = [
        "Description:",
        "Description :"
    ]

    for label in labels:

        pos = block.lower().find(label.lower())

        if pos != -1:

            desc = block[pos + len(label):]

            desc = re.split(
                r"Edited\s+January",
                desc
            )[0]

            return clean(desc)

    return None


def get_post_content(article):

    selectors = [
        ".ipsComment_content",
        ".cPost_contentWrap",
        ".ipsType_richText"
    ]

    for selector in selectors:

        el = article.select_one(selector)

        if el:

            text = el.get_text("\n", strip=True)

            if text:
                return remove_forum_garbage(text)

    return ""


def get_post_author(article):

    selectors = [
        ".cAuthorPane_author",
        ".ipsType_break"
    ]

    for selector in selectors:

        el = article.select_one(selector)

        if el:

            txt = clean(el.get_text())

            if txt:
                return txt

    return None


def get_post_date(article):

    time_el = article.select_one("time")

    if time_el:

        return (
            time_el.get("datetime")
            or clean(time_el.get_text())
        )

    return None


def get_page_number(url):

    m = re.search(r"page/(\d+)", url)

    if m:
        return int(m.group(1))

    return 1


def base_exists(code):

    params = {
        "base_code": f"eq.{code}",
        "select": "id"
    }

    r = requests.get(
        API_URL,
        headers=SUPABASE_HEADERS,
        params=params,
        timeout=30
    )

    if r.status_code != 200:
        return False

    try:
        return len(r.json()) > 0
    except:
        return False


def insert_base(payload):

    r = requests.post(
        API_URL,
        headers=SUPABASE_HEADERS,
        json=payload,
        timeout=30
    )

    print("INSERT STATUS:", r.status_code)

    if r.text:
        print(r.text[:300])

    return r.status_code in [200, 201]

# =========================================================
# SCRAPER
# =========================================================

def scrape_source(source):

    print("============================================================")
    print("SCRAPING")
    print(source["url"])
    print("============================================================")

    r = requests.get(
        source["url"],
        headers=HEADERS,
        timeout=60
    )

    soup = BeautifulSoup(r.text, "html.parser")

    articles = soup.select("article")

    print(f"FOUND {len(articles)} ARTICLES")

    inserted = 0

    for article in articles:

        raw_post = get_post_content(article)

        if not raw_post:
            continue

        blocks = split_base_blocks(raw_post)

        for block in blocks:

            parsed = extract_fields(
                block,
                source["fields"]
            )

            if not parsed:
                continue

            if "base_code" not in parsed:
                continue

            code_match = re.search(
                r"[A-Z0-9]+-\d+",
                parsed["base_code"],
                re.IGNORECASE
            )

            if not code_match:
                continue

            parsed["base_code"] = code_match.group(0).upper()

            parsed["shard"] = normalize_shard(
                parsed.get("shard", "")
            )

            if not parsed["shard"]:

                detected = detect_shard_from_text(block)

                if detected:
                    parsed["shard"] = detected

            category = parsed.get("category", "")

            for stop in STOP_LABELS:

                category = category.split(stop)[0]

            category = re.split(
                r"\b\d+\b",
                category
            )[0]

            category = clean(category)

            parsed["category"] = category

            parsed["supergroup_name"] = clean(
                parsed.get("supergroup_name")
            )

            description = extract_description(block)

            print("--------------------------------------------------")
            print("PARSED DATA:")
            print(parsed)

            if not parsed["shard"]:
                print("SKIPPED - NO SHARD")
                continue

            if base_exists(parsed["base_code"]):
                print("ALREADY EXISTS")
                continue

            payload = {

                "supergroup_name": parsed["supergroup_name"],

                "shard": parsed["shard"],

                "base_code": parsed["base_code"],

                "category": parsed["category"],

                "description": description,

                "raw_post": block,

                "source_topic": source["url"].split("/")[-2],

                "source_url": source["url"],

                "source_page": get_page_number(
                    source["url"]
                ),

                "post_author": get_post_author(article),

                "post_date": get_post_date(article)
            }

            print("----------------------------------------")
            print("BASE FOUND")
            print(payload["supergroup_name"])
            print(payload["shard"])
            print(payload["base_code"])
            print(payload["category"])

            ok = insert_base(payload)

            if ok:
                inserted += 1
                print("INSERTED")
            else:
                print("INSERT FAILED")

    return inserted

# =========================================================
# MAIN
# =========================================================

def main():

    print("============================================================")
    print("SUPABASE DEBUG")
    print("============================================================")
    print(f"API_URL = {API_URL}")
    print("============================================================")

    total = 0

    for source in SOURCES:

        total += scrape_source(source)

    print("============================================================")
    print("DONE")
    print(f"TOTAL UPSERTED: {total}")
    print("============================================================")


if __name__ == "__main__":
    main()
