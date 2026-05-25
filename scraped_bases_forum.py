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


def sanitize_supergroup_name(name):

    if not name:
        return None

    name = clean(name)

    patterns = [

        r"\(but.*?$",
        r"\(sg.*?$",
        r"\(supergroup.*?$",
        r"\(the sg.*?$"
    ]

    for pattern in patterns:

        name = re.sub(
            pattern,
            "",
            name,
            flags=re.IGNORECASE
        )

    return clean(name)


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
        "Posted"
    ]

    for stop in STOP_WORDS:

        idx = category.lower().find(
            stop.lower()
        )

        if idx > 0:

            category = category[:idx].strip()

    STOP_PATTERNS = [

        r"\(",
        r"I thought",
        r"Think I",
        r"Haven't put",
        r"I can't show",
        r"feel free",
        r"Its a",
        r"It's a",
        r"you'll need",
        r"must have"
    ]

    for pattern in STOP_PATTERNS:

        m = re.search(
            pattern,
            category,
            re.IGNORECASE
        )

        if m:

            category = category[:m.start()].strip()

    category = re.sub(
        r"\s+\d+$",
        "",
        category
    )

    category = category.replace(
        "Fantasy /",
        "Fantasy"
    )

    category = category.replace(
        "Tech /",
        "Tech"
    )

    category = category.replace(
        "Other /",
        "Other"
    )

    category = category.replace(
        "  ",
        " "
    )

    category = category.rstrip(".,:- ")

    category = category.strip(" :-")

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
        + r"(?=\n(?:"
        + r"Supergroup Name|"
        + r"Base or SG Name|"
        + r"Shard|"
        + r"Shard/Server|"
        + r"Passcode|"
        + r"Base Code|"
        + r"Category|"
        + r"Description|"
        + r"Special or Hidden Features"
        + r")[^\n]{0,60}:|\Z)"
    )

    match = re.search(
        pattern,
        raw_text,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return None

    value = clean(match.group(1))

    value = re.split(
        r"(Shard/Server|Shard|Base Code|Passcode|Category)",
        value,
        flags=re.IGNORECASE
    )[0].strip()

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

# =========================================================
# SPLIT MULTI BASE POSTS
# =========================================================

def split_into_base_blocks(raw_post):

    pattern = re.compile(
        r"(?=(?:Supergroup Name|Base or SG Name)\s*:)",
        re.IGNORECASE
    )

    matches = list(pattern.finditer(raw_post))

    if not matches:
        return [raw_post]

    blocks = []

    for i, match in enumerate(matches):

        start = match.start()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(raw_post)

        block = raw_post[start:end].strip()

        if block:
            blocks.append(block)

    return blocks

# =========================================================
# PAGINATION
# =========================================================

def get_total_pages(soup):

    max_page = 1

    for tag in soup.select("[data-page]"):

        try:

            page = int(tag.get("data-page"))

            if page > max_page:
                max_page = page

        except:
            pass

    for link in soup.select("a[href*='page=']"):

        href = link.get("href", "")

        m = re.search(
            r"[?&]page=(\d+)",
            href
        )

        if m:

            page = int(m.group(1))

            if page > max_page:
                max_page = page

    for link in soup.select("a[href*='/page/']"):

        href = link.get("href", "")

        m = re.search(
            r"/page/(\d+)",
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

    if base_url.endswith("/"):
        return f"{base_url}page/{page}/"

    return f"{base_url}/page/{page}/"

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

    print("==================================================")
    print("PAGINATION DEBUG")
    print("==================================================")

    pagination_links = soup.select("a[href]")

    for link in pagination_links[:200]:

        href = link.get("href", "")

        if "page" in href.lower():

            print(href)

    total_pages = get_total_pages(soup)

    print("==================================================")
    print(f"TOTAL PAGES DETECTED: {total_pages}")
    print("==================================================")

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

            # =====================================================
            # AUTHOR / DATE
            # =====================================================

            author_tag = article.select_one(
                ".ipsType_break.ipsContained a"
            )

            post_author = None

            if author_tag:
                post_author = clean(
                    author_tag.get_text()
                )

            time_tag = article.select_one("time")

            post_date = None

            if time_tag:

                post_date = (
                    time_tag.get("datetime")
                    or clean(time_tag.get_text())
                )

            # =====================================================
            # SPLIT MULTI BASE POSTS
            # =====================================================

            blocks = split_into_base_blocks(raw_post)

            for block in blocks:

                parsed = {}

                for key, label in source["fields"].items():

                    value = extract_field(block, label)

                    parsed[key] = value

                parsed["supergroup_name"] = sanitize_supergroup_name(
                    parsed.get("supergroup_name")
                )

                if not parsed.get("shard"):

                    inferred_server = extract_server_from_text(block)

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

                parsed["description"] = extract_description(block)

                parsed["source_url"] = page_url

                parsed["source_page"] = page

                parsed["source_topic"] = (
                    topic_url
                    .split("/topic/")[1]
                    .split("/")[0]
                )

                parsed["event_name"] = source["event_name"]

                parsed["event_type"] = source["event_type"]

                parsed["raw_post"] = block

                parsed["post_author"] = post_author

                parsed["post_date"] = post_date

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
