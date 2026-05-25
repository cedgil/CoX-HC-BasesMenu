#!/usr/bin/env python3

import os
import re
import requests
from collections import defaultdict

# =========================================================
# CONFIG
# =========================================================

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

SUPABASE_TABLE = "scraped_bases_forum"

MAX_CATEGORY_LENGTH = 45

# =========================================================
# API
# =========================================================

if "/rest/v1/" in SUPABASE_URL:

    REST_BASE_URL = (
        SUPABASE_URL
        .split("/rest/v1")[0]
        + "/rest/v1"
    )

elif SUPABASE_URL.endswith("/rest/v1"):

    REST_BASE_URL = SUPABASE_URL

else:

    REST_BASE_URL = SUPABASE_URL + "/rest/v1"

API_URL = f"{REST_BASE_URL}/{SUPABASE_TABLE}"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

# =========================================================
# CATEGORY NORMALIZATION
# =========================================================

CATEGORY_ALIASES = {

    # =====================================================
    # FREEFORM
    # =====================================================

    "freeform": "Freeform",
    "free form": "Freeform",
    "free-form": "Freeform",

    # =====================================================
    # TECH
    # =====================================================

    "tech sci-fi": "Tech/Sci-Fi",
    "tech / sci-fi": "Tech/Sci-Fi",
    "tech/sci-fi": "Tech/Sci-Fi",
    "sci-fi": "Tech/Sci-Fi",
    "scifi": "Tech/Sci-Fi",

    # =====================================================
    # FANTASY
    # =====================================================

    "fantasy arcane": "Fantasy/Arcane",
    "fantasy/arcane": "Fantasy/Arcane",

    # =====================================================
    # OTHER / MISC
    # =====================================================

    "other misc": "Other/Misc",
    "other / misc": "Other/Misc",
    "other / misc.": "Other/Misc",
    "other miscellaneous": "Other/Misc",
    "other / miscellaneous": "Other/Misc",
    "misc": "Other/Misc",
    "misc.": "Other/Misc",
    "miscellaneous": "Other/Misc",

    # =====================================================
    # CLUBS
    # =====================================================

    "clubs and venues": "Clubs and Venues",
    "club and venues": "Clubs and Venues",

    # =====================================================
    # REALISM
    # =====================================================

    "realism": "Realism",

    # =====================================================
    # FUNCTIONAL
    # =====================================================

    "functional": "Functional",

    # =====================================================
    # SCIENCE
    # =====================================================

    "science": "Science",

    # =====================================================
    # SEASONAL
    # =====================================================

    "seasonal": "Seasonal",

    # =====================================================
    # SUPERGROUP
    # =====================================================

    "supergroup headquarters": "Supergroup Headquarters",

    # =====================================================
    # CONTEST CATEGORIES
    # =====================================================

    "multipurpose base under 7k items":
        "Multipurpose Base Under 7K",

    "multipurpose base under 7k":
        "Multipurpose Base Under 7K",

    "multipurpose base over 7k items":
        "Multipurpose Base Over 7K",

    "multipurpose base over 7k":
        "Multipurpose Base Over 7K",

    "rp base under 7k items":
        "RP Base Under 7K",

    "rp base under 7k":
        "RP Base Under 7K",

    "rp base over 7k items":
        "RP Base Over 7K",

    "rp base over 7k":
        "RP Base Over 7K",

    "decorated utility base under 7k items":
        "Decorated Utility Base Under 7K",

    "decorated utility base under 7k":
        "Decorated Utility Base Under 7K",

    "decorated utility base over 7k items":
        "Decorated Utility Base Over 7K",

    "decorated utility base over 7k":
        "Decorated Utility Base Over 7K",

    "utility under 7000":
        "Decorated Utility Base Under 7K",

    "utility way under 7000":
        "Decorated Utility Base Under 7K",

    "novice":
        "Novice"
}

# =========================================================
# HELPERS
# =========================================================

