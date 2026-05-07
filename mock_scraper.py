import os
import requests
from datetime import datetime

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

print("Secrets chargés OK")

def main():
    url = f"{SUPABASE_URL}?on_conflict=code"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation"
    }

    data = [{
        "code": "TEST-0001",
        "server": "Everlasting",
        "name": "Mock Base",
        "style": "",
        "sources": ["mock"],
        "updated_at": datetime.utcnow().isoformat()
    }]

    print("Pushing 1 mock row to Supabase...")
    r = requests.post(url, headers=headers, json=data, timeout=30)

    print("Status:", r.status_code)
    print("Response:", r.text)

    r.raise_for_status()

if __name__ == "__main__":
    main()
