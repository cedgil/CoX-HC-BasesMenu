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

    # =====================================================
    # TECH / SCI-FI
    # =====================================================

    "Tech Sci-Fi": "Tech/Sci-Fi",
    "Tech / Sci-Fi": "Tech/Sci-Fi",
    "Tech/Sci-Fi": "Tech/Sci-Fi",

    "Sci-Fi": "Tech/Sci-Fi",
    "Sci Fi": "Tech/Sci-Fi",
    "Science Fiction": "Tech/Sci-Fi",

    # =====================================================
    # FREEFORM
    # =====================================================

    "Freeform": "Freeform",
    "Free Form": "Freeform",
    "Free form": "Freeform",

    # =====================================================
    # OTHER / MISC
    # =====================================================

    "Other Misc": "Other/Misc",
    "Other / Misc": "Other/Misc",
    "Other / Misc.": "Other/Misc",

    "Other Miscellaneous": "Other/Misc",
    "Other / Miscellaneous": "Other/Misc",
    "Other/Miscellaneous": "Other/Misc",

    "Misc": "Other/Misc",
    "Misc.": "Other/Misc",
    "Miscellaneous": "Other/Misc",

    # =====================================================
    # FANTASY
    # =====================================================

    "Fantasy Arcane": "Fantasy/Arcane",
    "Fantasy / Arcane": "Fantasy/Arcane",
    "Fantasy/Arcane": "Fantasy/Arcane",

    # =====================================================
    # UTILITY
    # =====================================================

    "Utility Way Under 7000": "Utility Under 7000",
    "Utility Under 7000": "Utility Under 7000",

    "Decorated Utility Base Under 7K": "Utility Under 7000",
    "Decorated Utility Base Over 7K": "Utility Over 7000"
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


def get_total_pages(soup):

    max_page = 1

    for a in soup.select("a[href]"):

        href = a.get("href", "")

        m = re.search(r"/page/(\d+)/", href)

        if m:

            page = int(m.group(1))

            if page > max_page:
                max_page = page

    return max_page


def get_page_url(base_url, page):

    if page <= 1:
        return base_url

    return base_url.rstrip("/") + f"/page/{page}/"

# =========================================================
# CATEGORY CLEANING
# =========================================================

STOP_PATTERNS = [

    r"Special or Hidden Features.*",
    r"Is flight or teleportation.*",
    r"Additional Info.*",
    r"Must-See Areas.*",
    r"Other associated contributors.*",
    r"Contributing builders.*",
    r"Edited.*",
    r"Posted.*",
    r"Area of interest.*",
    r"For those interested in lore.*",
    r"So, Clubs and Venues.*",
    r"I can't show a lot because.*",
    r"Haven't put this in the base registry.*",
    r"It's a small but functional base.*"
]


def clean_category(raw):

    if not raw:
        return None

    category = clean(raw)

    for pattern in STOP_PATTERNS:

        category = re.sub(
            pattern,
            "",
            category,
            flags=re.IGNORECASE
        )

    category = category.strip(" :-.,;/")

    category = re.sub(
        r"\s+items?$",
        "",
        category,
        flags=re.IGNORECASE
    )

    category = re.sub(
        r"\s+2$",
        "",
        category
    )

    category = re.sub(
        r"\s+The$",
        "",
        category,
        flags=re.IGNORECASE
    )

    lower = category.lower()

    if "way under 7000" in lower:
        return "Utility Under 7000"

    if "other / misc" in lower:
        return "Other/Misc"

    if "miscellaneous" in lower:
        return "Other/Misc"

    if "free form" in lower:
        return "Freeform"

    if "freeform" in lower:
        return "Freeform"

    if "sci-fi" in lower:
        return "Tech/Sci-Fi"

    if "tech / sci-fi" in lower:
        return "Tech/Sci-Fi"

    if "tech/sci-fi" in lower:
        return "Tech/Sci-Fi"

    return category.strip()


def normalize_category(category):

    if not category:
        return None

    category = clean_category(category)

    if not category:
        return None

    for alias, target in CATEGORY_ALIASES.items():

        if category.lower() == alias.lower():
            return target

    return category


def resolve_category(raw_category, allowed_categories):

    category = normalize_category(raw_category)

    if not category:
        return None

    if not allowed_categories:
        return category

    for allowed in allowed_categories:

        if category.lower() == allowed.lower():
            return allowed

    for allowed in allowed_categories:

        if category.lower().startswith(allowed.lower()):
            return allowed

    return category

# =========================================================
# FIELD EXTRACTION
# =========================================================

def extract_field(text, label):

    if not label:
        return None

    pattern = (
        re.escape(label)
        + r"\s*(.*?)"
        + r"(?=\n[A-Z][^:\n]{1,80}:|\Z)"
    )

    m = re.search(
        pattern,
        text,
        re.IGNORECASE | re.DOTALL
    )

    if not m:
        return None

    value = clean(m.group(1))

    value = value.split("\n")[0].strip()

    return value


def extract_post_author(article):

    selectors = [

        ".ipsType_break",
        ".cAuthorPane_author strong",
        ".ipsType_sectionHead"
    ]

    for selector in selectors:

        el = article.select_one(selector)

        if el:

            value = clean(el.get_text())

            if value:
                return value

    return None


def extract_post_date(article):

    time_el = article.select_one("time")

    if not time_el:
        return None

    value = (
        time_el.get("datetime")
        or time_el.get_text(strip=True)
    )

    return clean(value)

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

# =========================================================
# SCRAPER
# =========================================================

TOTAL_UPSERTED = 0


def split_post_into_chunks(text):

    markers = [

        "Supergroup Name:",
        "Base or SG Name:",
        "Your base’s name:"
    ]

    positions = []

    lower = text.lower()

    for marker in markers:

        idx = 0

        while True:

            pos = lower.find(marker.lower(), idx)

            if pos == -1:
                break

            positions.append(pos)

            idx = pos + 1

    positions = sorted(set(positions))

    if not positions:
        return [text]

    chunks = []

    for i, pos in enumerate(positions):

        end = (
            positions[i + 1]
            if i + 1 < len(positions)
            else len(text)
        )

        chunk = text[pos:end].strip()

        if chunk:
            chunks.append(chunk)

    return chunks


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

    source_topic = (
        topic_url
        .split("/topic/")[1]
        .split("/")[0]
    )

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

            chunks = split_post_into_chunks(raw_post)

            for chunk in chunks:

                parsed = {}

                for key, label in source["fields"].items():

                    parsed[key] = extract_field(
                        chunk,
                        label
                    )

                if not parsed.get("shard"):

                    inferred = extract_server_from_text(chunk)

                    if inferred:
                        parsed["shard"] = inferred

                parsed["shard"] = normalize_server(
                    parsed.get("shard")
                )

                parsed["category"] = resolve_category(
                    parsed.get("category"),
                    source.get("allowed_categories", [])
                )

                parsed["post_author"] = extract_post_author(article)

                parsed["post_date"] = extract_post_date(article)

                parsed["source_url"] = page_url

                parsed["source_page"] = page

                parsed["source_topic"] = source_topic

                parsed["event_name"] = source["event_name"]

                parsed["event_type"] = source["event_type"]

                parsed["raw_post"] = chunk

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
