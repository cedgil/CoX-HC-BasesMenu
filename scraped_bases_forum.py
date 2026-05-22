import os
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ============================================================
# SUPABASE CONFIG
# ============================================================

SUPABASE_URL = os.environ["SUPABASE_URL"].strip().rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()

TABLE_NAME = "scraped_bases_forum"

# IMPORTANT :
# Tes autres scripts utilisent déjà /rest/v1
# donc on NE le rajoute PAS ici

API_URL = f"{SUPABASE_URL}/{TABLE_NAME}"

print("=" * 60)
print("SUPABASE DEBUG")
print("=" * 60)
print("SUPABASE_URL =", SUPABASE_URL)
print("API_URL =", API_URL)
print("=" * 60)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ============================================================
# SOURCES CONFIG
# ============================================================

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

# ============================================================
# BAD VALUES
# ============================================================

BAD_VALUES = [
    "",
    "n/a",
    "none",
    "unknown",
    "code, please",
    "where is the base",
    "where does this fit?",
]

# ============================================================
# HELPERS
# ============================================================

def clean_text(text):

    text = text.replace("\xa0", " ")
    text = text.replace("\u200b", "")
    text = text.strip()

    return text


def extract_field(content, keyword):

    lines = content.splitlines()

    for line in lines:

        line = clean_text(line)

        if line.lower().startswith(keyword.lower()):

            value = line[len(keyword):].strip()

            if value.lower() in BAD_VALUES:
                return None

            if not value:
                return None

            return value

    return None


def get_total_pages(url):

    print("=" * 60)
    print("DISCOVERING PAGES")
    print(url)
    print("=" * 60)

    r = requests.get(url)

    print("STATUS:", r.status_code)

    if r.status_code != 200:
        return [url]

    soup = BeautifulSoup(r.text, "html.parser")

    pages = set()
    pages.add(url)

    for a in soup.find_all("a", href=True):

        href = a["href"]

        if "/page/" in href:

            full_url = urljoin(url, href)
            full_url = full_url.split("?")[0]

            if full_url not in pages:

                pages.add(full_url)

                print("DISCOVERED PAGE:", full_url)

    return sorted(pages)


def fetch_page(url):

    print("=" * 60)
    print("FETCHING")
    print(url)
    print("=" * 60)

    r = requests.get(url)

    print("STATUS:", r.status_code)

    if r.status_code != 200:
        return None

    return BeautifulSoup(r.text, "html.parser")


def get_posts(soup):

    posts = soup.find_all("article")

    print(f"FOUND {len(posts)} POSTS")

    return posts


# =========================================================
# SUPABASE
# =========================================================

import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# IMPORTANT :
# Ta variable SUPABASE_URL contient DEJA
# l'URL REST complète de la table.
#
# Exemple :
# https://xxxxx.supabase.co/rest/v1/scraped_bases_forum

API_URL = SUPABASE_URL

def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def upsert_base(base_data):
    try:
        check_url = (
            f"{API_URL}"
            f"?base_code=eq.{base_data['base_code']}"
            f"&select=id"
        )

        check = requests.get(
            check_url,
            headers=supabase_headers(),
            timeout=30
        )

        print(f"CHECK STATUS: {check.status_code}")

        if check.text:
            print(f"CHECK RESPONSE: {check.text[:300]}")

        url = f"{API_URL}?on_conflict=base_code"

        r = requests.post(
            url,
            headers=supabase_headers(),
            json=base_data,
            timeout=30
        )

        print(f"UPSERT STATUS: {r.status_code}")

        if r.text:
            print(f"UPSERT RESPONSE: {r.text[:300]}")

        if r.status_code in [200, 201]:
            print("INSERTED")
            return True

        print("INSERT FAILED")
        return False

    except Exception as e:
        print(f"SUPABASE ERROR: {e}")
        return False


# ============================================================
# PROCESS
# ============================================================

def process_post(post, source):

    text = clean_text(post.get_text("\n"))

    fields = source["fields"]

    data = {}

    for field_name, keyword in fields.items():

        value = extract_field(text, keyword)

        data[field_name] = value

    missing = []

    for required in fields.keys():

        if not data.get(required):
            missing.append(required)

    if missing:

        for m in missing:
            print(f"SKIPPED POST - MISSING {m}")

        return

    print("-" * 40)
    print("BASE FOUND")
    print(data["supergroup_name"])
    print(data["shard"])
    print(data["base_code"])
    print(data["category"])

    exists = base_exists(
        data["base_code"],
        data["shard"]
    )

    if exists:

        print(
            f"ALREADY EXISTS: "
            f'{data["base_code"]} ({data["shard"]})'
        )

        return

    success = insert_base({
        "supergroup_name": data["supergroup_name"],
        "shard": data["shard"],
        "base_code": data["base_code"],
        "category": data["category"],
        "source_url": source["url"]
    })

    if success:
        print("SUCCESSFULLY INSERTED")


def process_source(source):

    print("=" * 60)
    print("PROCESSING SOURCE")
    print(source["url"])
    print("=" * 60)

    pages = get_total_pages(source["url"])

    print(f"TOTAL PAGES FOUND: {len(pages)}")

    for index, page_url in enumerate(pages, start=1):

        print("=" * 60)
        print(f"PAGE {index}")
        print("=" * 60)

        soup = fetch_page(page_url)

        if not soup:
            continue

        posts = get_posts(soup)

        for post in posts:

            process_post(post, source)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("SCRAPED BASES FORUM")
    print("=" * 60)

    for source in SOURCES:

        process_source(source)

    print("=" * 60)
    print("DONE")
    print("=" * 60)


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print("\nSTOPPED")

    except Exception as e:

        print("=" * 60)
        print("ERROR")
        print("=" * 60)
        print(str(e))

        sys.exit(1)
