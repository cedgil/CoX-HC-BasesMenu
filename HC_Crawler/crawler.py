import requests

from bs4 import BeautifulSoup

from config import BASE_SECTION_URL

# =========================================================

def discover_topics():

    headers = {
        "User-Agent": "HC-BaseCrawler/1.0"
    }

    r = requests.get(
        BASE_SECTION_URL,
        headers=headers,
        timeout=30
    )

    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    topics = []

    for a in soup.select("a[href*='/topic/']"):

        href = a.get("href", "")

        if "/topic/" not in href:
            continue

        if href.startswith("/"):
            href = (
                "https://forums.homecomingservers.com"
                + href
            )

        title = a.get_text(" ", strip=True)

        topics.append({
            "title": title,
            "url": href.split("?")[0]
        })

    unique = {}

    for t in topics:
        unique[t["url"]] = t

    return list(unique.values())
