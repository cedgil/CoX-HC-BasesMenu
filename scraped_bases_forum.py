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
    # FREEFORM
    # =====================================================

    "freeform": "Freeform",
    "free form": "Freeform",
    "free-form": "Freeform",
    "free form and venue": "Freeform",

    # =====================================================
    # TECH SCI-FI
    # =====================================================

    "tech sci-fi": "Tech/Sci-Fi",
    "tech / sci-fi": "Tech/Sci-Fi",
    "tech/sci-fi": "Tech/Sci-Fi",
    "sci-fi": "Tech/Sci-Fi",
    "science fiction": "Tech/Sci-Fi",

    # =====================================================
    # FANTASY ARCANE
    # =====================================================

    "fantasy arcane": "Fantasy/Arcane",
    "fantasy / arcane": "Fantasy/Arcane",
    "fantasy/arcane": "Fantasy/Arcane",

    # =====================================================
    # OTHER MISC
    # =====================================================

    "other misc": "Other/Misc",
    "other / misc": "Other/Misc",
    "other/misc": "Other/Misc",
    "other miscellaneous": "Other/Misc",
    "other / miscellaneous": "Other/Misc",
    "other/miscellaneous": "Other/Misc",
    "misc": "Other/Misc",
    "misc.": "Other/Misc",
    "miscellaneous": "Other/Misc",

    # =====================================================
    # CLUBS
    # =====================================================

    "clubs and venues": "Clubs and Venues",
    "club and venues": "Clubs and Venues",

    # =====================================================
    # UTILITY
    # =====================================================

    "utility under 7000": "Utility Under 7000",
    "utility way under 7000": "Utility Under 7000",
    "decorated utility base under 7k": "Decorated Utility Base Under 7K",
    "decorated utility base over 7k": "Decorated Utility Base Over 7K",

    # =====================================================
    # MULTIPURPOSE
    # =====================================================

    "multipurpose base under 7k": "Multipurpose Base Under 7K",
    "multipurpose base under 7k items": "Multipurpose Base Under 7K",

    "multipurpose base over 7k": "Multipurpose Base Over 7K",
    "multipurpose base over 7k items": "Multipurpose Base Over 7K",

    # =====================================================
    # RP
    # =====================================================

    "rp base under 7k": "RP Base Under 7K",
    "rp base under 7k items": "RP Base Under 7K",

    "rp base over 7k": "RP Base Over 7K",
    "rp base over 7k items": "RP Base Over 7K",

    # =====================================================
    # SUPERGROUP HQ
    # =====================================================

    "supergroup headquarters": "Supergroup Headquarters",
    "supergroup headquarters.": "Supergroup Headquarters",
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

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = text.strip()

    # ============================================
    # remove trailing forum separators
    # ============================================

    text = re.sub(
        r"\s*[-–—]+\s*$",
        "",
        text
    )

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
# CATEGORY CLEANUP
# =========================================================

CATEGORY_STOP_MARKERS = [

    "special or hidden features",
    "is flight or teleportation",
    "additional info",
    "must-see areas",
    "must see areas",
    "other associated contributors",
    "contributing builders",
    "description",
    "edited",
    "posted",
    "setting to",
    "for those interested in lore",
    "area of interest",
    "i can't show a lot because",
    "important !!!",
    "definitely a base that is not going",
    "home and living design",
    "feel free to relocate",
]


