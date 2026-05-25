#!/usr/bin/env python3

import os
import re
import requests

from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

from scraped_bases_sources import SOURCES

# =========================================================
# CONFIG
# =========================================================

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

SUPABASE_TABLE = "scraped_bases_forum"

NOW = datetime.now(timezone.utc)

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

    "indom": "Indomitable",
    "indomitable": "Indomitable",

    "reunion": "Reunion",

    "victory": "Victory"
}

# =========================================================
# CATEGORY ALIASES
# =========================================================

CATEGORY_ALIASES = {

    "Tech Sci-Fi": "Tech/Sci-Fi",
    "Tech / Sci-Fi": "Tech/Sci-Fi",
    "Sci-Fi": "Tech/Sci-Fi",
    "Sci Fi": "Tech/Sci-Fi",
    "Tech/Sci Fi": "Tech/Sci-Fi",

    "Fantasy Arcane": "Fantasy/Arcane",
    "Fantasy / Arcane": "Fantasy/Arcane",

    "Other Misc": "Other/Misc",
    "Other / Misc": "Other/Misc",
    "Other / Misc.": "Other/Misc",
    "Other Miscellaneous": "Other/Misc",
    "Other / Miscellaneous": "Other/Misc",

    "Freeform": "Free Form",
    "Free form": "Free Form",
    "Free Form": "Free Form",

    "Clubs And Venues": "Clubs and Venues",
    "Club And Venues": "Clubs and Venues",

    "Supergroup Headquarters": "Supergroup Headquarters",
    "Supergroup headquarters": "Supergroup Headquarters",

    "Decorated Utility Base Under 7K Items": "Decorated Utility Base Under 7K",
    "Decorated Utility Base Over 7K Items": "Decorated Utility Base Over 7K",

    "Multipurpose Base Under 7K Items": "Multipurpose Base Under 7K",
    "Multipurpose Base Over 7K Items": "Multipurpose Base Over 7K",

    "RP Base Under 7K Items": "RP Base Under 7K",
    "RP Base Over 7K Items": "RP Base Over 7K",

    "Utility Way Under 7000": "Utility Under 7000",
}

# =========================================================
# SUPABASE
# =========================================================