def clean(text):

    if not text:
        return ""

    text = text.replace("\u00a0", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_category(category):

    if not category:
        return "Other/Misc"

    category = clean(category)

    lowered = category.lower()

    # =====================================================
    # AGGRESSIVE CLEANING
    # =====================================================

    STOP_WORDS = [

        "special or hidden",
        "is flight or teleportation",
        "additional info",
        "must-see",
        "edited",
        "posted",
        "definitely a base",
        "for those interested",
        "which, i list",
        "haven't put this",
        "i can't show",
        "its a small but functional",
        "the base is completely open",
        "must have water effects",
        "water looks terrible",
        "there are 27 invisible",
        "area of interest",
        "so, clubs and venues",
        "clubs and venues are for",
        "home and living design"
    ]

    for stop in STOP_WORDS:

        idx = lowered.find(stop)

        if idx > 0:

            category = category[:idx].strip()

            lowered = category.lower()

    # =====================================================
    # REMOVE PARENTHESIS
    # =====================================================

    category = re.sub(r"\(.*?\)", "", category)

    category = category.strip(" :-.,;/")

    lowered = category.lower()

    # =====================================================
    # EXACT MATCH
    # =====================================================

    if lowered in CATEGORY_ALIASES:

        return CATEGORY_ALIASES[lowered]

    # =====================================================
    # PARTIAL MATCH
    # =====================================================

    for key, value in CATEGORY_ALIASES.items():

        if lowered.startswith(key):

            return value

    # =====================================================
    # SAFETY LIMIT
    # =====================================================

    if len(category) > MAX_CATEGORY_LENGTH:

        return "Other/Misc"

    # =====================================================
    # TITLE CASE
    # =====================================================

    return category.title()


def final_category(row):

    category_fix = clean(
        row.get("category_fix")
    )

    if category_fix:

        return normalize_category(category_fix)

    category = clean(
        row.get("category")
    )

    return normalize_category(category)


def fetch_bases():

    params = {
        "select": "*",
        "order": "supergroup_name.asc"
    }

    r = requests.get(
        API_URL,
        headers=HEADERS,
        params=params,
        timeout=120
    )

    r.raise_for_status()

    return r.json()

# =========================================================
# MENU GENERATION
# =========================================================

def generate():

    rows = fetch_bases()

    grouped = defaultdict(list)

    for row in rows:

        category = final_category(row)

        if len(category) > MAX_CATEGORY_LENGTH:

            category = "Other/Misc"

        row["final_category"] = category

        grouped[category].append(row)

    lines = []

    lines.append('Title "POINT OF INTEREST"')
    lines.append("")

    for category in sorted(grouped.keys()):

        lines.append(f'Menu "{category}"')
        lines.append("{")
        lines.append("")

        for row in grouped[category]:

            name = clean(
                row.get("supergroup_name")
            )

            code = clean(
                row.get("base_code")
            )

            if not name or not code:
                continue

            lines.append(f'    Menu "{name}"')
            lines.append("    {")
            lines.append(f'        Title "{name}"')
            lines.append("")
            lines.append("        DIVIDER")
            lines.append("")
            lines.append(
                f'        Option "ENTER BASE" '
                f'"enterbasefrompasscode {code}"'
            )
            lines.append("")
            lines.append("        DIVIDER")
            lines.append("")
            lines.append(
                f'        Option "Send Passcode to Group" '
                f'"beginchat /group {code}"'
            )
            lines.append("")
            lines.append("        DIVIDER")
            lines.append("")
            lines.append(
                f'        Title "PASSCODE : {code}"'
            )
            lines.append("")
            lines.append("    }")
            lines.append("")

        lines.append("}")
        lines.append("")

    return "\n".join(lines)

# =========================================================
# MAIN
# =========================================================

def main():

    output = generate()

    with open("generator_lite_output.mnu", "w", encoding="utf-8") as f:

        f.write(output)

    print("============================================================")
    print("DONE")
    print("generator_lite_output.mnu generated")
    print("============================================================")


if __name__ == "__main__":
    main()
