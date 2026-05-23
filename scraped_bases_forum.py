#!/usr/bin/env python3

import os
import re
import requests

from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# =========================================================
# CONFIG
# =========================================================

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

SUPABASE_TABLE = "scraped_bases_forum"

NOW = datetime.now(timezone.utc)

# =========================================================
# SOURCES
# =========================================================

SOURCES = [

    {
        "url": "https://forums.homecomingservers.com/topic/62785-list-your-base-for-the-noncompetitive-our-based-showcase/",
        "event_name": "Noncompetitive Base Showcase",
        "event_type": "showcase",
        "fields": {
            "supergroup_name": "Supergroup Name:",
            "shard": "Shard/Server:",
            "base_code": "Base Code:",
            "category": "Category to list base in:"
        }
    },

    {
        "url": "https://forums.homecomingservers.com/topic/56486-2025-homecoming-base-contest-rules-entries-thread/",
        "event_name": "2025 Base Contest",
        "event_type": "contest",
        "fields": {
            "supergroup_name": "Your base’s name:",
            "shard": "The shard it is located on:",
            "base_code": "The passcode for entry:",
            "category": "The category your base is entering under:"
        }
    },

    {
        "url": "https://forums.homecomingservers.com/topic/57844-community-challenge-contest-pride-through-the-ages/",
        "event_name": "2025 Pride through the age",
        "event_type": "contest",
        "fields": {
            "supergroup_name": "Base or SG Name:",
            "shard": "Shard:",
            "base_code": "Passcode:"
        }
    },

    {
        "url": "https://forums.homecomingservers.com/topic/39881-2023-homecoming-base-contest-rules-entries-thread/",
        "event_name": "2023 Base Contest",
        "event_type": "contest",
        "fields": {
            "supergroup_name": "Base or SG Name:",
            "shard": "Shard:",
            "base_code": "Passcode:",
            "category": "Category for Contest:"
        }
    }

]

# =========================================================
# VALID SHARDS
# =========================================================

VALID_SHARDS = {
    "Excelsior",
    "Torchbearer",
    "Everlasting",
    "Indomitable",
    "Reunion",
    "Victory"
}

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

# =========================================================
# SUPABASE
# =========================================================

if "/rest/v1/" in SUPABASE_URL:
    REST_BASE_URL = SUPABASE_URL.split("/rest/v1")[0] + "/rest/v1"

elif SUPABASE_URL.endswith("/rest/v1"):
    REST_BASE_URL = SUPABASE_URL

else:
    REST_BASE_URL = SUPABASE_URL + "/rest/v1"

API_URL = f"{REST_BASE_URL}/{SUPABASE_TABLE}"

# =========================================================
# HELPERS
# =========================================================

def headers():

    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def clean(text):

    if not text:
        return ""

    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()

def clean_multiline(text):

    if not text:
        return ""

    text = text.replace("\u00a0", " ")
    text = text.replace("\r", "\n")

    lines = []

    for line in text.split("\n"):

        line = line.strip()

        if line:
            lines.append(line)

    return "\n".join(lines).strip()

def normalize_server(value):

    if not value:
        return None

    value = clean(value).lower()

    for key, normalized in SERVER_MAP.items():

        if value == key:
            return normalized

    for key, normalized in SERVER_MAP.items():

        if key in value:
            return normalized

    return value.title()

def sanitize_category(category):

    if not category:
        return None

    category = clean(category)

    if category.lower().startswith("where does this fit?"):
        category = category.split("?")[-1].strip()

    category = category.replace("Sci/Tech", "Tech Sci-Fi")
    category = category.replace("Sci-Fi", "Tech Sci-Fi")
    category = category.replace("Clubs and Venues", "Clubs and Venues")

    STOP_WORDS = [
        "Other associated",
        "Contributing builders",
        "Additional Info",
        "Special or Hidden Features",
        "Description",
        "Edited",
        "Posted"
    ]

    for stop in STOP_WORDS:

        idx = category.find(stop)

        if idx > 0:
            category = category[:idx].strip()

    return clean(category)