if "/rest/v1/" in SUPABASE_URL:

    REST_BASE_URL = (
        SUPABASE_URL
        .split("/rest/v1")[0]
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


def sanitize_category(category, allowed_categories=None):

    if not category:
        return None

    category = clean(category)

    category = re.sub(
        r"\(.*",
        "",
        category
    ).strip()

    STOP_PATTERNS = [

        r"special or hidden features",
        r"is flight or teleportation",
        r"additional info",
        r"must-see",
        r"edited",
        r"posted",
        r"other associated",
        r"contributing builders",
        r"definitely a base",
        r"haven't put this",
        r"i can't show",
        r"for those interested",
        r"area of interest"
    ]

    lower = category.lower()

    for pattern in STOP_PATTERNS:

        m = re.search(pattern, lower)

        if m:
            category = category[:m.start()].strip()
            lower = category.lower()

    category = category.strip(" :-.,;/")

    category = re.sub(
        r"\s+2$",
        "",
        category
    ).strip()

    category = re.sub(
        r"\s+items?$",
        "",
        category,
        flags=re.IGNORECASE
    )

    category = category.title()

    for alias, canonical in CATEGORY_ALIASES.items():

        if category.lower() == alias.lower():
            category = canonical

    if allowed_categories:

        for allowed in allowed_categories:

            if category.lower() == allowed.lower():
                return allowed

            if category.lower().startswith(allowed.lower()):
                return allowed

            if allowed.lower().startswith(category.lower()):
                return allowed

    return category


def extract_field(raw_text, label):

    relaxed_label = ""

    for char in label:

        if char.isalpha():
            relaxed_label += char + r"\s*"
        else:
            relaxed_label += re.escape(char)

    pattern = (
        relaxed_label
        + r"\s*(.*?)"
        + r"(?=\n[A-Z][^\n]{0,60}:|\Z)"
    )

    match = re.search(
        pattern,
        raw_text,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return None

    value = clean(match.group(1))

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


def get_total_pages(soup):

    max_page = 1

    for link in soup.select("a[href]"):

        href = link.get("href", "")

        m = re.search(
            r"/page/(\d+)/",
            href
        )

        if m:

            page = int(m.group(1))

            if page > max_page:
                max_page = page

    return max_page


def get_page_url(base_url, page):

    if page <= 1:
        return base_url

    return base_url.rstrip("/") + f"/page/{page}/"


def split_multiple_entries(raw_post):

    patterns = [

        r"(?=Supergroup Name:)",
        r"(?=Base or SG Name:)",
        r"(?=Your base.?s name:)"
    ]

    splitter = "|".join(patterns)

    chunks = re.split(
        splitter,
        raw_post,
        flags=re.IGNORECASE
    )

    cleaned = []

    for chunk in chunks:

        chunk = chunk.strip()

        if (
            "Base Code" in chunk
            or "Passcode" in chunk
        ):
            cleaned.append(chunk)

    return cleaned

# =========================================================
# SUPABASE REQUESTS
# =========================================================

def upsert_base(data):

    payload = {
        **data,
        "scraped_at": NOW.isoformat()
    }

    r = requests.post(
        API_URL,
        headers=headers(),
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

    print("============================================================")
    print("PURGING OLD BASES")
    print("============================================================")

    cutoff = (
        NOW - timedelta(days=30)
    ).isoformat()

    r = requests.delete(
        API_URL,
        headers=headers(),
        params={
            "scraped_at": f"lt.{cutoff}"
        },
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

    allowed_categories = source.get(
        "allowed_categories",
        []
    )

    for page in range(1, total_pages + 1):

        page_url = get_page_url(
            topic_url,
            page
        )

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

            chunks = split_multiple_entries(raw_post)

            if not chunks:
                chunks = [raw_post]

            post_author = None

            author_tag = article.select_one(
                ".ipsType_break"
            )

            if author_tag:
                post_author = clean(author_tag.get_text())

            post_date = None

            time_tag = article.select_one("time")

            if time_tag:

                post_date = (
                    time_tag.get("datetime")
                    or clean(time_tag.get_text())
                )

            for chunk in chunks:

                parsed = {}

                for key, label in source["fields"].items():

                    value = extract_field(
                        chunk,
                        label
                    )

                    parsed[key] = value

                if not parsed.get("shard"):

                    inferred_server = extract_server_from_text(chunk)

                    if inferred_server:
                        parsed["shard"] = inferred_server

                parsed["shard"] = normalize_server(
                    parsed.get("shard")
                )

                parsed["category"] = sanitize_category(
                    parsed.get("category"),
                    allowed_categories
                )

                parsed["description"] = extract_description(chunk)

                parsed["category_fix"] = None

                parsed["source_url"] = page_url

                parsed["source_page"] = page

                parsed["source_topic"] = (
                    topic_url
                    .split("/topic/")[1]
                    .split("/")[0]
                )

                parsed["event_name"] = source["event_name"]

                parsed["event_type"] = source["event_type"]

                parsed["raw_post"] = chunk

                parsed["post_author"] = post_author

                parsed["post_date"] = post_date

                if not parsed.get("supergroup_name"):
                    continue

                if not parsed.get("shard"):
                    continue

                if parsed["shard"] not in VALID_SHARDS:
                    continue

                if not parsed.get("base_code"):
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
                    r"^[A-Z0-9]+-[0-9]+$",
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

    for source in SOURCES:

        scrape_source(source)

    purge_old_bases()

    print("============================================================")
    print("DONE")
    print(f"TOTAL UPSERTED: {TOTAL_UPSERTED}")
    print("============================================================")


if __name__ == "__main__":
    main()
