import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

BASE_FORUM_URL = (
    "https://forums.homecomingservers.com/forum/53-base-construction/"
)

MIN_YEAR = 2021

MAX_TOPIC_PAGES = 10

HEADERS = {
    "User-Agent": "HC-BaseCrawler/1.0"
}

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
        "passcode",
        "showcase",
        "contest",
        "sg",
        "supergroup",
        "teleport",
        "teleporter",
        "hub",
        "roleplay",
        "rp",
        "venue"
    ]

    return any(k in t for k in keywords)

# =========================================================
# DISCOVER TOPICS
# =========================================================

def discover_topics():

    topics = []

    print("============================================================")
    print("DISCOVERING TOPICS")
    print("============================================================")

    for forum_page in range(1, 6):

        if forum_page == 1:

            url = BASE_FORUM_URL

        else:

            url = (
                BASE_FORUM_URL
                + f"?page={forum_page}"
            )

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

            links = soup.select(
                "a[data-linktype='link']"
            )

            for link in links:

                href = link.get("href", "")
                title = link.get_text(" ", strip=True)

                if not href:
                    continue

                if "/topic/" not in href:
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

                topic = {
                    "title": title,
                    "url": full_url
                }

                if topic not in topics:

                    topics.append(topic)

                    print("FOUND TOPIC:")
                    print(title)
                    print(full_url)
                    print()

        except Exception as e:

            print("ERROR:")
            print(e)

    print("============================================================")
    print(f"FOUND {len(topics)} TOPICS")
    print("============================================================")

    return topics

# =========================================================
# DISCOVER TOPIC PAGES
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

        pagination_links = soup.select(
            "a[href*='page=']"
        )

        max_page = 1

        for a in pagination_links:

            href = a.get("href", "")

            m = re.search(
                r"page=(\d+)",
                href
            )

            if not m:
                continue

            p = int(m.group(1))

            if p > max_page:
                max_page = p

        max_page = min(
            max_page,
            MAX_TOPIC_PAGES
        )

        for p in range(2, max_page + 1):

            pages.append(
                topic_url + f"?page={p}"
            )

    except Exception as e:

        print("PAGE DISCOVERY ERROR:")
        print(e)

    return pages
