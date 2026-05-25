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


# =========================================================
# CATEGORY CLEANER
# =========================================================

def sanitize_category(category):

    if not category:
        return None

    category = clean(category)

    # -----------------------------------------------------
    # HARD STOPS
    # -----------------------------------------------------

    STOP_PATTERNS = [

        r"special or hidden features",
        r"is flight or teleportation useful",
        r"additional info",
        r"must-see areas",
        r"edited",
        r"base services",
        r"setting to",
        r"for those interested",
        r"i can't show",
        r"its a small but functional",
        r"haven't put this",
        r"which, i list things",
        r"so, clubs and venues",
        r"the area of interest",
        r"important !!!",
        r"water looks terrible",
        r"feel free to relocate",
        r"think i technically qualify",
        r"i thought it was over",
        r"description",
        r"posted"
    ]

    lower = category.lower()

    cut_positions = []

    for pattern in STOP_PATTERNS:

        m = re.search(pattern, lower)

        if m:
            cut_positions.append(m.start())

    if cut_positions:
        category = category[:min(cut_positions)].strip()

    # -----------------------------------------------------
    # FIX "or maybe"
    # -----------------------------------------------------

    category = re.sub(
        r"\s+or maybe.*",
        "",
        category,
        flags=re.IGNORECASE
    )

    category = re.sub(
        r"\s+or.*",
        "",
        category,
        flags=re.IGNORECASE
    )

    # -----------------------------------------------------
    # REMOVE PARENTHESIS
    # -----------------------------------------------------

    category = re.sub(
        r"\(.*?\)",
        "",
        category
    )

    # -----------------------------------------------------
    # NORMALIZE SLASHES
    # -----------------------------------------------------

    category = category.replace(
        "Tech/Sci-Fi",
        "Tech Sci-Fi"
    )

    category = category.replace(
        "Fantasy/Arcane",
        "Fantasy Arcane"
    )

    category = category.replace(
        "Other/Misc",
        "Other Misc"
    )

    # -----------------------------------------------------
    # FIX UNDER/OVER ITEMS
    # -----------------------------------------------------

    category = re.sub(
        r"\bunder\s+7k\s+items\b",
        "Under 7K",
        category,
        flags=re.IGNORECASE
    )

    category = re.sub(
        r"\bover\s+7k\s+items\b",
        "Over 7K",
        category,
        flags=re.IGNORECASE
    )

    category = re.sub(
        r"\bunder\s+7k\b",
        "Under 7K",
        category,
        flags=re.IGNORECASE
    )

    category = re.sub(
        r"\bover\s+7k\b",
        "Over 7K",
        category,
        flags=re.IGNORECASE
    )

    category = re.sub(
        r"\s+2$",
        "",
        category
    )

    # -----------------------------------------------------
    # SPECIFIC FIXES
    # -----------------------------------------------------

    SPECIFIC = {

        "clubs and venues": "Clubs And Venues",
        "club and venues": "Clubs And Venues",

        "sci-fi": "Sci-Fi",
        "science": "Science",

        "realism": "Realism",

        "functional": "Functional",

        "seasonal": "Seasonal",

        "free form": "Freeform",
        "freeform": "Freeform",

        "supergroup headquarters": "Supergroup Headquarters",

        "tech sci-fi": "Tech Sci-Fi",

        "fantasy arcane": "Fantasy Arcane",

        "other misc": "Other Misc",

        "rp base under 7k": "RP Base Under 7K",

        "multipurpose base under 7k": "Multipurpose Base Under 7K",

        "multipurpose base over 7k": "Multipurpose Base Over 7K",

        "decorated utility base under 7k":
            "Decorated Utility Base Under 7K",

        "decorated utility base over 7k":
            "Decorated Utility Base Over 7K"
    }

    key = category.lower().strip(" :-/")

    if key in SPECIFIC:
        return SPECIFIC[key]

    # -----------------------------------------------------
    # FINAL CLEAN
    # -----------------------------------------------------

    category = category.strip(" :-/,")

    category = re.sub(
        r"\s+",
        " ",
        category
    )

    if not category:
        return None

    return category.title()


# =========================================================
# FIELD EXTRACTION
# =========================================================

def extract_field(block, labels):

    if isinstance(labels, str):
        labels = [labels]

    ALL_LABELS = [

        "Supergroup Name",
        "Base or SG Name",
        "Shard",
        "Shard/Server",
        "Server",
        "Passcode",
        "Base Code",
        "Category for Contest",
        "Category to list base in",
        "Description",
        "Special or Hidden Features",
        "Is flight or teleportation useful or needed in this base"
    ]

    for label in labels:

        escaped = re.escape(label)

        pattern = (
            rf"{escaped}\s*:?\s*(.*?)"
            rf"(?=\n(?:{'|'.join(map(re.escape, ALL_LABELS))})\s*:|\Z)"
        )

        match = re.search(
            pattern,
            block,
            re.IGNORECASE | re.DOTALL
        )

        if match:

            value = clean(match.group(1))

            if value:
                return value

    return None


def extract_description(block):

    desc = extract_field(
        block,
        "Description"
    )

    if not desc:
        return None

    return clean(desc)


# =========================================================
# MULTI-BASE SPLIT
# =========================================================

def split_post_into_blocks(raw_post):

    pattern = re.compile(

        r"(?=("
        r"Supergroup Name\s*:|"
        r"Base or SG Name\s*:)"
        r")",

        re.IGNORECASE
    )

    matches = list(pattern.finditer(raw_post))

    if not matches:
        return [raw_post]

    chunks = []

    for i, match in enumerate(matches):

        start = match.start()

        end = (
            matches[i + 1].start()
            if i + 1 < len(matches)
            else len(raw_post)
        )

        chunk = raw_post[start:end].strip()

        if chunk:
            chunks.append(chunk)

    return chunks


# =========================================================
# PAGINATION
# =========================================================

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

    if base_url.endswith("/"):
        return f"{base_url}page/{page}/"

    return f"{base_url}/page/{page}/"


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
                "[data-role='commentAuthor']"
            )

            if author_tag:
                author = clean(author_tag.get_text())

            post_date = None

            time_tag = article.select_one("time")

            if time_tag:

                post_date = (
                    time_tag.get("datetime")
                    or clean(time_tag.get_text())
                )

            blocks = split_post_into_blocks(raw_post)

            for block in blocks:

                parsed = {}

                parsed["supergroup_name"] = extract_field(
                    block,
                    [
                        "Supergroup Name",
                        "Base or SG Name"
                    ]
                )

                parsed["shard"] = extract_field(
                    block,
                    [
                        "Shard/Server",
                        "Shard",
                        "Server"
                    ]
                )

                parsed["base_code"] = extract_field(
                    block,
                    [
                        "Passcode",
                        "Base Code"
                    ]
                )

                parsed["category"] = extract_field(
                    block,
                    [
                        "Category to list base in",
                        "Category for Contest"
                    ]
                )

                if not parsed.get("shard"):

                    inferred = extract_server_from_text(block)

                    if inferred:
                        parsed["shard"] = inferred

                parsed["shard"] = normalize_server(
                    parsed.get("shard")
                )

                parsed["category"] = sanitize_category(
                    parsed.get("category")
                )

                parsed["description"] = extract_description(block)

                parsed["post_author"] = author

                parsed["post_date"] = post_date

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

                if not parsed.get("supergroup_name"):
                    continue

                if not parsed.get("base_code"):
                    continue

                if not parsed.get("shard"):
                    continue

                if parsed["shard"] not in VALID_SHARDS:
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
