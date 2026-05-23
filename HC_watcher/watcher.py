import json
import os
import smtplib
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

FORUM_URL = "https://forums.homecomingservers.com/forum/30-base-construction/"

KEYWORDS = [
    keyword.strip().lower()
    for keyword in os.getenv(
        "KEYWORDS",
        "teleporter,lighting,editor,contest"
    ).split(",")
]

SEEN_FILE = "automation/homecoming_watcher/seen_topics.json"

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

    print("WhatsApp status:", response.status_code)


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
    response = requests.get(FORUM_URL, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    topics = []

    for topic in soup.select("li.ipsDataItem"):
        title_link = topic.select_one("a[data-linktype='link']")

        if not title_link:
            continue

        title = title_link.get_text(strip=True)
        link = title_link.get("href")

        if not link:
            continue

        topics.append({
            "title": title,
            "link": link,
        })

    return topics


def topic_matches(title):
    title_lower = title.lower()

    return any(keyword in title_lower for keyword in KEYWORDS)


def main():
    print("Fetching forum topics...")

    seen_topics = load_seen_topics()
    seen_links = {topic["link"] for topic in seen_topics}

    topics = fetch_topics()

    new_seen = list(seen_topics)

    found_matches = 0

    for topic in topics:
        title = topic["title"]
        link = topic["link"]

        if link in seen_links:
            continue

        print("New topic:", title)

        new_seen.append(topic)

        if topic_matches(title):
            found_matches += 1

            message = (
                "[Homecoming Forum]\n\n"
                f"Nouveau topic détecté\n\n"
                f"{title}\n\n"
                f"{link}"
            )

            print("Keyword match found")

            send_whatsapp(message)

            send_email(
                subject=f"Homecoming Alert: {title}",
                body=message
            )

    save_seen_topics(new_seen)

    print(f"Done. {found_matches} matching topics found.")


if __name__ == "__main__":
    main()
