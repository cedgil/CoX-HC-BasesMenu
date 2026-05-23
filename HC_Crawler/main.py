from crawler import discover_topics
from post_scraper import scrape_posts
from parser import extract_bases
from supabase import upsert_base

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

        try:

            posts = scrape_posts(topic["url"])

            print(f"FOUND {len(posts)} POSTS")

            for post in posts:

                bases = extract_bases(
                    post_text=post["content"],
                    topic_title=topic["title"],
                    topic_url=topic["url"],
                    post_author=post.get("author")
                )

                for base in bases:

                    print(base)

                    ok = upsert_base(base)

                    if ok:
                        total += 1

        except Exception as e:

            print("TOPIC ERROR")
            print(e)

    print("============================================================")
    print("DONE")
    print(f"TOTAL: {total}")
    print("============================================================")

# =========================================================

if __name__ == "__main__":
    main()
