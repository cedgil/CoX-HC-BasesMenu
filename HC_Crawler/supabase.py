import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

TABLE_NAME = "scraped_forum_bases"

# =========================================================
# FIX REST URL
# =========================================================

if "/rest/v1/" in SUPABASE_URL:

    REST_BASE_URL = (
        SUPABASE_URL.split("/rest/v1")[0]
        + "/rest/v1"
    )

elif SUPABASE_URL.endswith("/rest/v1"):

    REST_BASE_URL = SUPABASE_URL

else:

    REST_BASE_URL = (
        SUPABASE_URL
        + "/rest/v1"
    )

API_URL = f"{REST_BASE_URL}/{TABLE_NAME}"

print("============================================================")
print("SUPABASE DEBUG")
print("============================================================")
print("SUPABASE_URL =", SUPABASE_URL)
print("REST_BASE_URL =", REST_BASE_URL)
print("API_URL =", API_URL)
print("============================================================")


def headers():

    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }


def base_exists(base_code):

    r = requests.get(
        API_URL,
        headers=headers(),
        params={
            "base_code": f"eq.{base_code}",
            "select": "id",
            "limit": 1
        },
        timeout=30
    )

    if r.status_code != 200:
        print(r.status_code)
        print(r.text)
        return False

    try:
        data = r.json()
        return len(data) > 0

    except:
        return False


def insert_base(base):

    r = requests.post(
        API_URL,
        headers=headers(),
        json=base,
        timeout=30
    )

    print(r.status_code)

    if r.status_code >= 300:
        print(r.text)

    return r.status_code < 300
