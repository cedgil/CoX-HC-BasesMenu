import requests

from bs4 import BeautifulSoup

# =========================================================

def scrape_posts(topic_url):

    headers = {
        "User-Agent": "HC-BaseCrawler/1.0"
    }

    all_posts = []

    page = 1

    while True:

        url = topic_url

        if page > 1:
            url += f"?page={page}"

        print("SCRAPING", url)

        r = requests.get(
            url,
            headers=headers,
            timeout=30
        )

        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        articles = soup.select("article")

        if not articles:
            break

        print(f"FOUND {len(articles)} ARTICLES")

        for article in articles:

            raw_text = article.get_text(
                "\n",
                strip=True
            )

            if len(raw_text) < 50:
                continue

            author = None

            author_el = article.select_one(
                ".ipsType_break"
            )

            if author_el:
                author = author_el.get_text(
                    strip=True
                )

            all_posts.append({
                "raw_post": raw_text,
                "author": author,
                "page": page
            })

        next_button = soup.select_one(
            ".ipsPagination_next:not(.ipsPagination_inactive)"
        )

        if not next_button:
            break

        page += 1

        if page > 20:
            break

    return all_posts
