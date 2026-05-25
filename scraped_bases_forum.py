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


def normalize_category_case(category):

    if not category:
        return None

    category = category.strip()

    words = []

    for word in category.split():

        if word.upper() in ["RP", "WIP"]:
            words.append(word.upper())
        else:
            words.append(word.capitalize())

    return " ".join(words)


def sanitize_category(category):

    if not category:
        return None

    category = clean(category)

    STOP_WORDS = [

        "Contributing builders",
        "Other associated contributors",
        "Other associated co",
        "Additional Info",
        "Must-See Areas",
        "Special or Hidden Features",
        "Any additional information",
        "Is flight or teleportation",
        "Description",
        "Definitely a base",
        "Edited",
        "Posted",
        "So, Clubs and Venues",
        "I thought it was",
        "Think I technically",
        "Haven't put this",
        "I can't show",
        "Its a small but functional"

    ]

    for stop in STOP_WORDS:

        idx = category.lower().find(
            stop.lower()
        )

        if idx > 0:

            category = category[:idx].strip()

    category = category.split("\n")[0]

    if "/" in category:

        parts = [
            clean(p)
            for p in category.split("/")
            if clean(p)
        ]

        if parts:
            category = parts[0]

    category = re.sub(
        r"\(.*?\)",
        "",
        category
    )

    category = re.sub(
        r"\s+\d+$",
        "",
        category
    )

    category = category.strip(" :-,.;")

    category = normalize_category_case(category)

    return clean(category)


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
        + r"(?=\n(?:[A-Z][A-Za-z /&]{2,40}:)|\Z)"
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

    if label.lower().startswith("supergroup"):

        value = re.split(
            r"Shard/Server|Base Code|Passcode",
            value,
            flags=re.IGNORECASE
        )[0].strip()

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

        matches = re.findall(
            r"/page/(\d+)",
            href
        )

        for m in matches:

            page = int(m)

            if page > max_page:
                max_page = page

    return max_page


def get_page_url(base_url, page):

    if page <= 1:
        return base_url.rstrip("/")

    return f"{base_url.rstrip('/')}/page/{page}/"


def split_multiple_bases(raw_post):

    pattern = re.compile(
        r"(Supergroup Name\s*:?)",
        re.IGNORECASE
    )

    matches = list(pattern.finditer(raw_post))

    if len(matches) <= 1:
        return [raw_post]

    chunks = []

    for i, match in enumerate(matches):

        start = match.start()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(raw_post)

        chunk = raw_post[start:end].strip()

        if chunk:
            chunks.append(chunk)

    return chunks

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

            author = None

            author_tag = article.select_one(
                ".ipsType_break"
            )

            if author_tag:
                author = clean(author_tag.get_text())

            date = None

            time_tag = article.select_one("time")

            if time_tag:

                date = (
                    time_tag.get("datetime")
                    or clean(time_tag.get_text())
                )

            chunks = split_multiple_bases(raw_post)

            for chunk in chunks:

                parsed = {}

                for key, label in source["fields"].items():

                    value = extract_field(chunk, label)

                    parsed[key] = value

                if not parsed.get("shard"):

                    inferred_server = extract_server_from_text(chunk)

                    if inferred_server:
                        parsed["shard"] = inferred_server

                parsed["shard"] = normalize_server(
                    parsed.get("shard")
                )

                parsed["category"] = sanitize_category(
                    parsed.get("category")
                )

                if (
                    source["event_type"] == "contest"
                    and (
                        not parsed.get("category")
                        or parsed["category"].lower() in [
                            "unknown",
                            "n/a",
                            "none"
                        ]
                    )
                ):
                    parsed["category"] = "Thematic Contest"

                parsed["description"] = extract_description(chunk)

                parsed["source_url"] = page_url

                parsed["source_page"] = page

                parsed["source_topic"] = (
                    topic_url
                    .split("/topic/")[1]
                    .split("/")[0]
                )

                parsed["event_name"] = source["event_name"]

                parsed["event_type"] = source["event_type"]

                parsed["post_author"] = author

                parsed["post_date"] = date

                parsed["raw_post"] = chunk

                template_values = [

                    "Shard/Server",
                    "Base Code",
                    "Category to list base in",
                    "Passcode",
                    "Shard",
                    "Category for Contest"
                ]

                if (
                    parsed.get("shard") in template_values
                    or parsed.get("base_code") in template_values
                ):
                    continue

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
