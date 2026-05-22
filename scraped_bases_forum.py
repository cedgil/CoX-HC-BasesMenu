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
# BUILD REST URL
# =========================================================

# accepte :
# https://xxx.supabase.co
# https://xxx.supabase.co/rest/v1
# https://xxx.supabase.co/rest/v1/table

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
print("SUPABASE_URL =", SUPABASE_URL)
print("REST_BASE_URL =", REST_BASE_URL)
print("API_URL =", API_URL)
print("============================================================")

# =========================================================
# FETCH HTML
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

    posts = soup.select("article")

    print(f"FOUND {len(posts)} POSTS")

    return posts

# =========================================================
# EXTRACTION HELPERS
# =========================================================

def extract_supergroup(text):

    patterns = [
        r"Supergroup Name:\s*(.+)",
        r"SG Name:\s*(.+)",
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return clean(m.group(1))

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


def extract_base_code(text):

    m = re.search(r"\b[A-Z0-9]{2,}-\d+\b", text.upper())

    if m:
        return m.group(0)

    return None


def extract_category(text):

    patterns = [
        r"The category your base is entering under:\s*(.+)",
        r"Category:\s*(.+)"
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return clean(m.group(1))

    return None

# =========================================================
# CHECK EXISTING
# =========================================================

def base_exists(base_code):

    url = f"{API_URL}?base_code=eq.{base_code}&select=id"

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    print("CHECK STATUS:", r.status_code)

    if r.text:
        print("CHECK RESPONSE:", r.text[:300])

    if r.status_code != 200:
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
        print("UPSERT RESPONSE:", r.text[:500])

    return r.status_code in [200, 201]

# =========================================================
# MAIN SCRAPER
# =========================================================

def scrape():

    html = fetch_html(FORUM_URL)

    posts = parse_posts(html)

    inserted = 0

    for post in posts:

        text = clean(post.get_text("\n"))

        supergroup_name = extract_supergroup(text)
        shard = extract_shard(text)
        base_code = extract_base_code(text)
        category = extract_category(text)

        if not supergroup_name:
            print("SKIPPED POST - MISSING supergroup_name")
            continue

        if not shard:
            print("SKIPPED POST - MISSING shard")
            continue

        if not base_code:
            print("SKIPPED POST - MISSING base_code")
            continue

        if not category:
            print("SKIPPED POST - MISSING category")
            continue

        print("----------------------------------------")
        print("BASE FOUND")
        print(supergroup_name)
        print(shard)
        print(base_code)
        print(category)

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
    print(f"TOTAL UPSERTED: {inserted}")
    print("============================================================")

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    scrape()