def extract_field(raw_text, label):

    pattern = (
        re.escape(label)
        + r"\s*(.*?)"
        + r"(?=\n[A-Z][^\n]{1,80}:|\Z)"
    )

    match = re.search(
        pattern,
        raw_text,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return None

    value = clean(match.group(1))

    value = value.split("\n")[0].strip()

    return value

def extract_description(raw_text):

    match = re.search(
        r"Description\s*:?\s*(.*?)(?=Edited|$)",
        raw_text,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return None

    return clean(match.group(1))

def get_total_pages(soup):

    links = soup.select("a[href*='page=']")

    max_page = 1

    for link in links:

        href = link.get("href", "")

        m = re.search(r"page=(\d+)", href)

        if m:
            max_page = max(max_page, int(m.group(1)))

    return max_page

def get_page_url(base_url, page):

    if page <= 1:
        return base_url

    separator = "&" if "?" in base_url else "?"

    return f"{base_url}{separator}page={page}"

# =========================================================
# SUPABASE
# =========================================================

def upsert_base(data):

    payload = {
        **data,
        "scraped_at": NOW.isoformat()
    }

    r = requests.post(
        API_URL,
        headers={
            **headers(),
            "Prefer": "resolution=merge-duplicates"
        },
        params={
            "on_conflict": "base_code"
        },
        json=payload,
        timeout=60
    )

    print(f"UPSERT STATUS: {r.status_code}")

    if r.status_code >= 400:
        print(r.text)
        return False

    return True

def purge_old_bases():

    threshold = (
        NOW - timedelta(days=30)
    ).isoformat()

    requests.delete(
        API_URL,
        headers=headers(),
        params={
            "scraped_at": f"lt.{threshold}"
        },
        timeout=60
    )

# =========================================================
# SCRAPER
# =========================================================

TOTAL_UPSERTED = 0

def scrape_source(source):

    global TOTAL_UPSERTED

    topic_url = source["url"]

    print("SCRAPING", topic_url)

    r = requests.get(
        topic_url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=60
    )

    soup = BeautifulSoup(r.text, "html.parser")

    total_pages = get_total_pages(soup)

    for page in range(1, total_pages + 1):

        page_url = get_page_url(topic_url, page)

        r = requests.get(
            page_url,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=60
        )

        soup = BeautifulSoup(r.text, "html.parser")

        articles = soup.select("article")

        for article in articles:

            raw_post = clean_multiline(
                article.get_text("\n", strip=True)
            )

            parsed = {}

            for key, label in source["fields"].items():

                parsed[key] = extract_field(
                    raw_post,
                    label
                )

            parsed["shard"] = normalize_server(
                parsed.get("shard")
            )

            parsed["category"] = sanitize_category(
                parsed.get("category")
            )

            if (
                source["event_type"] == "contest"
                and not parsed.get("category")
            ):
                parsed["category"] = "Thematic Contest"

            parsed["description"] = extract_description(raw_post)

            parsed["source_url"] = page_url
            parsed["source_page"] = page
            parsed["source_topic"] = (
                topic_url
                .split("/topic/")[1]
                .split("/")[0]
            )

            parsed["event_name"] = source["event_name"]
            parsed["event_type"] = source["event_type"]

            parsed["raw_post"] = raw_post

            # =====================================================
            # TEMPLATE FILTERS
            # =====================================================

            if parsed.get("supergroup_name") in [
                "Supergroup Name:",
                "Base or SG Name:",
                "Your base’s name:"
            ]:
                continue

            if parsed.get("shard") not in VALID_SHARDS:
                continue

            if not parsed.get("base_code"):
                continue

            parsed["base_code"] = clean(
                parsed["base_code"]
            )

            if not re.match(
                r"^[A-Z0-9]+-[0-9]+$",
                parsed["base_code"],
                re.IGNORECASE
            ):
                continue

            print("PARSED DATA:")
            print(parsed)

            inserted = upsert_base(parsed)

            if inserted:
                TOTAL_UPSERTED += 1

# =========================================================
# MAIN
# =========================================================

def main():

    for source in SOURCES:
        scrape_source(source)

    purge_old_bases()

    print("DONE")
    print(TOTAL_UPSERTED)

if __name__ == "__main__":
    main()
