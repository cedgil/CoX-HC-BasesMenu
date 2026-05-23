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
# SERVERS
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

# =========================================================
# CATEGORY NORMALIZATION
# =========================================================

CATEGORY_MAP = {

    "rp base under 7k": "RP Base Under 7K",
    "free form": "Freeform",
    "freeform": "Freeform",
    "realism": "Realism",
    "fantasy": "Fantasy",
    "tech": "Tech",
    "novice": "Novice",
    "clubs and venues": "Clubs and Venues"
}

# =========================================================
# SUPABASE
# =========================================================

if "/rest/v1/" in SUPABASE_URL:

    REST_BASE_URL = (
        SUPABASE_URL.split("/rest/v1")[0]
        + "/rest/v1"
    )

elif SUPABASE_URL.endswith("/rest/v1"):

    REST_BASE_URL = SUPABASE_URL

else:

    REST_BASE_URL = SUPABASE_URL + "/rest/v1"

API_URL = f"{REST_BASE_URL}/{SUPABASE_TABLE}"

print("============================================================")
print("SUPABASE DEBUG")
print("============================================================")
print(f"SUPABASE_URL = {SUPABASE_URL}")
print(f"REST_BASE_URL = {REST_BASE_URL}")
print(f"API_URL = {API_URL}")
print("============================================================")

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


def extract_server_from_text(text):

    lower = text.lower()

    for key, normalized in SERVER_MAP.items():

        if f"all on {key}" in lower:
            return normalized

        if f"on {key}" in lower:
            return normalized

    return None


def sanitize_category(category):

    if not category:
        return None

    category = clean(category)

    STOP_WORDS = [

        "Contributing builders",
        "Other associated contributors",
        "Other associated contributor",
        "Additional Info",
        "Any additional information",
        "Special or Hidden Features",
        "Is flight or teleportation",
        "Description",
        "Edited",
        "Posted"
    ]

    for stop in STOP_WORDS:

        idx = category.find(stop)

        if idx > 0:
            category = category[:idx].strip()

    category = re.sub(r"\s+\d+$", "", category)

    category = category.replace(" 1", "")
    category = category.replace(" 2", "")
    category = category.replace(" 3", "")

    category = category.replace("Fantasy /", "Fantasy")
    category = category.replace("Tech /", "Tech")
    category = category.replace("Other /", "Other")

    if category.lower().startswith("where does this fit?"):

        category = (
            category.split("?")[-1]
            .strip()
        )

    lower = category.lower().strip()

    if lower in CATEGORY_MAP:
        category = CATEGORY_MAP[lower]

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

    desc = clean(match.group(1))

    if not desc:
        return None

    return desc


def extract_post_date(article):

    time_el = article.select_one("time")

    if not time_el:
        return None

    value = (
        time_el.get("datetime")
        or time_el.get("title")
    )

    if not value:
        return None

    return value


def extract_author(article):

    candidates = [

        ".ipsType_break",
        ".cAuthorPane_author",
        ".ipsComment_author"
    ]

    for selector in candidates:

        el = article.select_one(selector)

        if el:

            value = clean(
                el.get_text(" ", strip=True)
            )

            if value:
                return value

    return None


def get_total_pages(soup):

    links = soup.select("a[href*='page=']")

    max_page = 1

    for link in links:

        href = link.get("href", "")

        m = re.search(r"page=(\d+)", href)

        if m:

            page = int(m.group(1))

            if page > max_page:
                max_page = page

    return min(max_page, 25)


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

        "source_topic": data["source_topic"],
        "source_url": data["source_url"],
        "source_page": data["source_page"],
        "post_author": data["post_author"],
        "post_date": data["post_date"],

        "supergroup_name": data["supergroup_name"],
        "shard": data["shard"],
        "base_code": data["base_code"],
        "category": data["category"],

        "description": data["description"],
        "raw_post": data["raw_post"],

        "event_name": data["event_name"],
        "event_type": data["event_type"],

        "scraped_at": NOW.isoformat(),
        "last_seen_at": NOW.isoformat()
    }

    url = API_URL + "?on_conflict=base_code"

    r = requests.post(
        url,
        headers=headers(),
        json=payload,
        timeout=60
    )

    print(f"UPSERT STATUS: {r.status_code}")

    if r.status_code >= 400:

        print(r.text)

        return False

    return True


