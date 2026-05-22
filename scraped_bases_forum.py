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
# HELPERS
# =========================================================

def clean(text):

    if not text:
        return ""

    text = text.replace("\u00a0", " ")

    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text):

    text = text.replace("\r", "\n")
    text = re.sub(r"\n+", "\n", text)

    return text


def extract_between(text, start_label, all_labels):

    start = text.lower().find(start_label.lower())

    if start == -1:
        return None

    start += len(start_label)

    next_positions = []

    for label in all_labels:

        if label == start_label:
            continue

        pos = text.lower().find(label.lower(), start)

        if pos != -1:
            next_positions.append(pos)

    end = min(next_positions) if next_positions else len(text)

    value = text[start:end]

    value = clean(value)

    return value if value else None


def extract_fields(raw_text, fields):

    data = {}

    labels = list(fields.values())

    for key, label in fields.items():

        value = extract_between(
            raw_text,
            label,
            labels
        )

        if value:
            data[key] = value

    return data


def is_valid_entry(data):

    required = [
        "supergroup_name",
        "shard",
        "base_code",
        "category"
    ]

    for field in required:

        if field not in data:
            return False

        value = data[field].strip()

        if len(value) < 2:
            return False

    if data["supergroup_name"] in [
        "Shard/Server:",
        "Your",
        "The"
    ]:
        return False

    if data["base_code"] in [
        "Base",
        "Code",
        "The"
    ]:
        return False

    if not re.search(r"-\d+", data["base_code"]):
        return False

    return True


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
                return normalize_text(text)

    return ""


def get_post_author(article):

    selectors = [
        ".cAuthorPane_author",
        ".ipsType_break"
    ]

    for selector in selectors:

        el = article.select_one(selector)

        if el:

            text = clean(el.get_text())

            if text:
                return text

    return None


def get_post_date(article):

    time_el = article.select_one("time")

    if time_el:

        return (
            time_el.get("datetime")
            or clean(time_el.get_text())
        )

    return None


def base_exists(base_code):

    params = {
        "base_code": f"eq.{base_code}",
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
        print(r.text[:500])

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

        parsed = extract_fields(
            raw_post,
            source["fields"]
        )

        if not is_valid_entry(parsed):
            continue

        print("--------------------------------------------------")
        print("PARSED DATA:")
        print(parsed)

        if base_exists(parsed["base_code"]):
            print("ALREADY EXISTS")
            continue

        payload = {

            "supergroup_name": parsed["supergroup_name"],

            "shard": parsed["shard"],

            "base_code": parsed["base_code"],

            "category": parsed["category"],

            "source_topic": source["url"].split("/")[-2],

            "source_url": source["url"],

            "source_page": 1,

            "post_author": get_post_author(article),

            "post_date": get_post_date(article),

            "description": raw_post[:4000],

            "raw_post": raw_post

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


# =========================================================

if __name__ == "__main__":
    main()
