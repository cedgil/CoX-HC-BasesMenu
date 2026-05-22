import os

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

REST_BASE_URL = f"{SUPABASE_URL}/rest/v1"

TABLE_NAME = "scraped_forum_bases"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

BASE_SECTION_URL = (
    "https://forums.homecomingservers.com/forum/53-base-construction/"
)

SHARD_ALIASES = {

    "torch": "Torchbearer",
    "torchbearer": "Torchbearer",

    "excel": "Excelsior",
    "excelsior": "Excelsior",

    "ever": "Everlasting",
    "everlasting": "Everlasting",

    "reunion": "Reunion",

    "indo": "Indomitable",
    "indomitable": "Indomitable",

    "victory": "Victory"
}

CATEGORY_MAP = {

    "clubs and venues": "Clubs and Venues",
    "club": "Clubs and Venues",
    "venue": "Clubs and Venues",

    "realism": "Realism",
    "fantasy": "Fantasy",
    "arcane": "Arcane",
    "freeform": "Freeform",
    "novice": "Novice",
    "nature": "Nature",
    "tech": "Sci-Tech",
    "sci": "Sci-Tech",
    "maze": "Maze",
    "floating": "Floating Islands",
    "rp": "RP"
}
