from crawler import discover_topics

from post_scraper import scrape_posts

from parser import parse_post

from supabase import upsert_base

# =========================================================

def looks_like_base(data):

    return (
        data["supergroup_name"]
        and data["shard"]
        and data["base_code"]
    )

# =========================================================

def main():

    topics = discover_topics()

    print(f"FOUND {len(topics)} TOPICS")

    total = 0

    for topic in topics:

        print("=" * 60)
        print(topic["title"])
        print(topic["url"])
        print("=" * 60)

        posts = scrape_posts(
            topic["url"]
        )

        for post in posts:

            parsed = parse_post(
                post["raw_post"]
            )

            if not looks_like_base(parsed):
                continue

            payload = {
                **parsed,

                "source_topic": topic["title"],

                "source_url": topic["url"],

                "source_page": post["page"],

                "post_author": post["author"],

                "raw_post": post["raw_post"]
            }

            print(payload)

            upsert_base(payload)

            total += 1

    print("=" * 60)
    print("DONE")
    print("TOTAL:", total)
    print("=" * 60)

# =========================================================

if __name__ == "__main__":
    main()
