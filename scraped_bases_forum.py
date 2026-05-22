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
    "https://forums.homecomingservers.com/topic/65389-2025-base-building-contest/"
)

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

SUPABASE_TABLE = "scraped_bases_forum"

NOW = datetime.now(timezone.utc)

# =========================================================
# FIX REST URL
# =========================================================

if "/rest/v1/" in SUPABASE_URL:
    REST_BASE_URL = SUPABASE_URL.split("/rest/v1")[0] + "/rest/v1"

elif SUPABASE_URL.endswith("/rest/v1"):
    REST_BASE_URL = SUPABASE_URL

else:
    REST_BASE_URL = SUPABASE_URL + "/rest/v1"

API_URL = f"{REST_BASE_URL}/{SUPABASE_TABLE}"

# =========================================================
# DEBUG
# =========================================================

print("============================================================")
print("SUPABASE DEBUG")
print("============================================================")
print(f"API_URL = {API_URL}")
print("============================================================")

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

VALID_SHARDS = [
    "Everlasting",
    "Excelsior",
    "Torchbearer",
    "Indomitable",
    "Victory",
    "Reunion"
]

VALID_CATEGORIES = [
    "Arcane",
    "Tech",
    "Roleplay",
    "RP",
    "Transit",
    "Hub",
    "Misc",
    "Other",
    "Realism",
    "Utilities",
    "Maze"
]

# =========================================================
# CLEAN
# =========================================================

def clean(text):

    if not text:
        return ""

    text = text.replace("\xa0", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()

# =========================================================
# EXTRACTORS
# =========================================================

def extract_base_code(text):

    m = re.search(
        r"\b([A-Z0-9]{2,}-\d{3,})\b",
        text,
        re.IGNORECASE
    )

    if m:
        return m.group(1).upper()

    return None


def extract_shard(text):

    for shard in VALID_SHARDS:

        if re.search(
            rf"\b{re.escape(shard)}\b",
            text,
            re.IGNORECASE
        ):
            return shard

    return None


def extract_category(text):

    lower = text.lower()

    for category in VALID_CATEGORIES:

        if category.lower() in lower:
            return category

    return None


def extract_supergroup_name(text):

    patterns = [

        r"BASE FOUND\s+(.+?)\s+(Everlasting|Excelsior|Torchbearer|Indomitable|Victory|Reunion)",

        r"Supergroup Name[:\s]+(.+?)(?:Shard|Server|Passcode|Base Code)",

        r"Name[:\s]+(.+?)(?:Shard|Server|Passcode|Base Code)"
    ]

    for pattern in patterns:

        m = re.search(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL
        )

        if m:

            value = clean(m.group(1))

            if len(value) > 2:
                return value

    return None

# =========================================================
# SUPABASE
# =========================================================

def base_exists(base_code):

    url = API_URL

    params = {
        "select": "id",
        "base_code": f"eq.{base_code}",
        "limit": 1
    }

    r = requests.get(
        url,
        headers=SUPABASE_HEADERS,
        params=params,
        timeout=30
    )

    if r.status_code != 200:
        print("CHECK STATUS:", r.status_code)
        print("CHECK RESPONSE:", r.text)
        return False

    data = r.json()

    return len(data) > 0


def upsert_entry(entry):

    params = {
        "on_conflict": "base_code"
    }

    r = requests.post(
        API_URL,
        headers=SUPABASE_HEADERS,
        params=params,
        json=[entry],
        timeout=30
    )

    print("UPSERT STATUS:", r.status_code)

    if r.text:
        print("UPSERT RESPONSE:", r.text[:500])

    return r.status_code in [200, 201]

# =========================================================
# MAIN
# =========================================================

def main():

    r = requests.get(
        FORUM_URL,
        headers=HEADERS,
        timeout=60
    )

    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    posts = []

    selectors = [
        ".ipsComment_content",
        ".cPost_contentWrap",
        ".ipsType_richText",
        "article"
    ]

    for selector in selectors:

        found = soup.select(selector)

        print(f"FOUND {len(found)} POSTS USING {selector}")

        posts.extend(found)

    print(f"TOTAL RAW POSTS: {len(posts)}")
    print("============================================================")

    inserted = 0

    for idx, post in enumerate(posts):

        text = post.get_text("\n", strip=True)

        text = clean(text)

        print("--------------------------------------------------")
        print(f"POST #{idx + 1}")
        print("--------------------------------------------------")
        print(text[:2000])
        print()

        if len(text) < 100:
            print("TOO SHORT")
            continue

        base_code = extract_base_code(text)
        supergroup_name = extract_supergroup_name(text)
        shard = extract_shard(text)
        category = extract_category(text)

        print("PARSED:")
        print("supergroup_name =", supergroup_name)
        print("shard =", shard)
        print("base_code =", base_code)
        print("category =", category)

        if not base_code:
            print("SKIP: no base code")
            continue

        if not supergroup_name:
            print("SKIP: no supergroup name")
            continue

        if not shard:
            print("SKIP: no shard")
            continue

        if not category:
            print("SKIP: no category")
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
    print(f"TOTAL UPSERTED: {inserted}")
    print("============================================================")

# =========================================================

if __name__ == "__main__":
    main()
