import json
import os
import re
import smtplib
import sys
from pathlib import Path
from email.mime.text import MIMEText
from datetime import datetime

import requests
from bs4 import BeautifulSoup

CURRENT_DIR = Path(__file__).parent
sys.path.append(str(CURRENT_DIR))

from keywords import KEYWORDS
from forums import FORUMS

KEYWORDS = [k.lower() for k in KEYWORDS]

SEEN_FILE = "HC_watcher/seen_topics.json"

CALLMEBOT_APIKEY = os.getenv("CALLMEBOT_APIKEY")
WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE")

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")


def load_seen_topics():
    if not os.path.exists(SEEN_FILE):
        return []

    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_seen_topics(seen_topics):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_topics, f, indent=2)


def send_whatsapp(message):
    if not CALLMEBOT_APIKEY or not WHATSAPP_PHONE:
        print("WhatsApp config missing")
        return

    url = "https://api.callmebot.com/whatsapp.php"

    params = {
        "phone": WHATSAPP_PHONE,
        "text": message,
        "apikey": CALLMEBOT_APIKEY,
    }

    response = requests.get(url, params=params, timeout=30)

    print(f"WhatsApp status: {response.status_code}")


def send_email(subject, body):
    if not all([
        GMAIL_USER,
        GMAIL_APP_PASSWORD,
        EMAIL_TO
    ]):
        print("Email config missing")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = EMAIL_TO

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)

    print("Email sent")


def fetch_topics():
    all_topics = []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }

    topic_pattern = re.compile(
        r'https://forums\.homecomingservers\.com/topic/(\d+)-([^/"?#]+)'
    )

    for forum in FORUMS:
        forum_name = forum["name"]
        forum_url = forum["url"]

        print(f"\nFetching: {forum_name}")

        response = requests.get(
            forum_url,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        print(f"HTTP status: {response.status_code}")
        print(f"HTML size: {len(response.text)}")

        matches = topic_pattern.findall(response.text)

        print(f"Regex matches found: {len(matches)}")

        found_links = set()

        for topic_id, slug in matches:
            link = f"https://forums.homecomingservers.com/topic/{topic_id}-{slug}"

            if link in found_links:
                continue

            found_links.add(link)

            title = (
                slug
                .replace("-", " ")
                .title()
            )

            summary = ""

            try:
                topic_response = requests.get(
                    link,
                    headers=headers,
                    timeout=30
                )

                soup = BeautifulSoup(
                    topic_response.text,
                    "html.parser"
                )

                content = soup.select_one(".ipsType_richText")

                if content:
                    summary = content.get_text(
                        " ",
                        strip=True
                    )[:500]

            except Exception as e:
                print(f"Summary fetch error: {e}")

            all_topics.append({
                "forum": forum_name,
                "title": title,
                "link": link,
                "summary": summary,
            })

            print(f"Topic found: {title}")

    return all_topics


def topic_matches(title):
    title_lower = title.lower()

    return any(
        keyword in title_lower
        for keyword in KEYWORDS
    )


def main():
    print("Fetching forum topics...")

    seen_topics = load_seen_topics()
    seen_links = {
        topic["link"]
        for topic in seen_topics
    }

    topics = fetch_topics()

    new_seen = list(seen_topics)

    total_topics_checked = 0
    total_new_topics = 0
    total_keyword_matches = 0
    whatsapp_sent = 0
    emails_sent = 0

    for topic in topics:
        total_topics_checked += 1

        title = topic["title"]
        link = topic["link"]
        forum_name = topic["forum"]

        if link in seen_links:
            continue

        total_new_topics += 1

        print(f"New topic detected: {title}")

        new_seen.append(topic)

        if topic_matches(title):
            total_keyword_matches += 1

            now = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            whatsapp_message = (
                "[Homecoming Forum]\n\n"
                f"Date: {now}\n\n"
                f"Forum: {forum_name}\n\n"
                f"Nouveau topic détecté\n\n"
                f"{title}\n\n"
                f"{link}"
            )

            email_body = (
                "[Homecoming Forum]\n\n"
                f"Date: {now}\n\n"
                f"Forum: {forum_name}\n\n"
                f"Nouveau topic détecté\n\n"
                f"Titre:\n{title}\n\n"
                f"Lien:\n{link}\n\n"
                f"Résumé:\n{topic['summary']}"
            )

            print(f"Keyword match: {title}")

            try:
                send_whatsapp(whatsapp_message)
                whatsapp_sent += 1
            except Exception as e:
                print(f"WhatsApp error: {e}")

            try:
                send_email(
                    subject=f"Homecoming Alert: {title}",
                    body=email_body
                )
                emails_sent += 1
            except Exception as e:
                print(f"Email error: {e}")

    save_seen_topics(new_seen)

    print("\n========== HC WATCHER DEBUG ==========")
    print(f"Topics checked        : {total_topics_checked}")
    print(f"New topics detected   : {total_new_topics}")
    print(f"Keyword matches       : {total_keyword_matches}")
    print(f"WhatsApp sent         : {whatsapp_sent}")
    print(f"Emails sent           : {emails_sent}")
    print("======================================\n")


if __name__ == "__main__":
    main()
