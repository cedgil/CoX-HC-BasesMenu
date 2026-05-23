import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

RSS_URL = "https://forums.homecomingservers.com/forum/30-base-construction.xml/?member=21918&key=22144eda58c7068450db661ddeaf347e"

HEADERS = {
    "User-Agent": "HC-BaseCrawler/1.0"
}

BASE_URL = "https://forums.homecomingservers.com"


def discover_topics():

    print("============================================================")
    print("DISCOVERING TOPICS FROM AUTH RSS")
    print("============================================================")

    r = requests.get(
        RSS_URL,
        headers=HEADERS,
        timeout=30
    )

    print("RSS STATUS:", r.status_code)

    r.raise_for_status()

    soup = BeautifulSoup(
        r.text,
        "html.parser"
    )

    items = soup.find_all("item")

    print("RSS ITEMS:", len(items))

    topics = []

    for item in items:

        title_tag = item.find("title")
        link_tag = item.find("link")

        if not title_tag or not link_tag:
            continue

        title = title_tag.get_text(strip=True)

        raw_link = link_tag.get_text(strip=True)

        if not raw_link:
            continue

        if raw_link.startswith("/"):
            raw_link = urljoin(BASE_URL, raw_link)

        if not raw_link.startswith("http"):
            continue

        if "/topic/" not in raw_link:
            continue

        topic = {
            "title": title,
            "url": raw_link
        }

        print("FOUND TOPIC")
        print(title)
        print(raw_link)
        print()

        topics.append(topic)

    print("============================================================")
    print(f"FOUND {len(topics)} TOPICS")
    print("============================================================")

    return topics
