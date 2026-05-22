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

TABLE_NAME = "scraped_bases_forum"

NOW = datetime.now(timezone.utc).isoformat()

# =========================================================
# FIX REST URL
# =========================================================

if "/rest/v1" in SUPABASE_URL:
    REST_BASE_URL = SUPABASE_URL.split("/rest/v1")[0] + "/rest/v1"
else:
    REST_BASE_URL = SUPABASE_URL + "/rest/v1"

API_URL = f"{REST_BASE_URL}/{TABLE_NAME}"

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
# SERVER NORMALIZATION
# =========================================================

SERVER_MAP = {
    "torch": "Torchbearer",
    "torchbearer": "Torchbearer",

    "excel": "Excelsior",
    "excelsior": "Excelsior",

    "ever": "Everlasting",
    "everlasting": "Everlasting",

    "reunion": "Reunion",

    "indom": "Indomitable",
    "indomitable": "Indomitable",

    "victory": "Victory"
}

VALID_SERVERS = set(SERVER_MAP.values())

# =========================================================
# HEADERS
# =========================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================================================
# HELPERS
# =========================================================

def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

# =========================================================
# SERVER EXTRACTION
# =========================================================

def normalize_server(value):

    if not value:
        return None

    v = value.strip().lower()

    for k, final_name in SERVER_MAP.items():
        if v == k:
            return final_name

    for k, final_name in SERVER_MAP.items():
        if k in v:
            return final_name

    return None

# =========================================================
# CATEGORY CLEANUP
# =========================================================

def cleanup_category(value):

    if not value:
        return None

    value = value.strip()

    stop_markers = [
        "Contributing builders",
        "Any additional information",
        "Special or Hidden Features",
        "Is flight or teleportation",
        "Description",
        "Edited",
        "Posted"
    ]

    for marker in stop_markers:
        if marker in value:
            value = value.split(marker)[0].strip()

    value = value.replace("\n", " ").strip()

    value = re.sub(r"\s+", " ", value)

    value = re.sub(r"\b\d+\s*$", "", value).strip()

    mappings = {
        "Where does this fit? Clubs and Venues": "Clubs and Venues",
        "Fantasy /": "Fantasy",
        "Tech /": "Tech",
        "Sci/Tech,": "Sci/Tech",
        "Other /": "Other",
        "Misc?": "Misc",
        "Free form": "Freeform",
        "Floating Islands": "Floating Islands"
    }

    for k, v in mappings.items():
        if value.startswith(k):
            return v

    return value

# =========================================================
# BASE CODE CLEANUP
# =========================================================

def cleanup_base_code(value):

    if not value:
        return None

    m = re.search(r"\b[A-Z0-9\-]+-\d+\b", value, re.I)

    if m:
        return m.group(0).upper()

    return None

# =========================================================
# FIELD EXTRACTOR
# =========================================================

def extract_field(text, label):

    escaped = re.escape(label)

    pattern = rf"{escaped}\s*(.+?)(?=\n[A-Z][^\n]{{0,80}}:|\Z)"

    m = re.search(
        pattern,
        text,
        re.I | re.S
    )

    if not m:
        return None

    value = m.group(1).strip()

    value = re.sub(r"\s+", " ", value)

    return value.strip()

# =========================================================
# FALLBACK SERVER DETECTION
# =========================================================

def detect_server_anywhere(text):

    text_lower = text.lower()

    for key, final_name in SERVER_MAP.items():
        if key in text_lower:
            return final_name

    return None

# =========================================================
# DESCRIPTION
# =========================================================

def extract_description(text):

    patterns = [
        r"Description\s*:?\s*(.+?)(?:Edited|$)",
        r"Any additional information.*?:\s*(.+?)(?:Edited|$)"
    ]

    for pattern in patterns:

        m = re.search(
            pattern,
            text,
            re.I | re.S
        )

        if m:
            desc = m.group(1).strip()

            desc = re.sub(r"\s+", " ", desc)

            return desc[:5000]

    return None

# =========================================================
# DATE
# =========================================================

def extract_post_date(article):

    time_tag = article.find("time")

    if not time_tag:
        return None

    value = (
        time_tag.get("datetime")
        or time_tag.get("title")
        or time_tag.text
    )

    return value

# =========================================================
# AUTHOR
# =========================================================

def extract_author(article):

    selectors = [
        ".ipsType_break",
        ".ipsType_normal a",
        ".cAuthorPane_author"
    ]

    for sel in selectors:

        el = article.select_one(sel)

        if el:
            value = el.get_text(" ", strip=True)

            if value:
                return value

    return None

