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
# CALLMEBOT TEST
# =========================================================

def test_callmebot():

    print("========================================")
    print("TESTING CALLMEBOT")
    print("========================================")
    print()

    # =====================================================
    # CHECK CONFIG
    # =====================================================

    if not CALLMEBOT_APIKEY:

        print("ERROR:")
        print("Missing CALLMEBOT_APIKEY")
        print()

        return

    if not WHATSAPP_PHONE:

        print("ERROR:")
        print("Missing WHATSAPP_PHONE")
        print()

        return

    print("PHONE:")
    print(WHATSAPP_PHONE)
    print()

    print("API KEY:")
    print(CALLMEBOT_APIKEY)
    print()

    # =====================================================
    # MESSAGE
    # =====================================================

    message = (
        "✅ CallMeBot test successful"
    )

    # =====================================================
    # REQUEST
    # =====================================================

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

        # =================================================
        # DEBUG OUTPUT
        # =================================================

        print("HTTP STATUS:")
        print(response.status_code)
        print()

        print("RESPONSE TEXT:")
        print(response.text)
        print()

        print("FINAL URL:")
        print(response.url)
        print()

        if response.status_code == 200:

            print("WHATSAPP SENT SUCCESSFULLY")
            print()

        else:

            print("WHATSAPP FAILED")
            print()

    except Exception as e:

        print("CALLMEBOT ERROR:")
        print(e)
        print()

# =========================================================
# EMAIL TEST
# =========================================================

def test_email():

    print("========================================")
    print("TESTING EMAIL")
    print("========================================")
    print()

    required = [

        GMAIL_USER,
        GMAIL_APP_PASSWORD,
        EMAIL_TO
    ]

    if not all(required):

        print("ERROR:")
        print("Missing email configuration")
        print()

        return

    print("FROM:")
    print(GMAIL_USER)
    print()

    print("TO:")
    print(EMAIL_TO)
    print()

    # =====================================================
    # EMAIL CONTENT
    # =====================================================

    subject = (
        "HC Watcher Email Test"
    )

    body = (
        "✅ Gmail SMTP test successful"
    )

    msg = MIMEText(body)

    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = EMAIL_TO

    # =====================================================
    # SEND
    # =====================================================

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

        print("EMAIL SENT SUCCESSFULLY")
        print()

    except Exception as e:

        print("EMAIL ERROR:")
        print(e)
        print()

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print("========================================")
    print("NOTIFICATION TEST SCRIPT")
    print("========================================")
    print()

    test_callmebot()

    print()

    test_email()

    print("========================================")
    print("TEST FINISHED")
    print("========================================")
    print()
