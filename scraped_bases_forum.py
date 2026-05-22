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

HEADERS = {
    "User-Agent": "HC-Base-Scraper/5.0"
}

NOW = datetime.now(timezone.utc).isoformat()

MAX_PAGES = 10

# =========================================================
# FIX SUPABASE URL
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
# SERVERS
# =========================================================

SERVER_ALIASES = {
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

VALID_SERVERS = [
    "Torchbearer",
    "Excelsior",
    "Everlasting",
    "Reunion",
    "Indomitable",
    "Victory"
]

# =========================================================
# HELPERS
# =========================================================

def clean(text):

    if not text:
        return ""

    text = text.replace("\xa0", " ")

    return re.sub(r"\s+", " ", text).strip()


def normalize_server(server):

    server = clean(server).lower()

    for key, value in SERVER_ALIASES.items():

        if key == server:
            return value

    return server.title()


def extract_topic_slug(url):

    m = re.search(r"/topic/\d+-([^/]+)/?", url)

    if m:
        return m.group(1)

    return "unknown-topic"


def extract_page(url):

    m = re.search(r"[?&]page=(\d+)", url)

    if m:
        return int(m.group(1))

    return 1


def extract_author(article):

    selectors = [
        ".ipsType_break",
        ".cAuthorPane_author strong",
        ".ipsType_sectionHead a"
    ]

    for sel in selectors:

        el = article.select_one(sel)

        if el:

            txt = clean(el.get_text())

            if txt:
                return txt

    return None


def extract_post_date(article):

    time_el = article.select_one("time")

    if not time_el:
        return None

    value = (
        time_el.get("datetime")
        or time_el.get("title")
        or clean(time_el.get_text())
    )

    return value


def normalize_category(cat):

    cat = clean(cat)

    cat = re.split(
        r"(Contributing builders|Any additional information|Edited)",
        cat,
        flags=re.I
    )[0]

    cat = re.split(
        r"(Special or Hidden Features|Is flight or teleportation useful)",
        cat,
        flags=re.I
    )[0]

    cat = cat.strip()

    mappings = {
        "clubs and venues": "Clubs and Venues",
        "clubs & venues": "Clubs and Venues",
        "free form": "Freeform",
        "freeform": "Freeform",
        "misc/other": "Misc",
        "misc": "Misc",
        "novice": "Novice",
        "realism": "Realism",
        "fantasy": "Fantasy",
        "sci/tech": "Sci/Tech",
        "sci-tech": "Sci/Tech"
    }

    low = cat.lower()

    for k, v in mappings.items():

        if low.startswith(k):
            return v

    return cat


def extract_server_from_text(text):

    low = text.lower()

    for alias, real in SERVER_ALIASES.items():

        if alias in low:
            return real

    return ""


# =========================================================
# FIELD EXTRACTION
# =========================================================

def extract_field(text, label):

    pattern = rf"{re.escape(label)}\s*(.+?)(?=\n[A-Z][^:\n]+:|\Z)"

    m = re.search(
        pattern,
        text,
        flags=re.I | re.S
    )

    if not m:
        return ""

    value = clean(m.group(1))

    value = re.split(
        r"(Edited\s+[A-Z][a-z]+|\d+\s*$)",
        value,
        flags=re.I
    )[0]

    return clean(value)


def extract_base_code(value):

    m = re.search(
        r"\b[A-Z0-9]{2,}-\d+\b",
        value,
        flags=re.I
    )

    if m:
        return m.group(0).upper()

    return ""


# =========================================================
# PARSER
# =========================================================

def parse_article(article, source, source_url):

    text = article.get_text("\n", strip=True)

    text = clean(text)

    fields = source["fields"]

    supergroup_name = extract_field(
        text,
        fields["supergroup_name"]
    )

    shard = extract_field(
        text,
        fields["shard"]
    )

    base_code = extract_field(
        text,
        fields["base_code"]
    )

    category = extract_field(
        text,
        fields["category"]
    )

    if not shard:
        shard = extract_server_from_text(text)

    shard = normalize_server(shard)

    base_code = extract_base_code(base_code)

    category = normalize_category(category)

    if shard not in VALID_SERVERS:
        return None

    if not supergroup_name:
        return None

    if not base_code:
        return None

    data = {
        "source_topic": extract_topic_slug(source_url),
        "source_url": source_url,
        "source_page": extract_page(source_url),
        "post_author": extract_author(article),
        "post_date": extract_post_date(article),
        "supergroup_name": supergroup_name,
        "shard": shard,
        "base_code": base_code,
        "category": category,
        "description": None,
        "raw_post": text,
        "scraped_at": NOW
    }

    print("--------------------------------------------------")
    print("PARSED DATA:")
    print(data)

    return data

# =========================================================
# SUPABASE
# =========================================================

def supabase_headers():

    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }


def insert_base(data):

    r = requests.post(
        API_URL,
        headers=supabase_headers(),
        json=data,
        timeout=60
    )

    print("INSERT STATUS:", r.status_code)

    if r.text:
        print("INSERT RESPONSE:", r.text[:500])

    return r.status_code in [200, 201]


# =========================================================
# SCRAPER
# =========================================================

def scrape_topic(source):

    base_url = source["url"]

    visited_pages = set()

    all_entries = []

    page = 1

    while True:

        if page > MAX_PAGES:
            print("MAX PAGES REACHED")
            break

        if page == 1:
            url = base_url
        else:
            url = f"{base_url}?page={page}"

        if url in visited_pages:
            break

        visited_pages.add(url)

        print("============================================================")
        print("SCRAPING")
        print(url)
        print("============================================================")

        try:

            resp = requests.get(
                url,
                headers=HEADERS,
                timeout=30
            )

            if resp.status_code != 200:
                break

            soup = BeautifulSoup(resp.text, "html.parser")

            articles = soup.select("article")

            print(f"FOUND {len(articles)} ARTICLES")

            if not articles:
                break

            valid_count = 0

            for article in articles:

                parsed = parse_article(
                    article,
                    source,
                    url
                )

                if not parsed:
                    continue

                valid_count += 1

                ok = insert_base(parsed)

                if ok:
                    all_entries.append(parsed)

            print(f"VALID ENTRIES: {valid_count}")

            if valid_count == 0:
                break

            next_link = soup.select_one(
                'a[rel="next"]'
            )

            if not next_link:
                print("NO NEXT PAGE")
                break

            page += 1

        except Exception as e:

            print("SCRAPE ERROR")
            print(e)
            break

    return all_entries

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

        entries = scrape_topic(source)

        total += len(entries)

    print("============================================================")
    print("DONE")
    print(f"TOTAL UPSERTED: {total}")
    print("============================================================")


if __name__ == "__main__":
    main()