def purge_old_bases():

    print("============================================================")
    print("PURGING OLD BASES")
    print("============================================================")

    cutoff = (
        NOW - timedelta(days=30)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    url = (
        API_URL
        + "?last_seen_at=lt."
        + cutoff
    )

    r = requests.delete(
        url,
        headers=headers(),
        timeout=60
    )

    print(f"PURGE STATUS: {r.status_code}")

    if r.status_code >= 400:
        print(r.text)

# =========================================================
# SCRAPER
# =========================================================

TOTAL_UPSERTED = 0


def scrape_source(source):

    global TOTAL_UPSERTED

    topic_url = source["url"]

    print("============================================================")
    print("SCRAPING")
    print(topic_url)
    print("============================================================")

    r = requests.get(
        topic_url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=60
    )

    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    total_pages = get_total_pages(soup)

    print(f"TOTAL PAGES: {total_pages}")

    for page in range(1, total_pages + 1):

        page_url = get_page_url(topic_url, page)

        print("--------------------------------------------------")
        print(f"PAGE {page}")
        print(page_url)
        print("--------------------------------------------------")

        r = requests.get(
            page_url,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=60
        )

        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        articles = soup.select("article")

        print(f"FOUND {len(articles)} ARTICLES")

        for article in articles:

            raw_post = clean_multiline(
                article.get_text("\n", strip=True)
            )

            if not raw_post:
                continue

            parsed = {}

            for key, label in source["fields"].items():

                value = extract_field(
                    raw_post,
                    label
                )

                parsed[key] = value

            if not parsed.get("shard"):

                inferred_server = (
                    extract_server_from_text(raw_post)
                )

                if inferred_server:
                    parsed["shard"] = inferred_server

            parsed["shard"] = normalize_server(
                parsed.get("shard")
            )

            parsed["category"] = sanitize_category(
                parsed.get("category")
            )

            parsed["description"] = extract_description(
                raw_post
            )

            parsed["post_author"] = extract_author(
                article
            )

            parsed["post_date"] = extract_post_date(
                article
            )

            parsed["source_url"] = page_url

            parsed["source_page"] = page

            parsed["source_topic"] = (
                topic_url
                .split("/topic/")[1]
                .split("/")[0]
            )

            parsed["raw_post"] = raw_post

            parsed["event_name"] = source["event_name"]

            parsed["event_type"] = source["event_type"]

            if not parsed.get("supergroup_name"):
                continue

            if not parsed.get("shard"):
                continue

            if not parsed.get("base_code"):
                continue

            if not parsed.get("category"):
                continue

            parsed["base_code"] = clean(
                parsed["base_code"]
            )

            parsed["base_code"] = (
                parsed["base_code"]
                .split(" ")[0]
                .strip()
            )

            if not re.match(
                r"^[A-Z0-9\-]+$",
                parsed["base_code"],
                re.IGNORECASE
            ):
                continue

            print("--------------------------------------------------")
            print("PARSED DATA:")
            print(parsed)

            inserted = upsert_base(parsed)

            if inserted:

                TOTAL_UPSERTED += 1

                print("UPSERTED")

# =========================================================
# MAIN
# =========================================================

def main():

    print("============================================================")
    print("HC FORUM BASE SCRAPER")
    print("============================================================")

    for source in SOURCES:

        scrape_source(source)

    purge_old_bases()

    print("============================================================")
    print("DONE")
    print(f"TOTAL UPSERTED: {TOTAL_UPSERTED}")
    print("============================================================")


if __name__ == "__main__":
    main()
