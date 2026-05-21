import requests
import re
import time
from bs4 import BeautifulSoup

# ============================================================
# SUPABASE
# ============================================================

SUPABASE_URL = "https://njswkwbacffyayhzivzh.supabase.co/rest/v1/scraped_bases_forum"

SUPABASE_KEY = "TON_SUPABASE_KEY"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ============================================================
# SOURCES
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
# BAD VALUES / TEMPLATE FILTER
# ============================================================

BAD_VALUES = [
    "Shard/Server:",
    "Base Code:",
    "Base Owner:",
    "Code, please",
    "where is the base",
    "Your sg here",
    "The shard it is located on:",
    "The passcode for entry:",
    "The category your base is entering under:",
    "Contributing builders’ names or Global handles:",
    "Special or Hidden Features, if any:"
]

# ============================================================
# HELPERS
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = text.replace("\n", " ")
    text = text.replace("\r", " ")

    return " ".join(text.split()).strip()


def extract_field(content, keyword):
    pattern = rf"{re.escape(keyword)}\s*(.+)"

    match = re.search(pattern, content, re.IGNORECASE)

    if not match:
        return None

    value = clean_text(match.group(1))

    if value in BAD_VALUES:
        return None

    return value


# ============================================================
# DISCOVER PAGES
# ============================================================

def discover_pages(base_url):
    pages = [base_url]

    print("=" * 60)
    print("FETCHING")
    print(base_url)
    print("=" * 60)

    r = requests.get(base_url)

    print("STATUS:", r.status_code)

    soup = BeautifulSoup(r.text, "html.parser")

    for a in soup.find_all("a", href=True):

        href = a["href"]

        if "/page/" in href and base_url.split("/topic/")[0] in href:

            clean = href.split("?")[0]

            if clean not in pages:
                pages.append(clean)

                print("DISCOVERED PAGE:", clean)

    print("TOTAL PAGES FOUND:", len(pages))

    return pages


# ============================================================
# SUPABASE CHECK
# ============================================================

def base_exists(base_code, shard):

    params = {
        "base_code": f"eq.{base_code}",
        "shard": f"eq.{shard}",
        "select": "id"
    }

    r = requests.get(
        SUPABASE_URL,
        headers=HEADERS,
        params=params
    )

    print("CHECK STATUS:", r.status_code)
    print("CHECK RESPONSE:", r.text)

    if r.status_code != 200:
        return False

    data = r.json()

    return len(data) > 0


# ============================================================
# INSERT
# ============================================================

def insert_base(data):

    payload = {
        "supergroup_name": data["supergroup_name"],
        "shard": data["shard"],
        "base_code": data["base_code"],
        "category": data["category"],
        "source_url": data["source_url"]
    }

    r = requests.post(
        SUPABASE_URL,
        headers=HEADERS,
        json=payload
    )

    print("UPSERT STATUS:", r.status_code)
    print("UPSERT RESPONSE:", r.text)


# ============================================================
# SCRAPE PAGE
# ============================================================

def scrape_page(url, field_map):

    print("=" * 60)
    print("FETCHING")
    print(url)
    print("=" * 60)

    r = requests.get(url)

    print("STATUS:", r.status_code)

    soup = BeautifulSoup(r.text, "html.parser")

    posts = soup.find_all("article")

    print("FOUND", len(posts), "POSTS")

    for post in posts:

        text = clean_text(post.get_text("\n"))

        supergroup_name = extract_field(
            text,
            field_map["supergroup_name"]
        )

        shard = extract_field(
            text,
            field_map["shard"]
        )

        base_code = extract_field(
            text,
            field_map["base_code"]
        )

        category = extract_field(
            text,
            field_map["category"]
        )

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

        print("-" * 40)
        print("BASE FOUND")
        print(supergroup_name)
        print(shard)
        print(base_code)
        print(category)

        exists = base_exists(base_code, shard)

        if exists:
            print(f"ALREADY EXISTS: {base_code} ({shard})")
            continue

        insert_base({
            "supergroup_name": supergroup_name,
            "shard": shard,
            "base_code": base_code,
            "category": category,
            "source_url": url
        })

        print("INSERTED")

        time.sleep(0.25)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("SCRAPED BASES FORUM")
    print("=" * 60)

    for source in SOURCES:

        print("=" * 60)
        print("PROCESSING SOURCE")
        print(source["url"])
        print("=" * 60)

        pages = discover_pages(source["url"])

        page_number = 1

        for page in pages:

            print("=" * 60)
            print(f"PAGE {page_number}")
            print("=" * 60)

            scrape_page(
                page,
                source["fields"]
            )

            page_number += 1

    print("=" * 60)
    print("DONE")
    print("=" * 60)


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":
    main()
