#!/usr/bin/env python3

import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# =========================================================
# CONFIG
# =========================================================

FORUM_URL = (
    "https://forums.homecomingservers.com/topic/53862-2025-base-building-contest/"
)

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

SUPABASE_TABLE = "scraped_bases_forum"

NOW = datetime.now(timezone.utc)

# =========================================================
# REST URL
# =========================================================

if "/rest/v1/" in SUPABASE_URL:
    REST_BASE_URL = SUPABASE_URL.split("/rest/v1")[0] + "/rest/v1"

elif SUPABASE_URL.endswith("/rest/v1"):
    REST_BASE_URL = SUPABASE_URL

else:
    REST_BASE_URL = SUPABASE_URL + "/rest/v1"

API_URL = f"{REST_BASE_URL}/{SUPABASE_TABLE}"

# =========================================================
# HEADERS
# =========================================================

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# =========================================================
# DEBUG
# =========================================================

print("============================================================")
print("SUPABASE DEBUG")
print("============================================================")
print("API_URL =", API_URL)
print("============================================================")

# =========================================================
# FETCH
# =========================================================

def fetch_html(url):

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    r.raise_for_status()

    return r.text

# =========================================================
# CLEAN
# =========================================================

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

# =========================================================
# PARSE POSTS
# =========================================================

def parse_posts(html):

    soup = BeautifulSoup(html, "html.parser")

    possible_posts = []

    selectors = [
        "article",
        ".ipsComment",
        ".cPost",
        ".ipsComment_content",
        ".ipsType_richText"
    ]

    for selector in selectors:

        found = soup.select(selector)

        if found:
            print(f"FOUND {len(found)} POSTS USING {selector}")
            possible_posts = found

            break

    return possible_posts

# =========================================================
# EXTRACTION
# =========================================================

def extract_base_code(text):

    m = re.search(
        r"\b[A-Z0-9]{2,}-\d+\b",
        text.upper()
    )

    if m:
        return m.group(0)

    return None


def extract_shard(text):

    shards = [
        "Excelsior",
        "Everlasting",
        "Torchbearer",
        "Indomitable",
        "Victory",
        "Reunion"
    ]

    for shard in shards:
        if re.search(rf"\b{shard}\b", text, re.IGNORECASE):
            return shard

    return None


def extract_category(text):

    patterns = [
        r"The category your base is entering under:\s*(.+?)(?:Contributing builders|$)",
        r"Category:\s*(.+)"
    ]

    for p in patterns:

        m = re.search(
            p,
            text,
            re.IGNORECASE
        )

        if m:
            return clean(m.group(1))

    return None


def extract_supergroup_name(text):

    patterns = [
        r"Supergroup Name:\s*(.+)",
        r"SG Name:\s*(.+)",
        r"Base Name:\s*(.+)"
    ]

    for p in patterns:

        m = re.search(
            p,
            text,
            re.IGNORECASE
        )

        if m:
            return clean(m.group(1))

    #
    # FALLBACK :
    # prendre la première ligne AVANT le shard
    #

    lines = [
        clean(l)
        for l in text.split("\n")
        if clean(l)
    ]

    for i, line in enumerate(lines):

        if extract_shard(line):

            if i > 0:
                candidate = lines[i - 1]

                if len(candidate) < 100:
                    return candidate

    return None

# =========================================================
# EXISTS
# =========================================================

def base_exists(base_code):

    url = f"{API_URL}?base_code=eq.{base_code}&select=id"

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    print("CHECK STATUS:", r.status_code)

    if r.status_code != 200:
        print(r.text[:300])
        return False

    try:
        data = r.json()
        return len(data) > 0
    except:
        return False

# =========================================================
# UPSERT
# =========================================================

def upsert_entry(entry):

    params = {
        "on_conflict": "base_code"
    }

    r = requests.post(
        API_URL,
        headers=HEADERS,
        params=params,
        json=[entry],
        timeout=60
    )

    print("UPSERT STATUS:", r.status_code)

    if r.text:
        print(r.text[:500])

    return r.status_code in [200, 201]

# =========================================================
# SCRAPER
# =========================================================

def scrape():

    html = fetch_html(FORUM_URL)

    posts = parse_posts(html)

    inserted = 0

    for post in posts:

        text = post.get_text("\n", strip=True)

        text = clean(text)

        base_code = extract_base_code(text)

        #
        # skip direct si pas de passcode
        #

        if not base_code:
            continue

        supergroup_name = extract_supergroup_name(text)
        shard = extract_shard(text)
        category = extract_category(text)

        print("----------------------------------------")
        print("BASE FOUND")
        print("NAME:", supergroup_name)
        print("SHARD:", shard)
        print("CODE:", base_code)
        print("CATEGORY:", category)

        if not supergroup_name:
            print("SKIP: NO NAME")
            continue

        if not shard:
            print("SKIP: NO SHARD")
            continue

        if not category:
            print("SKIP: NO CATEGORY")
            continue

        exists = base_exists(base_code)

        entry = {
            "supergroup_name": supergroup_name,
            "shard": shard,
            "base_code": base_code,
            "category": category,
            "raw_text": text,
            "scraped_at": NOW.isoformat()
        }

        ok = upsert_entry(entry)

        if ok:

            if exists:
                print("UPDATED")
            else:
                print("INSERTED")

            inserted += 1

        else:
            print("INSERT FAILED")

    print("============================================================")
    print("DONE")
    print("TOTAL UPSERTED:", inserted)
    print("============================================================")

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    scrape()
