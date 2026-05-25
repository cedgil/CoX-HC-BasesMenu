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

    return None()


def get_total_pages(soup):

    max_page = 1

    # =====================================================
    # STANDARD PAGE LINKS
    # =====================================================

    for link in soup.select("a[href]"):

        href = link.get("href", "")

        patterns = [

            r"/page/(\d+)/",
            r"[?&]page=(\d+)",
            r"-page-(\d+)"
        ]

        for pattern in patterns:

            m = re.search(pattern, href)

            if m:

                page = int(m.group(1))

                if page > max_page:
                    max_page = page

    # =====================================================
    # PAGINATION TEXT
    # =====================================================

    text = soup.get_text(" ", strip=True)

    matches = re.findall(
        r"Page\s+\d+\s+of\s+(\d+)",
        text,
        re.IGNORECASE
    )

    for m in matches:

        page = int(m)

        if page > max_page:
            max_page = page

    return max_page


def get_page_url(base_url, page):

    if page <= 1:
        return base_url

    if "/page/" in base_url:

        return re.sub(
            r"/page/\d+/?",
            f"/page/{page}/",
            base_url
        )

    if base_url.endswith("/"):

        return f"{base_url}page/{page}/"

    return f"{base_url}/page/{page}/"

# =========================================================
# CATEGORY
# =========================================================

def sanitize_category(category):

    if not category:
        return None

    category = clean(category)

    # =====================================================
    # KEEP ONLY FIRST CATEGORY BEFORE /
    # =====================================================

    if "/" in category:

        first = category.split("/")[0].strip()

        if first:
            category = first

    # =====================================================
    # REMOVE LONG EXPLANATIONS / COMMENTS
    # =====================================================

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

        "So,",
        "Which,",
        "I can't show",
        "I list",
        "feel free",
        "Important",
        "Must have",
        "Its a",
        "It's a",
        "Think I technically",
        "wasn't sure where",
        "haven't put this",
        "Home and Living",
        "games and CC venues",
        "when a base is also"

    ]

    for stop in STOP_WORDS:

        idx = category.lower().find(
            stop.lower()
        )

        if idx > 0:

            category = category[:idx].strip()

    # =====================================================
    # REMOVE COMMENTS BETWEEN () OR AFTER ,
    # =====================================================

    category = re.sub(
        r"\(.*?\)",
        "",
        category
    )

    category = category.split(",")[0].strip()

    # =====================================================
    # CLEAN TRAILING GARBAGE
    # =====================================================

    category = re.sub(
        r"\s+\d+$",
        "",
        category
    )

    category = category.strip(" :-/")

    # =====================================================
    # NORMALIZE COMMON VARIANTS
    # =====================================================

    normalized_map = {

        "supergroup headquarters":
            "Supergroup Headquarters",

        "supergroup base":
            "Supergroup Base",

        "clubs and venues":
            "Clubs and Venues",

        "club and venues":
            "Clubs and Venues",

        "clubs & venues":
            "Clubs and Venues",

        "club":
            "Clubs and Venues",

        "utility base":
            "Utility Base",

        "utility bases":
            "Utility Base",

        "free form":
            "Freeform",

        "freeform":
            "Freeform",

        "rp base":
            "RP Base",

        "realism":
            "Realism",

        "fantasy":
            "Fantasy",

        "tech":
            "Tech",

        "space":
            "Space",

        "nature":
            "Nature",

        "novice":
            "Novice",

        "other":
            "Other",

        "other misc":
            "Other Misc",

        "misc":
            "Other Misc"

    }

    lower = category.lower().strip()

    if lower in normalized_map:
        return normalized_map[lower]

    category = category.title()

    return clean(category)

# =========================================================
# POST SPLITTING
# =========================================================

def split_post_into_entries(raw_post):

    patterns = [

        r"Supergroup Name\s*:",
        r"Base or SG Name\s*:"
    ]

    combined = "(" + "|".join(patterns) + ")"

    matches = list(
        re.finditer(
            combined,
            raw_post,
            re.IGNORECASE
        )
    )

    if not matches:
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
# FIELD EXTRACTION
# =========================================================

def extract_value_after_label(text, labels):

    if isinstance(labels, str):
        labels = [labels]

    for label in labels:

        pattern = (
            re.escape(label)
            + r"\s*:?\s*(.+?)(?=\n[A-Z][^\n]{0,60}:|\Z)"
        )

        m = re.search(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL
        )

        if m:

            value = clean(m.group(1))

            value = value.split("\n")[0].strip()

            if value:
                return value

    return None

# =========================================================
# DESCRIPTION
# =========================================================

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

            # =================================================
            # AUTHOR / DATE
            # =================================================

            post_author = None
            post_date = None

            author_el = article.select_one(
                ".ipsType_break"
            )

            if author_el:
                post_author = clean(
                    author_el.get_text(" ", strip=True)
                )

            time_el = article.select_one("time")

            if time_el:

                post_date = (
                    time_el.get("datetime")
                    or clean(
                        time_el.get_text(" ", strip=True)
                    )
                )

            # =================================================
            # MULTI-ENTRY SUPPORT
            # =================================================

            chunks = split_post_into_entries(raw_post)

            for chunk in chunks:

                parsed = {}

                parsed["supergroup_name"] = extract_value_after_label(
                    chunk,
                    [
                        "Supergroup Name",
                        "Base or SG Name"
                    ]
                )

                parsed["shard"] = extract_value_after_label(
                    chunk,
                    [
                        "Shard/Server",
                        "Shard",
                        "Server"
                    ]
                )

                parsed["base_code"] = extract_value_after_label(
                    chunk,
                    [
                        "Base Code",
                        "Passcode"
                    ]
                )

                parsed["category"] = extract_value_after_label(
                    chunk,
                    [
                        "Category to list base in",
                        "Category for Contest"
                    ]
                )

                parsed["description"] = extract_description(chunk)

                # =================================================
                # FIX NAME EXTRACTION
                # =================================================

                if parsed.get("supergroup_name"):

                    parsed["supergroup_name"] = (
                        parsed["supergroup_name"]
                        .split("Shard/Server")[0]
                        .split("Shard")[0]
                        .strip(" :-")
                    )

                # =================================================
                # SERVER
                # =================================================

                if not parsed.get("shard"):

                    inferred_server = extract_server_from_text(chunk)

                    if inferred_server:
                        parsed["shard"] = inferred_server

                parsed["shard"] = normalize_server(
                    parsed.get("shard")
                )

                # =================================================
                # CATEGORY
                # =================================================

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

                # =================================================
                # METADATA
                # =================================================

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

                # =================================================
                # VALIDATION
                # =================================================

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
