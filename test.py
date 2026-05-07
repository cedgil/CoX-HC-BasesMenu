import os
import requests

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_KEY"]

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}"
}

r = requests.get(url + "?select=code&limit=1", headers=headers, timeout=30)
print(r.status_code)
print(r.text)
