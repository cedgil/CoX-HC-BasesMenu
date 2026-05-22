import requests
from bs4 import BeautifulSoup
import re

# =========================================================
# CONFIG
# =========================================================

RSS_URL = (
    "https://forums.homecomingservers.com/forum/30-base-construction.xml/?member=21918&key=22144eda58c7068450db661ddeaf347e"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124 Safari/537.36"
    )
}

MIN_YEAR = 2021

MAX_TOPIC_PAGES = 10

# =========================================================
# HELPERS
# =========================================================

def extract_year(title):

    m = re.search(r"(20\d{2})", title)

    if not m:
        return None

    return int(m.group(1))


def looks_like_base_topic(title):

    t = title.lower()

    keywords = [

        "base",
        "showcase",
        "contest",
        "passcode",
        "teleport",
        "teleporter",
        "hub",
        "venue",
        "rp",
        "supergroup"
    ]

    return any(k in t for k in keywords)

# =========================================================
# DISCOVER TOPICS
# =========================================================

def discover_topics():

    print("============================================================")
    print("DISCOVERING TOPICS FROM AUTH RSS")
    print("============================================================")

    found = []
    seen = set()

    r = requests.get(
        RSS_URL,
        headers=HEADERS,
        timeout=30
    )

    print("RSS STATUS:", r.status_code)

    soup = BeautifulSoup(
        r.text,
        "xml"
    )

    items = soup.find_all("item")

    print(f"RSS ITEMS: {len(items)}")

    for item in items:

        title_tag = item.find("title")
        link_tag = item.find("link")

        if not title_tag or not link_tag:
            continue

        title = title_tag.text.strip()
        url = link_tag.text.strip()

        if not looks_like_base_topic(title):
            continue

        year = extract_year(title)

        if year and year < MIN_YEAR:
            continue

        url = url.split("?")[0]

        if url in seen:
            continue

        seen.add(url)

        topic = {
            "title": title,
            "url": url
        }

        found.append(topic)

        print("FOUND TOPIC")
        print(title)
        print(url)
        print()

    print("============================================================")
    print(f"FOUND {len(found)} TOPICS")
    print("============================================================")

    return found

# =========================================================
# DISCOVER PAGES
# =========================================================

def discover_topic_pages(topic_url):

    pages = [topic_url]

    try:

        r = requests.get(
            topic_url,
            headers=HEADERS,
            timeout=30
        )

        html = r.text

        matches = re.findall(
            r"page=(\d+)",
            html
        )

        max_page = 1

        for m in matches:

            try:

                p = int(m)

                if p > max_page:
                    max_page = p

            except:
                pass

        max_page = min(
            max_page,
            MAX_TOPIC_PAGES
        )

        print(f"TOPIC PAGES: {max_page}")

        for p in range(2, max_page + 1):

            pages.append(
                f"{topic_url}?page={p}"
            )

    except Exception as e:

        print("PAGE DISCOVERY ERROR")
        print(e)

    return pages
