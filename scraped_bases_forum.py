#!/usr/bin/env python3

import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

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
    return re.sub(r"\s+", " ", text).strip()


def extract_field(text, label):

    pattern = rf"{re.escape(label)}\s*(.+?)(?=\s+[A-Z][^:\n]+:|$)"

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    if not match:
        return None

    value = clean(match.group(1))

    value = re.split(
        r"(Contributing builders|Any additional information|Special or Hidden Features|Is flight or teleportation useful|Again, please list the TOUR hub)",
        value,
        flags=re.IGNORECASE
    )[0].strip()

    return value


def parse_post(text, fields):

    data = {}

    for key, label in fields.items():
        value = extract_field(text, label)

        if value:
            data[key] = value

    return data


def get_post_date(article):

    selectors = [
        "time",
        ".ipsType_light",
        ".cAuthorPane_info"
    ]

    for selector in selectors:

        el = article.select_one(selector)

        if not el:
            continue

        value = (
            el.get("datetime")
            or el.get_text(" ", strip=True)
        )

        if value:
            return clean(value)

    return None


def get_post_author(article):

    selectors = [
        ".cAuthorPane_author a",
        ".ipsType_break",
        ".ipsType_normal a"
    ]

    for selector in selectors:

        el = article.select_one(selector)

        if not el:
            continue

        text = el.get_text(" ", strip=True)

        if text:
            return clean(text)

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
            return clean(
                el.get_text("\n", strip=True)
            )

    return ""


# =========================================================
# SUPABASE
# =========================================================

def base_exists(base_code):

    url = API_URL

    params = {
        "base_code": f"eq.{base_code}",
        "select": "id"
    }

    r = requests.get(
        url,
        headers=SUPABASE_HEADERS,
        params=params,
        timeout=30
    )

    return r.status_code == 200 and len(r.json()) > 0


def insert_base(data):

    r = requests.post(
        API_URL,
        headers=SUPABASE_HEADERS,
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

        parsed = parse_post(
            raw_post,
            source["fields"]
        )

        if (
            "supergroup_name" not in parsed
            or "shard" not in parsed
            or "base_code" not in parsed
            or "category" not in parsed
        ):
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

            "description": raw_post[:5000],
            "raw_post": raw_post,

            "created_at": datetime.utcnow().isoformat()
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
