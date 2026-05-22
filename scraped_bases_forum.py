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

if "/rest/v1" in SUPABASE_URL:
    REST_BASE_URL = SUPABASE_URL.split("/rest/v1")[0] + "/rest/v1"
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

# =========================================================
# SUPABASE HEADERS
# =========================================================

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# =========================================================
# HELPERS
# =========================================================

def clean(value):
    if not value:
        return ""
    return " ".join(value.strip().split())


def extract_field(text, label):

    pattern = rf"{re.escape(label)}\s*(.+?)(?=\n[A-Z][^\n:]+:|\Z)"

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    if not match:
        return ""

    return clean(match.group(1))


def is_valid_base_code(code):

    return bool(
        re.match(r"^[A-Z0-9]+-\d+$", code.upper())
    )

# =========================================================
# CHECK EXISTING
# =========================================================

def base_exists(base_code):

    url = f"{API_URL}?base_code=eq.{base_code}"

    response = requests.get(
        url,
        headers=SUPABASE_HEADERS,
        timeout=30
    )

    print("CHECK STATUS:", response.status_code)

    if response.status_code != 200:
        print("CHECK RESPONSE:", response.text)
        return False

    data = response.json()

    return len(data) > 0

# =========================================================
# INSERT
# =========================================================

def insert_base(payload):

    response = requests.post(
        API_URL,
        headers=SUPABASE_HEADERS,
        json=payload,
        timeout=30
    )

    print("INSERT STATUS:", response.status_code)

    if response.status_code >= 300:
        print("INSERT RESPONSE:", response.text)
        return False

    return True

# =========================================================
# PARSE POST
# =========================================================

def parse_post(text, fields):

    parsed = {}

    for key, label in fields.items():
        parsed[key] = extract_field(text, label)

    return parsed

# =========================================================
# SCRAPER
# =========================================================

def scrape_source(source):

    print("============================================================")
    print("SCRAPING")
    print(source["url"])
    print("============================================================")

    response = requests.get(
        source["url"],
        headers=HEADERS,
        timeout=60
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    selectors = [
        ".ipsComment_content",
        ".cPost_contentWrap",
        ".ipsType_richText",
        "article"
    ]

    raw_posts = []

    for selector in selectors:

        posts = soup.select(selector)

        print(f"FOUND {len(posts)} POSTS USING {selector}")

        for post in posts:

            text = clean(
                post.get_text("\n", strip=True)
            )

            if len(text) > 100:
                raw_posts.append(text)

    print(f"TOTAL RAW POSTS: {len(raw_posts)}")

    inserted = 0

    for text in raw_posts:

        parsed = parse_post(
            text,
            source["fields"]
        )

        if not parsed.get("supergroup_name"):
            continue

        if not parsed.get("shard"):
            continue

        if not parsed.get("base_code"):
            continue

        if not parsed.get("category"):
            continue

        parsed["base_code"] = parsed["base_code"].upper()

        if not is_valid_base_code(parsed["base_code"]):
            continue

        print("--------------------------------------------------")
        print("PARSED DATA:")
        print(parsed)

        print("----------------------------------------")
        print("BASE FOUND")
        print(parsed["supergroup_name"])
        print(parsed["shard"])
        print(parsed["base_code"])
        print(parsed["category"])

        if base_exists(parsed["base_code"]):
            print("ALREADY EXISTS")
            continue

        payload = {
            "supergroup_name": parsed["supergroup_name"],
            "shard": parsed["shard"],
            "base_code": parsed["base_code"],
            "category": parsed["category"]
        }

        success = insert_base(payload)

        if success:
            print("INSERTED")
            inserted += 1
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
    print("API_URL =", API_URL)
    print("============================================================")

    total = 0

    for source in SOURCES:
        total += scrape_source(source)

    print("============================================================")
    print("DONE")
    print(f"TOTAL UPSERTED: {total}")
    print("============================================================")

# =========================================================

if __name__ == "__main__":
    main()
