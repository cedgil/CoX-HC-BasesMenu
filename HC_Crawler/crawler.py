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
    "User-Agent": "HC-BaseCrawler/2.0"
}

MIN_YEAR = 2021

MAX_FORUM_PAGES = 5

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
        "sg",
        "supergroup",
        "venue",
        "rp"
    ]

    return any(k in t for k in keywords)

# =========================================================
# DISCOVER TOPICS
# =========================================================

def discover_topics():

    found = []

    print("============================================================")
    print("DISCOVERING TOPICS")
    print("============================================================")

    for page in range(1, MAX_FORUM_PAGES + 1):

        if page == 1:

            url = BASE_FORUM_URL

        else:

            url = BASE_FORUM_URL + f"?page={page}"

        print(url)

        try:

            r = requests.get(
                url,
                headers=HEADERS,
                timeout=30
            )

            soup = BeautifulSoup(
                r.text,
                "html.parser"
            )

            # =====================================================
            # IPS topic links
            # =====================================================

            topic_links = soup.select(
                "a[href*='/topic/']"
            )

            print(f"RAW TOPIC LINKS: {len(topic_links)}")

            for a in topic_links:

                href = a.get("href", "")
                title = a.get_text(" ", strip=True)

                if not href:
                    continue

                if "/topic/" not in href:
                    continue

                if not title:
                    continue

                if not looks_like_base_topic(title):
                    continue

                year = extract_year(title)

                if year and year < MIN_YEAR:
                    continue

                full_url = urljoin(
                    "https://forums.homecomingservers.com",
                    href
                )

                # remove anchors
                full_url = full_url.split("?do=")[0]
                full_url = full_url.split("#")[0]

                topic = {
                    "title": title,
                    "url": full_url
                }

                if topic not in found:

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

        links = soup.select(
            "a[href*='page=']"
        )

        for a in links:

            href = a.get("href", "")

            m = re.search(
                r"page=(\d+)",
                href
            )

            if not m:
                continue

            page_num = int(m.group(1))

            if page_num > max_page:
                max_page = page_num

        # protection anti-boucle infinie
        max_page = min(
            max_page,
            MAX_TOPIC_PAGES
        )

        print(f"TOPIC PAGES: {max_page}")

        for p in range(2, max_page + 1):

            pages.append(
                topic_url + f"?page={p}"
            )

    except Exception as e:

        print("PAGE DISCOVERY ERROR")
        print(e)

    return pages
