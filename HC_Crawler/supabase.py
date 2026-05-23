import requests
from config import (
    API_URL,
    SUPABASE_KEY
)

# =========================================================

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# =========================================================

def upsert_base(base_data):

    try:

        r = requests.post(
            API_URL,
            headers=HEADERS,
            json=base_data,
            timeout=30
        )

        if r.status_code >= 400:

            print("INSERT STATUS:", r.status_code)
            print("INSERT RESPONSE:", r.text)

            return False

        print("UPSERT OK")

        return True

    except Exception as e:

        print("SUPABASE ERROR")
        print(e)

        return False
