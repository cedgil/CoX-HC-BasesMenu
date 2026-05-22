#!/usr/bin/env python3

import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# =========================================================
# CONFIG
# =========================================================

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

SUPABASE_TABLE = "scraped_bases_forum"

NOW = datetime.now(timezone.utc).isoformat()

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
    },

    {
        "url": "https://forums.homecomingservers.com/topic/39881-2023-homecoming-base-contest-rules-entries-thread/",
        "fields": {
            "supergroup_name": "Base or SG Name:",
            "shard": "Shard:",
            "base_code": "Passcode:",
            "category": "Category for Contest:"
        }
    }

]

# =========================================================
# SUPABASE URL FIX
# =========================================================

if "/rest/v1/" in SUPABASE_URL:
    REST_BASE_URL = SUPABASE_URL.split("/rest/v1")[0] + "/rest/v1"

elif SUPABASE_URL.endswith("/rest/v1"):
    REST_BASE_URL = SUPABASE_URL

else:
    REST_BASE_URL = SUPABASE_URL + "/rest/v1"

API_URL = f"{REST_BASE_URL}/{SUPABASE_TABLE}"

# =========================================================
# SHARDS
# =========================================================

SHARD_MAP = {
    "torch": "Torchbearer",
    "torchbearer": "Torchbearer",

    "excel": "Excelsior",
    "excelsior": "Excelsior",

    "ever": "Everlasting",
    "everlasting": "Everlasting",

    "reunion": "Reunion",

    "indo": "Indomitable",
    "indomitable": "Indomitable",

    "victory": "Victory"
}

VALID_SHARDS = {
    "Torchbearer",
    "Excelsior",
    "Everlasting",
    "Reunion",
    "Indomitable",
    "Victory"
}

# =========================================================
# HEADERS
# =========================================================

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# =========================================================
# HELPERS
# =========================================================

def clean(text):
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def normalize_shard(value):

    if not value:
        return None

    value = clean(value).lower()

    for key, normalized in SHARD_MAP.items():
        if value == key:
            return normalized

    for key, normalized in SHARD_MAP.items():
        if key in value:
            return normalized

    return None


def extract_passcode(text):

    if not text:
        return None

    m = re.search(
        r"\b[A-Z0-9]{2,}-\d+\b",
        text,
        re.I
    )

    if not m:
        return None

    return m.group(0).upper()


def extract_single_value(text):

    if not text:
        return None

    text = clean(text)

    text = text.split("\n")[0]

    text = re.split(
        r"(Contributing builders|Any additional information|Special or Hidden Features|Is flight|Description|Edited)",
        text,
        flags=re.I
    )[0]

    text = re.sub(r"\s{2,}", " ", text)

    return text.strip(" :-")


def extract_field(raw_text, label):

    escaped = re.escape(label)

    pattern = rf"""
        {escaped}
        \s*
        (.*?)
        (?=
            \n[A-Z][^\n]{{1,80}}:
            |
            Edited
            |
            Posted
            |
            $
        )
    """

    m = re.search(
        pattern,
        raw_text,
        re.I | re.S | re.X
    )

    if not m:
        return None

    return clean(m.group(1))


def infer_shard_from_text(text):

    lowered = text.lower()

    for key, shard in SHARD_MAP.items():
        if key in lowered:
            return shard

    return None


def extract_description(raw_text):

    m = re.search(
        r"Description\s*:?\s*(.*?)(?=Edited|$)",
        raw_text,
        re.I | re.S
    )

    if not m:
        return None

    return clean(m.group(1))


def extract_post_date(article):

    time_tag = article.select_one("time")

    if not time_tag:
        return None

    dt = (
        time_tag.get("datetime")
        or time_tag.get("title")
    )

    return dt


def extract_author(article):

    selectors = [
        ".ipsType_break",
        ".ipsType_normal a",
        ".cAuthorPane_author"
    ]

    for selector in selectors:

        el = article.select_one(selector)

        if el:
            txt = clean(el.get_text())

            if txt:
                return txt

    return None


def get_page_number(url):

    m = re.search(r"/page/(\d+)", url)

    if m:
        return int(m.group(1))

    return 1


# =========================================================
# PARSE POST
# =========================================================

def parse_post(raw_text, fields):

    data = {}

    for key, label in fields.items():

        value = extract_field(raw_text, label)

        if not value:
            continue

        if key == "base_code":
            value = extract_passcode(value)

        elif key == "category":
            value = extract_single_value(value)

        elif key == "supergroup_name":
            value = extract_single_value(value)

        elif key == "shard":
            value = normalize_shard(value)

        data[key] = value

    if not data.get("shard"):
        inferred = infer_shard_from_text(raw_text)

        if inferred:
            data["shard"] = inferred

    return data


# =========================================================
# DB
# =========================================================

def base_exists(code):

    url = f"{API_URL}?base_code=eq.{code}&select=id"

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    if r.status_code != 200:
        return False

    try:
        data = r.json()
        return len(data) > 0
    except:
        return False


def insert_base(data):

    r = requests.post(
        API_URL,
        headers=HEADERS,
        json=data,
        timeout=30
    )

    print("INSERT STATUS:", r.status_code)

    if r.text:
        print("INSERT RESPONSE:", r.text[:500])

    return r.status_code in [200, 201]


# =========================================================
# SCRAPER
# =========================================================

def scrape_source(source):

    url = source["url"]
    fields = source["fields"]

    print("=" * 60)
    print("SCRAPING")
    print(url)
    print("=" * 60)

    r = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=30
    )

    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    articles = soup.select("article")

    print(f"FOUND {len(articles)} ARTICLES")

    inserted = 0

    for idx, article in enumerate(articles, start=1):

        raw_text = clean(article.get_text("\n"))

        parsed = parse_post(raw_text, fields)

        if not parsed.get("supergroup_name"):
            continue

        if not parsed.get("shard"):
            continue

        if parsed["shard"] not in VALID_SHARDS:
            continue

        if not parsed.get("base_code"):
            continue

        if not parsed.get("category"):
            continue

        print("-" * 50)
        print("PARSED DATA:")
        print(parsed)

        if base_exists(parsed["base_code"]):
            print("ALREADY EXISTS")
            continue

        topic_slug = url.rstrip("/").split("/")[-1]

        payload = {
            "source_topic": topic_slug,
            "source_url": url,
            "source_page": get_page_number(url),
            "post_author": extract_author(article),
            "post_date": extract_post_date(article),

            "supergroup_name": parsed["supergroup_name"],
            "shard": parsed["shard"],
            "base_code": parsed["base_code"],
            "category": parsed["category"],

            "description": extract_description(raw_text),
            "raw_post": raw_text,

            "scraped_at": NOW
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

    print("=" * 60)
    print("SUPABASE DEBUG")
    print("=" * 60)
    print(f"API_URL = {API_URL}")
    print("=" * 60)

    total = 0

    for source in SOURCES:

        total += scrape_source(source)

    print("=" * 60)
    print("DONE")
    print(f"TOTAL UPSERTED: {total}")
    print("=" * 60)


# =========================================================

if __name__ == "__main__":
    main()
