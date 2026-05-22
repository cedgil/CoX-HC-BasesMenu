import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_FORUM_URL = (
    "https://forums.homecomingservers.com/forum/30-base-construction/"
)

HEADERS = {
    "User-Agent": "HC-Forum-Crawler/1.0"
}


def fetch_page(url):

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    r.raise_for_status()

    return r.text


def extract_topics_from_page(html):

    soup = BeautifulSoup(html, "html.parser")

    topics = []

    seen = set()

    # =====================================================
    # NEW FORUM SELECTORS
    # =====================================================

    selectors = [

        "a[data-linktype='link']",

        ".ipsDataItem_title a",

        "a.ipsDataItem_title",

        "h4.ipsDataItem_title a",

        "article a"

    ]

    for selector in selectors:

        links = soup.select(selector)

        print(f"SELECTOR {selector} -> {len(links)}")

        for link in links:

            href = link.get("href", "")

            title = link.get_text(" ", strip=True)

            if not href:
                continue

            if "/topic/" not in href:
                continue

            full_url = urljoin(
                "https://forums.homecomingservers.com",
                href
            )

            slug = href.split("/topic/")[-1]

            if slug in seen:
                continue

            seen.add(slug)

            topics.append({
                "title": title,
                "url": full_url
            })

    return topics


def crawl_topics():

    print("============================================================")
    print("CRAWLING BASE CONSTRUCTION FORUM")
    print("============================================================")

    html = fetch_page(BASE_FORUM_URL)

    topics = extract_topics_from_page(html)

    print(f"FOUND {len(topics)} TOPICS")

    for t in topics[:10]:
        print("-", t["title"])

    return topics
