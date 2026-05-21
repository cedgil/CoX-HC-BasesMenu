import re
import time
import requests
from bs4 import BeautifulSoup

# =========================================================
# SUPABASE
# =========================================================

SUPABASE_URL = "https://njswkwbacffyayhzivzh.supabase.co/rest/v1/scraped_bases_forum"

SUPABASE_KEY = "YOUR_SUPABASE_KEY"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

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
# SETTINGS
# =========================================================

REQUEST_DELAY = 1

# =========================================================
# HELPERS
# =========================================================

def clean_text(text):
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = text.replace("\r", "")
    text = text.strip()

    return text


def extract_field(content, label):

    if label == "*":
        return ""

    pattern = rf"{re.escape(label)}\s*(.+)"

    match = re.search(pattern, content, re.IGNORECASE)

    if match:
        value = match.group(1).strip()

        value = value.split("\n")[0].strip()

        return clean_text(value)

    return ""


def fetch_page(url):

    print("=" * 60)
    print("FETCHING")
    print(url)
    print("=" * 60)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    r = requests.get(url, headers=headers)

    print("STATUS:", r.status_code)

    r.raise_for_status()

    return r.text


def find_all_topic_pages(first_url):

    pages = []

    current_url = first_url

    visited = set()

    while current_url and current_url not in visited:

        visited.add(current_url)

        pages.append(current_url)

        print(f"DISCOVERED PAGE: {current_url}")

        html = fetch_page(current_url)

        soup = BeautifulSoup(html, "html.parser")

        next_link = soup.select_one('a[rel="next"]')

        if next_link:
            current_url = next_link.get("href")
        else:
            current_url = None

        time.sleep(REQUEST_DELAY)

    return pages


def extract_posts(html):

    soup = BeautifulSoup(html, "html.parser")

    posts = soup.select("article")

    print(f"FOUND {len(posts)} POSTS")

    return posts


def parse_post(post, source):

    text = clean_text(post.get_text("\n"))

    fields = source["fields"]

    result = {
        "source_topic": source["url"],
        "source_url": source["url"],
        "source_page": None,

        "post_author": "",
        "post_date": None,

        "supergroup_name": "",
        "shard": "",
        "base_code": "",
        "category": "",

        "description": "",
        "raw_post": text
    }

    # =====================================================
    # AUTHOR
    # =====================================================

    author = post.select_one(".ipsType_break")

    if author:
        result["post_author"] = clean_text(author.get_text())

    # =====================================================
    # FIELDS
    # =====================================================

    for db_field, keyword in fields.items():

        value = extract_field(text, keyword)

        result[db_field] = value

    # =====================================================
    # REQUIRED CHECK
    # =====================================================

    required = [
        "supergroup_name",
        "shard",
        "base_code",
        "category"
    ]

    for field in required:

        if not result[field]:

            print(f"SKIPPED POST - MISSING {field}")

            return None

    return result


def upsert_entry(entry):

    query_url = (
        f"{SUPABASE_URL}"
        f"?base_code=eq.{entry['base_code']}"
        f"&shard=eq.{entry['shard']}"
    )

    r = requests.get(query_url, headers=HEADERS)

    existing = r.json()

    if existing:

        print(
            f"ALREADY EXISTS: "
            f"{entry['base_code']} "
            f"({entry['shard']})"
        )

        return

    r = requests.post(
        SUPABASE_URL,
        headers=HEADERS,
        json=entry
    )

    print(
        f"INSERTED: "
        f"{entry['supergroup_name']} "
        f"| {entry['base_code']}"
    )

    print("STATUS:", r.status_code)

    if r.status_code >= 400:
        print(r.text)


# =========================================================
# MAIN
# =========================================================

def process_source(source):

    print("\n")
    print("=" * 60)
    print("PROCESSING SOURCE")
    print(source["url"])
    print("=" * 60)

    pages = find_all_topic_pages(source["url"])

    print(f"TOTAL PAGES FOUND: {len(pages)}")

    for page_number, page_url in enumerate(pages, start=1):

        print("\n")
        print("=" * 60)
        print(f"PAGE {page_number}")
        print("=" * 60)

        html = fetch_page(page_url)

        posts = extract_posts(html)

        for post in posts:

            try:

                parsed = parse_post(post, source)

                if parsed:

                    parsed["source_page"] = page_number

                    print("-" * 40)
                    print("BASE FOUND")
                    print(parsed["supergroup_name"])
                    print(parsed["shard"])
                    print(parsed["base_code"])
                    print(parsed["category"])

                    upsert_entry(parsed)

            except Exception as e:

                print("POST ERROR")
                print(e)

        time.sleep(REQUEST_DELAY)


def main():

    print("=" * 60)
    print("SCRAPED BASES FORUM")
    print("=" * 60)

    for source in SOURCES:

        process_source(source)

    print("\n")
    print("=" * 60)
    print("DONE")
    print("=" * 60)

    input("Press ENTER to exit...")


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as e:

        print("\n")
        print("=" * 60)
        print("ERROR")
        print("=" * 60)
        print(e)

        input("Press ENTER to exit...")
