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

REST_BASE_URL = (
    SUPABASE_URL.split("/rest/v1")[0] + "/rest/v1"
)

API_URL = f"{REST_BASE_URL}/scraped_bases_forum"

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
# HELPERS
# =========================================================

def normalize_text(text):

    text = text.replace("\xa0", " ")
    text = text.replace("\r", "\n")

    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def clean_value(v):

    if not v:
        return ""

    v = normalize_text(v)

    v = re.sub(r"^:+", "", v)
    v = re.sub(r"\s+", " ", v)

    return v.strip()


def extract_field(text, label, all_labels):

    try:

        start = text.lower().index(label.lower())

    except ValueError:
        return ""

    start += len(label)

    end_positions = []

    for other_label in all_labels:

        if other_label == label:
            continue

        pos = text.lower().find(
            other_label.lower(),
            start
        )

        if pos != -1:
            end_positions.append(pos)

    if end_positions:
        end = min(end_positions)
        value = text[start:end]
    else:
        value = text[start:]

    value = normalize_text(value)

    # remove edited footer
    value = re.split(
        r"Edited\s+[A-Z][a-z]+\s+\d{1,2}",
        value
    )[0]

    # remove forum reactions garbage
    value = re.split(
        r"\b\d+\s+\d+\s+\d+\b",
        value
    )[0]

    return value.strip(" :-")


def valid_base_code(code):

    return bool(
        re.match(
            r"^[A-Z0-9]{2,}-\d+$",
            code.upper()
        )
    )

# =========================================================
# SUPABASE
# =========================================================

def headers():

    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

# =========================================================
# UPSERT
# =========================================================

def upsert_base(data):

    code = data["base_code"]

    check_url = (
        f"{API_URL}"
        f"?base_code=eq.{code}"
        f"&select=id"
    )

    check = requests.get(
        check_url,
        headers=headers(),
        timeout=30
    )

    print(f"CHECK STATUS: {check.status_code}")

    if check.status_code != 200:
        print("CHECK FAILED")
        print(check.text)
        return False

    exists = len(check.json()) > 0

    payload = {
        "supergroup_name": data["supergroup_name"],
        "shard": data["shard"],
        "base_code": data["base_code"],
        "category": data["category"]
    }

    # ----------------------------------------
    # UPDATE
    # ----------------------------------------

    if exists:

        update_url = (
            f"{API_URL}"
            f"?base_code=eq.{code}"
        )

        r = requests.patch(
            update_url,
            headers=headers(),
            json=payload,
            timeout=30
        )

        print(f"UPDATE STATUS: {r.status_code}")

        if r.status_code not in [200, 204]:
            print(r.text)
            return False

        print("UPDATED")
        return True

    # ----------------------------------------
    # INSERT
    # ----------------------------------------

    r = requests.post(
        API_URL,
        headers=headers(),
        json=payload,
        timeout=30
    )

    print(f"INSERT STATUS: {r.status_code}")

    if r.status_code not in [200, 201]:
        print(r.text)
        return False

    print("INSERTED")
    return True

# =========================================================
# SCRAPER
# =========================================================

def scrape_source(source):

    print("============================================================")
    print("SCRAPING")
    print(source["url"])
    print("============================================================")

    headers_req = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(
        source["url"],
        headers=headers_req,
        timeout=60
    )

    soup = BeautifulSoup(r.text, "html.parser")

    selectors = [
        ".ipsComment_content",
        ".cPost_contentWrap",
        ".ipsType_richText",
        "article"
    ]

    raw_posts = []

    for selector in selectors:

        found = soup.select(selector)

        print(f"FOUND {len(found)} POSTS USING {selector}")

        raw_posts.extend(found)

    print(f"TOTAL RAW POSTS: {len(raw_posts)}")

    inserted = 0

    for post in raw_posts:

        text = normalize_text(
            post.get_text("\n", strip=True)
        )

        if not text:
            continue

        data = {}

        all_labels = list(source["fields"].values())

        for field_name, label in source["fields"].items():

            data[field_name] = clean_value(
                extract_field(
                    text,
                    label,
                    all_labels
                )
            )

        print("--------------------------------------------------")
        print("PARSED DATA:")
        print(data)

        if not data["supergroup_name"]:
            continue

        if not data["shard"]:
            continue

        if not data["base_code"]:
            continue

        if not data["category"]:
            continue

        if not valid_base_code(data["base_code"]):
            continue

        print("----------------------------------------")
        print("BASE FOUND")
        print(data["supergroup_name"])
        print(data["shard"])
        print(data["base_code"])
        print(data["category"])

        ok = upsert_base(data)

        if ok:
            inserted += 1

    return inserted

# =========================================================
# MAIN
# =========================================================

def main():

    print("============================================================")
    print("SUPABASE DEBUG")
    print("============================================================")
    print(f"API_URL = {API_URL}")
    print("============================================================")

    total = 0

    for source in SOURCES:

        total += scrape_source(source)

    print("============================================================")
    print("DONE")
    print(f"TOTAL UPSERTED: {total}")
    print("============================================================")

# =========================================================

if __name__ == "__main__":
    main()
