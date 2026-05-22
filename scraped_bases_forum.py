#!/usr/bin/env python3

import os
import re
import requests

from bs4 import BeautifulSoup

# =========================================================
# CONFIG
# =========================================================

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

SUPABASE_TABLE = "scraped_bases_forum"

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
    }

]

# =========================================================
# HEADERS
# =========================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# =========================================================
# HELPERS
# =========================================================

def clean(text):

    if not text:
        return ""

    text = text.replace("\u00a0", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()

# =========================================================
# FIELD EXTRACTION
# =========================================================

def extract_field(text, label):

    idx = text.lower().find(label.lower())

    if idx == -1:
        return ""

    start = idx + len(label)

    chunk = text[start:start + 1500]

    stop_patterns = [

        "supergroup name:",
        "shard/server:",
        "base code:",
        "category to list base in:",

        "your base’s name:",
        "the shard it is located on:",
        "the passcode for entry:",
        "the category your base is entering under:",

        "contributing builders",
        "additional information",
        "edited "
    ]

    lower_chunk = chunk.lower()

    stop_positions = []

    for p in stop_patterns:

        pos = lower_chunk.find(p)

        if pos > 0:
            stop_positions.append(pos)

    if stop_positions:
        chunk = chunk[:min(stop_positions)]

    value = clean(chunk)

    value = value.replace("|", " ")

    value = re.sub(r"\s+", " ", value)

    return value.strip()

# =========================================================
# NORMALIZATION
# =========================================================

def normalize_code(code):

    if not code:
        return ""

    code = code.upper().strip()

    m = re.search(
        r"[A-Z0-9]{2,}-\d+",
        code
    )

    if not m:
        return ""

    return m.group(0)

# =========================================================
# VALIDATION
# =========================================================

def valid_base(data):

    required = [
        "supergroup_name",
        "shard",
        "base_code",
        "category"
    ]

    for field in required:

        if not data.get(field):
            return False

    return True

# =========================================================
# SUPABASE
# =========================================================

def base_exists(base_code):

    params = {
        "base_code": f"eq.{base_code}",
        "select": "id"
    }

    r = requests.get(
        API_URL,
        headers=SUPABASE_HEADERS,
        params=params,
        timeout=30
    )

    print("CHECK STATUS:", r.status_code)

    if r.status_code >= 400:
        print("CHECK RESPONSE:", r.text)
        return False

    try:

        data = r.json()

        return len(data) > 0

    except:
        return False

# =========================================================
# UPSERT
# =========================================================

def upsert_base(data):

    params = {
        "on_conflict": "base_code"
    }

    r = requests.post(
        API_URL,
        headers=SUPABASE_HEADERS,
        params=params,
        json=[data],
        timeout=60
    )

    print("UPSERT STATUS:", r.status_code)

    if r.text:
        print("UPSERT RESPONSE:", r.text[:500])

    return r.status_code < 300

# =========================================================
# SCRAPER
# =========================================================

def scrape_source(source):

    url = source["url"]

    fields = source["fields"]

    print("============================================================")
    print("SCRAPING")
    print(url)
    print("============================================================")

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=60
    )

    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    selectors = [
        ".ipsComment_content",
        ".cPost_contentWrap",
        ".ipsType_richText",
        "article"
    ]

    posts = []

    for selector in selectors:

        found = soup.select(selector)

        print(f"FOUND {len(found)} POSTS USING {selector}")

        posts.extend(found)

    # =====================================================
    # DEDUPE
    # =====================================================

    unique_posts = []

    seen = set()

    for post in posts:

        text = clean(
            post.get_text("\n", strip=True)
        )

        if not text:
            continue

        if text in seen:
            continue

        seen.add(text)

        unique_posts.append(text)

    print(f"TOTAL RAW POSTS: {len(unique_posts)}")

    inserted = 0

    # =====================================================
    # PARSE
    # =====================================================

    for text in unique_posts:

        data = {}

        for key, label in fields.items():

            value = extract_field(
                text,
                label
            )

            data[key] = value

        data["base_code"] = normalize_code(
            data.get("base_code", "")
        )

        print("--------------------------------------------------")
        print("PARSED DATA:")
        print(data)

        if not valid_base(data):
            print("INVALID ENTRY")
            continue

        print("----------------------------------------")
        print("BASE FOUND")
        print(data["supergroup_name"])
        print(data["shard"])
        print(data["base_code"])
        print(data["category"])

        exists = base_exists(
            data["base_code"]
        )

        if exists:
            print("ALREADY EXISTS")
            continue

        ok = upsert_base(data)

        if ok:
            print("INSERTED")
            inserted += 1
        else:
            print("INSERT FAILED")

    return inserted

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

        try:

            inserted = scrape_source(source)

            total += inserted

        except Exception as e:

            print("============================================================")
            print("ERROR")
            print("============================================================")
            print(e)

    print("============================================================")
    print("DONE")
    print("TOTAL UPSERTED:", total)
    print("============================================================")

# =========================================================

if __name__ == "__main__":
    main()
