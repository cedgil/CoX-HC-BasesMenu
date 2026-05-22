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

TABLE_NAME = "scraped_bases_forum"

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
# HELPERS
# =========================================================

def normalize_text(text):

    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = text.replace("\r", "\n")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_field(text, label):

    chunks = re.split(r"[\n\r]+| {2,}", text)

    for chunk in chunks:

        chunk = chunk.strip()

        if label.lower() in chunk.lower():

            idx = chunk.lower().find(label.lower())

            value = chunk[idx + len(label):].strip()

            if value:
                return normalize_text(value)

    # fallback ultra permissif
    pattern = re.escape(label) + r"\s*(.*?)(?:$|\n)"

    match = re.search(
        pattern,
        text,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        return normalize_text(match.group(1))

    return ""


def base_exists(base_code):

    url = f"{API_URL}?base_code=eq.{base_code}&select=id"

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


def insert_base(data):

    response = requests.post(
        API_URL,
        headers=SUPABASE_HEADERS,
        json=data,
        timeout=30
    )

    print("UPSERT STATUS:", response.status_code)

    if response.text:
        print("UPSERT RESPONSE:", response.text[:1000])

    return response.status_code in [200, 201]


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

    soup = BeautifulSoup(response.text, "html.parser")

    selectors = [
        ".ipsComment_content",
        ".cPost_contentWrap",
        ".ipsType_richText",
        "article"
    ]

    raw_posts = []

    for selector in selectors:

        found = soup.select(selector)

        print(f"FOUND {len(found)} POSTS USING {selector}")

        raw_posts.extend(found)

    print(f"TOTAL RAW POSTS: {len(raw_posts)}")

    inserted = 0

    for post in raw_posts:

        text = normalize_text(post.get_text(" ", strip=True))

        if len(text) < 50:
            continue

        data = {}

        for field_name, label in source["fields"].items():

            data[field_name] = extract_field(
                text,
                label
            )

        if not all([
            data.get("supergroup_name"),
            data.get("shard"),
            data.get("base_code"),
            data.get("category")
        ]):

            print("FAILED PARSE")
            print(text[:1000])
            print("--------------------------------")
            print(data)
            print("================================")

            continue

        data["source_url"] = source["url"]

        print("--------------------------------------------------")
        print("PARSED DATA:")
        print(data)

        if base_exists(data["base_code"]):

            print("ALREADY EXISTS")
            continue

        print("----------------------------------------")
        print("BASE FOUND")
        print(data["supergroup_name"])
        print(data["shard"])
        print(data["base_code"])
        print(data["category"])

        success = insert_base(data)

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


if __name__ == "__main__":
    main()
