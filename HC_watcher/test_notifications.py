import os
import smtplib
from email.mime.text import MIMEText

import requests


# =========================================================
# ENV VARIABLES
# =========================================================

CALLMEBOT_APIKEY = os.getenv(
    "CALLMEBOT_APIKEY"
)

WHATSAPP_PHONE = os.getenv(
    "WHATSAPP_PHONE"
)

GMAIL_USER = os.getenv(
    "GMAIL_USER"
)

GMAIL_APP_PASSWORD = os.getenv(
    "GMAIL_APP_PASSWORD"
)

EMAIL_TO = os.getenv(
    "EMAIL_TO"
)

# =========================================================
# WHATSAPP TEST
# =========================================================

def test_callmebot():

    print("========================================")
    print("TESTING CALLMEBOT")
    print("========================================")

    if not CALLMEBOT_APIKEY:

        print("Missing CALLMEBOT_APIKEY")
        return

    if not WHATSAPP_PHONE:

        print("Missing WHATSAPP_PHONE")
        return

    message = (
        "✅ CallMeBot test successful"
    )

    url = (
        "https://api.callmebot.com/whatsapp.php"
    )

    params = {

        "phone": WHATSAPP_PHONE,
        "text": message,
        "apikey": CALLMEBOT_APIKEY,
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=30
        )

        print(
            f"HTTP Status: "
            f"{response.status_code}"
        )

        print(response.text)

    except Exception as e:

        print(f"CallMeBot error: {e}")

# =========================================================
# EMAIL TEST
# =========================================================

def test_email():

    print("========================================")
    print("TESTING EMAIL")
    print("========================================")

    required = [

        GMAIL_USER,
        GMAIL_APP_PASSWORD,
        EMAIL_TO
    ]

    if not all(required):

        print("Missing email configuration")
        return

    subject = "HC Watcher Email Test"

    body = (
        "✅ Gmail SMTP test successful"
    )

    msg = MIMEText(body)

    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = EMAIL_TO

    try:

        with smtplib.SMTP(
            "smtp.gmail.com",
            587
        ) as server:

            server.starttls()

            server.login(
                GMAIL_USER,
                GMAIL_APP_PASSWORD
            )

            server.send_message(msg)

        print("Email sent successfully")

    except Exception as e:

        print(f"Email error: {e}")

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    test_callmebot()

    print()

    test_email()
