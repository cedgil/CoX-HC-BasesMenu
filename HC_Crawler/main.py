from crawler import (
    discover_topics,
    discover_topic_pages
)

from post_scraper import scrape_posts
from parser import extract_bases
from supabase import (
    base_exists,
    insert_base
)

# =========================================================
# MAIN
# =========================================================

def main():

    print("============================================================")
    print("HC FORUM BASE CRAWLER")
    print("============================================================")

    topics = discover_topics()

    total = 0

    for topic in topics:

        print("============================================================")
        print("TOPIC")
        print(topic["title"])
        print(topic["url"])
        print("============================================================")

        pages = discover_topic_pages(
            topic["url"]
        )

        for page_num, page_url in enumerate(pages, start=1):

            print("SCRAPING PAGE")
            print(page_num)
            print(page_url)

            posts = scrape_posts(page_url)

            print(f"FOUND {len(posts)} POSTS")

            for post in posts:

                bases = extract_bases(
                    post_text=post["raw_post"],
                    topic_title=topic["title"],
                    topic_url=topic["url"],
                    page_number=page_num,
                    author=post.get("author")
                )

                for base in bases:

                    print(base)

                    if not base.get("base_code"):
                        continue

                    if base_exists(base["base_code"]):

                        print("ALREADY EXISTS")
                        continue

                    ok = insert_base(base)

                    if ok:

                        total += 1

                        print("INSERTED")

                    else:

                        print("FAILED")

    print("============================================================")
    print("DONE")
    print(f"TOTAL: {total}")
    print("============================================================")

# =========================================================

if __name__ == "__main__":
    main()
