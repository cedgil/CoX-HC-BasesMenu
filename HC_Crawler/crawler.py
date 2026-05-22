import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

# =========================================================
# CONFIG
# =========================================================

BASE_FORUM_URL = (
    "https://forums.homecomingservers.com/forum/53-base-construction/"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124 Safari/537.36"
    )
}

MAX_FORUM_PAGES = 5

MIN_YEAR = 2021

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
    print("DISCOVERING TOPICS")
    print("============================================================")

    found = []
    seen = set()

    for page in range(1, MAX_FORUM_PAGES + 1):

        if page == 1:
            url = BASE_FORUM_URL
        else:
            url = f"{BASE_FORUM_URL}?page={page}"

        print(url)

        try:

            r = requests.get(
                url,
                headers=HEADERS,
                timeout=30
            )

            print("STATUS:", r.status_code)

            soup = BeautifulSoup(
                r.text,
                "html.parser"
            )

            # =====================================================
            # IPS topic links
            # =====================================================

            links = soup.select("a[href*='/topic/']")

            print("RAW TOPIC LINKS:", len(links))

            for a in links:

                href = a.get("href")

                if not href:
                    continue

                full_url = urljoin(
                    "https://forums.homecomingservers.com",
                    href
                )

                title = a.get_text(
                    strip=True
                )

                if not title:
                    continue

                if not looks_like_base_topic(title):
                    continue

                year = extract_year(title)

                if year and year < MIN_YEAR:
                    continue

                # remove page params
                full_url = full_url.split("?")[0]

                if full_url in seen:
                    continue

                seen.add(full_url)

                topic = {
                    "title": title,
                    "url": full_url
                }

                found.append(topic)

                print("FOUND TOPIC")
                print(title)
                print(full_url)
                print()

        except Exception as e:

            print("DISCOVERY ERROR")
            print(e)

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

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        max_page = 1

        page_links = soup.select(
            "a[href*='page=']"
        )

        for a in page_links:

            href = a.get("href", "")

            m = re.search(
                r"page=(\d+)",
                href
            )

            if not m:
                continue

            try:

                p = int(m.group(1))

                if p > max_page:
                    max_page = p

            except:
                pass

        max_page = min(max_page, 10)

        print(f"TOPIC PAGES: {max_page}")

        for p in range(2, max_page + 1):

            pages.append(
                f"{topic_url}?page={p}"
            )

    except Exception as e:

        print("PAGE DISCOVERY ERROR")
        print(e)

    return pages