# =========================================================
# PAGE COUNT
# =========================================================

def detect_last_page(soup):

    pages = []

    for a in soup.select("a"):

        txt = a.get_text(strip=True)

        if txt.isdigit():
            pages.append(int(txt))

    if not pages:
        return 1

    return max(pages)

# =========================================================
# PARSER
# =========================================================

def parse_post(text, fields):

    data = {}

    for key, label in fields.items():

        value = extract_field(text, label)

        data[key] = value

    if data.get("base_code"):
        data["base_code"] = cleanup_base_code(
            data["base_code"]
        )

    if data.get("category"):
        data["category"] = cleanup_category(
            data["category"]
        )

    if data.get("shard"):
        data["shard"] = normalize_server(
            data["shard"]
        )

    if not data.get("shard"):
        data["shard"] = detect_server_anywhere(text)

    return data

# =========================================================
# EXIST CHECK
# =========================================================

def base_exists(code):

    url = f"{API_URL}?base_code=eq.{code}&select=id"

    r = requests.get(
        url,
        headers=supabase_headers(),
        timeout=30
    )

    if r.status_code != 200:
        return False

    rows = r.json()

    return len(rows) > 0

# =========================================================
# INSERT
# =========================================================

def insert_base(row):

    r = requests.post(
        API_URL,
        headers=supabase_headers(),
        json=row,
        timeout=60
    )

    print(f"INSERT STATUS: {r.status_code}")

    if r.text:
        print(f"INSERT RESPONSE: {r.text[:500]}")

    return r.status_code in [200, 201]

# =========================================================
# SCRAPE ONE PAGE
# =========================================================

def scrape_page(source, page):

    url = source["url"]

    if page > 1:
        url = f"{url}?page={page}"

    print("============================================================")
    print("SCRAPING")
    print(url)
    print("============================================================")

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=60
    )

    soup = BeautifulSoup(r.text, "html.parser")

    articles = soup.select("article")

    print(f"FOUND {len(articles)} ARTICLES")

    inserted = 0

    for article in articles:

        raw_post = article.get_text(
            "\n",
            strip=True
        )

        parsed = parse_post(
            raw_post,
            source["fields"]
        )

        if not parsed.get("supergroup_name"):
            continue

        if not parsed.get("base_code"):
            continue

        if not parsed.get("category"):
            continue

        if not parsed.get("shard"):
            continue

        print("--------------------------------------------------")
        print("PARSED DATA:")
        print(parsed)

        if base_exists(parsed["base_code"]):
            print("ALREADY EXISTS")
            continue

        topic_slug = source["url"].rstrip("/").split("/")[-1]

        row = {
            "source_topic": topic_slug,
            "source_url": source["url"],
            "source_page": page,
            "post_author": extract_author(article),
            "post_date": extract_post_date(article),

            "supergroup_name": parsed["supergroup_name"],
            "shard": parsed["shard"],
            "base_code": parsed["base_code"],
            "category": parsed["category"],

            "description": extract_description(raw_post),

            "raw_post": raw_post,

            "scraped_at": NOW
        }

        print("----------------------------------------")
        print("BASE FOUND")
        print(row["supergroup_name"])
        print(row["shard"])
        print(row["base_code"])
        print(row["category"])

        ok = insert_base(row)

        if ok:
            inserted += 1
            print("INSERTED")
        else:
            print("INSERT FAILED")

    return inserted

# =========================================================
# SCRAPE SOURCE
# =========================================================

def scrape_source(source):

    first_page = requests.get(
        source["url"],
        headers=HEADERS,
        timeout=60
    )

    soup = BeautifulSoup(
        first_page.text,
        "html.parser"
    )

    last_page = detect_last_page(soup)

    print("============================================================")
    print(f"DETECTED {last_page} PAGES")
    print("============================================================")

    total = 0

    for page in range(1, last_page + 1):

        try:
            total += scrape_page(
                source,
                page
            )

        except Exception as e:

            print("PAGE ERROR")
            print(page)
            print(str(e))

    return total

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

        try:

            total += scrape_source(source)

        except Exception as e:

            print("SOURCE ERROR")
            print(str(e))

    print("============================================================")
    print("DONE")
    print(f"TOTAL UPSERTED: {total}")
    print("============================================================")

# =========================================================

if __name__ == "__main__":
    main()