def normalize_category(category, allowed_categories=None):

    if not category:
        return None

    if allowed_categories is None:
        allowed_categories = []

    category = clean(category)

    category = re.sub(
        r"\s+",
        " ",
        category
    ).strip()

    lower = category.lower()

    # =====================================================
    # STOP MARKERS
    # =====================================================

    for marker in CATEGORY_STOP_MARKERS:

        idx = lower.find(marker)

        if idx > 0:

            category = category[:idx].strip()
            lower = category.lower()

    # =====================================================
    # PARENTHESIS
    # =====================================================

    category = re.sub(
        r"\(.*?\)",
        "",
        category
    ).strip()

    lower = category.lower()

    # =====================================================
    # ALIASES
    # =====================================================

    alias = CATEGORY_ALIASES.get(lower)

    if alias:

        category = alias
        lower = category.lower()

    else:

        for alias_key, alias_value in CATEGORY_ALIASES.items():

            if lower.startswith(alias_key):

                category = alias_value
                lower = category.lower()
                break

    # =====================================================
    # EXACT MATCH
    # =====================================================

    for allowed in allowed_categories:

        if lower == allowed.lower():
            return allowed

    # =====================================================
    # CONTAINS MATCH
    # =====================================================

    for allowed in allowed_categories:

        if allowed.lower() in lower:
            return allowed

    # =====================================================
    # REVERSE CONTAINS
    # =====================================================

    for allowed in allowed_categories:

        if lower in allowed.lower():
            return allowed

    # =====================================================
    # KEYWORD MATCH
    # =====================================================

    keywords = {
    "fantasy": "Fantasy",
    "arcane": "Fantasy/Arcane",
    "tech": "Tech/Sci-Fi",
    "sci": "Tech/Sci-Fi",
    "realism": "Realism",
    "freeform": "Freeform",
    "free form": "Freeform",
    "novice": "Novice",
    "club": "Clubs and Venues",
    "venue": "Clubs and Venues",
    "headquarters": "Supergroup Headquarters",
    "utility": "Utility",
    "transit": "Transit Hub",
    "travel hub": "Transit Hub",
    "rp": "RP",
    "seasonal": "Seasonal",
    "nature": "Nature",
    "floating": "Floating Islands",
    "functional": "Functional"
}

    for keyword, target in keywords.items():

        if keyword in lower:

            for allowed in allowed_categories:

                if target.lower() in allowed.lower():
                    return allowed

    # =====================================================
    # FALLBACK
    # =====================================================

    for allowed in allowed_categories:

        first_word = allowed.lower().split()[0]

        if first_word in lower:
            return allowed

    return None


# =========================================================
# FIELD EXTRACTION
# =========================================================

def extract_field(raw_text, label):

    pattern = (
        re.escape(label)
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

    value = value.strip()

    if (
        len(value) >= 2
        and value[0] == '"'
        and value[-1] == '"'
    ):
        value = value[1:-1].strip()

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
# PAGINATION
# =========================================================

def get_total_pages(soup):

    max_page = 1

    for a in soup.select("a[href]"):

        href = a.get("href", "")

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

    if not base_url.endswith("/"):
        base_url += "/"

    return f"{base_url}page/{page}/"


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
# SPLIT MULTI-BASE POSTS
# =========================================================

def split_post_into_entries(raw_post):

    chunks = re.split(
        r"(?=Supergroup Name:|Base or SG Name:|Your base’s name:)",
        raw_post,
        flags=re.IGNORECASE
    )

    cleaned = []

    for chunk in chunks:

        chunk = clean_multiline(chunk)

        if not chunk:
            continue

        cleaned.append(chunk)

    return cleaned

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
                "[data-author]"
            )

            if author_el:
                post_author = clean(
                    author_el.get("data-author")
                )

            time_el = article.select_one("time")

            if time_el:

                post_date = (
                    time_el.get("datetime")
                    or clean(time_el.get_text())
                )

            # =================================================
            # SPLIT MULTI BASE POSTS
            # =================================================

            entries = split_post_into_entries(raw_post)

            for chunk in entries:

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

                parsed["category"] = normalize_category(
                    parsed.get("category"),
                    source.get("allowed_categories", [])
                )

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

                parsed["raw_post"] = chunk

                parsed["post_author"] = post_author

                parsed["post_date"] = post_date

                # =============================================
                # VALIDATION
                # =============================================

                if not parsed.get("supergroup_name"):
                    continue

                if not parsed.get("base_code"):
                    continue

                if not parsed.get("shard"):
                    continue

                if parsed["shard"] not in VALID_SHARDS:
                    continue

                print("================================")
                print("RAW BASE CODE")
                print(repr(parsed["base_code"]))
                print("================================")
                
                parsed["base_code"] = clean(
                    parsed["base_code"]
                )

                print("AFTER CLEAN")
                print(repr(parsed["base_code"]))

                parsed["base_code"] = (
                    parsed["base_code"]
                    .split(" ")[0]
                    .strip()
                )
    
                print("FINAL BASE CODE")
                print(repr(parsed["base_code"]))
                print("================================")

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

    for source in SOURCES:

        scrape_source(source)

    purge_old_bases()

    print("============================================================")
    print("DONE")
    print(f"TOTAL UPSERTED: {TOTAL_UPSERTED}")
    print("============================================================")


if __name__ == "__main__":
    main()
