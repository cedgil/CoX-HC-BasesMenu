import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import json

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
        "Chrome/124.0 Safari/537.36"
    )
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

            print("STATUS:", r.status_code)

            html = r.text

            print("HTML SIZE:", len(html))

            # =====================================================
            # FALLBACK DEBUG
            # =====================================================

            if "/topic/" not in html:

                print("NO /topic/ FOUND IN HTML")
                print(html[:500])
                continue

            # =====================================================
            # RAW REGEX EXTRACTION
            # =====================================================

            matches = re.findall(

                r'href="([^"]+/topic/\d+[^"]*)".*?>(.*?)<',

                html,

                re.IGNORECASE | re.DOTALL
            )

            print("RAW MATCHES:", len(matches))

            for href, raw_title in matches:

                title = BeautifulSoup(
                    raw_title,
                    "html.parser"
                ).get_text(" ", strip=True)

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

                full_url = full_url.split("#")[0]
                full_url = full_url.split("?do=")[0]

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

        html = r.text

        page_numbers = re.findall(
            r"page=(\d+)",
            html
        )

        max_page = 1

        for p in page_numbers:

            try:

                p = int(p)

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
                topic_url + f"?page={p}"
            )

    except Exception as e:

        print("PAGE DISCOVERY ERROR")
        print(e)

    return pages
