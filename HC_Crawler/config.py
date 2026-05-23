import os

# =========================================================
# SUPABASE
# =========================================================

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# accepte :
# https://xxx.supabase.co
# https://xxx.supabase.co/rest/v1

if SUPABASE_URL.endswith("/rest/v1"):

    REST_BASE_URL = SUPABASE_URL

else:

    REST_BASE_URL = f"{SUPABASE_URL}/rest/v1"

# =========================================================
# TABLE
# =========================================================

TABLE_NAME = "scraped_forum_bases"

API_URL = f"{REST_BASE_URL}/{TABLE_NAME}"

# =========================================================
# DEBUG
# =========================================================

print("============================================================")
print("SUPABASE DEBUG")
print("============================================================")
print("SUPABASE_URL =", SUPABASE_URL)
print("REST_BASE_URL =", REST_BASE_URL)
print("API_URL =", API_URL)
print("============================================================")
