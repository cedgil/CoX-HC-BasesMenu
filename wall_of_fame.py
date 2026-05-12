#!/usr/bin/env python3

import os
import re
import json
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
from datetime import datetime

# =========================================================
# CONFIG
# =========================================================

WALL_OF_FAME_URL = (
    "https://forums.homecomingservers.com/topic/44842-wall-of-fame/"
)

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

SUPABASE_TABLE = "base_contest_entries"

# =========================================================
# FIX URL
# =========================================================

# accepte :
# https://xxx.supabase.co
# https://xxx.supabase.co/rest/v1
# https://xxx.supabase.co/rest/v1/bases

if "/rest/v1/" in SUPABASE_URL:
    REST_BASE_URL = SUPABASE_URL.split("/rest/v1")[0] + "/rest/v1"

elif SUPABASE_URL.endswith("/rest/v1"):
    REST_BASE_URL = SUPABASE_URL

else:
    REST_BASE_URL = SUPABASE_URL + "/rest/v1"

# =========================================================
# CONSTANTS
# =========================================================

SHARDS = [
    "Everlasting",
    "Excelsior",
    "Torchbearer",
    "Indomitable",
    "Reunion",
    "Victory"
]

YEAR_RE = re.compile(r"~+\s*(\d{4})\s*~+")
STAR_TITLE_RE = re.compile(r"⭐([^⭐]+)⭐")

# =========================================================
# FETCH
# =========================================================

def fetch_wall_of_fame_html() -> str:

    headers = {
        "User-Agent": "HC-WallOfFame-Scraper/2.0"
    }

    resp = requests.get(
        WALL_OF_FAME_URL,
        headers=headers,
        timeout=30
    )

    resp.raise_for_status()

    return resp.text

# =========================================================
# HTML
# =========================================================

def extract_main_text(html: str) -> str:

    soup = BeautifulSoup(html, "html.parser")

    main = soup.find("main") or soup

    return main.get_text(
        separator="\n",
        strip=True
    )

# =========================================================
# TEXT HELPERS
# =========================================================

def normalize_whitespace(s: str) -> str:

    s = s.replace("\u00a0", " ")
    s = s.replace("\r", "\n")

    s = re.sub(r"[ \t]+", " ", s)

    return s


def canonicalize_pipes_and_codes(text: str) -> str:

    text = re.sub(
        r"\n\|\s*",
        " | ",
        text
    )

    text = re.sub(
        r"\|\s*\n([A-Z0-9-]+)",
        r"| \1",
        text
    )

    return text

# =========================================================
# SPLIT YEARS
# =========================================================

def split_by_year(text: str) -> Dict[int, str]:

    years = {}

    matches = list(YEAR_RE.finditer(text))

    for i, m in enumerate(matches):

        year = int(m.group(1))

        start = m.end()

        end = (
            matches[i + 1].start()
            if i + 1 < len(matches)
            else len(text)
        )

        years[year] = text[start:end]

    return years

# =========================================================
# SPLIT CONTESTS
# =========================================================

def split_contest_sections(year_block: str):

    sections = []

    matches = list(STAR_TITLE_RE.finditer(year_block))

    for i, m in enumerate(matches):

        title = m.group(1).strip()

        start = m.end()

        end = (
            matches[i + 1].start()
            if i + 1 < len(matches)
            else len(year_block)
        )

        chunk = year_block[start:end]

        sections.append({
            "title": title,
            "text": chunk
        })

    return sections

# =========================================================
# PARSER
# =========================================================

def parse_entries_from_section(
    year: int,
    contest_title: str,
    section_text: str
) -> List[Dict]:

    entries = []

    text = normalize_whitespace(section_text)

    text = canonicalize_pipes_and_codes(text)

    for shard in SHARDS:

        text = re.sub(
            rf"\s*{shard}\s*:",
            f"\n{shard}:",
            text
        )

        text = re.sub(
            rf"\s*{shard}\s*\|",
            f"\n{shard} |",
            text
        )

    lines = [
        l.strip()
        for l in text.split("\n")
        if l.strip()
    ]

    current_shard = None

    shard_header_re = re.compile(
        rf"^({'|'.join(SHARDS)})\s*:\s*(.*)$"
    )

    entry_with_shard_re = re.compile(
        rf"^({'|'.join(SHARDS)})\s*\|\s*([A-Z0-9-]+)\s*\|\s*([^|]+)\|"
    )

    entry_no_shard_re = re.compile(
        r"^([A-Z0-9-]+)\s*\|\s*([^|]+)\|"
    )

    for line in lines:

        m_header = shard_header_re.match(line)

        if m_header:

            current_shard = m_header.group(1)

            rest = m_header.group(2).strip()

            if rest:

                m_entry = entry_no_shard_re.match(rest)

                if m_entry:

                    entries.append({
                        "year": year,
                        "contest_title": contest_title,
                        "shard": current_shard,
                        "passcode": m_entry.group(1).strip(),
                        "base_name": m_entry.group(2).strip()
                    })

            continue

        m_with_shard = entry_with_shard_re.match(line)

        if m_with_shard:

            current_shard = m_with_shard.group(1).strip()

            entries.append({
                "year": year,
                "contest_title": contest_title,
                "shard": current_shard,
                "passcode": m_with_shard.group(2).strip(),
                "base_name": m_with_shard.group(3).strip()
            })

            continue

        m_no_shard = entry_no_shard_re.match(line)

        if m_no_shard and current_shard:

            entries.append({
                "year": year,
                "contest_title": contest_title,
                "shard": current_shard,
                "passcode": m_no_shard.group(1).strip(),
                "base_name": m_no_shard.group(2).strip()
            })

    return entries

# =========================================================
# SCRAPER
# =========================================================

def scrape_wall_of_fame():

    html = fetch_wall_of_fame_html()

    main_text = extract_main_text(html)

    years_blocks = split_by_year(main_text)

    all_entries = []

    for year, block in years_blocks.items():

        sections = split_contest_sections(block)

        for sec in sections:

            entries = parse_entries_from_section(
                year,
                sec["title"],
                sec["text"]
            )

            all_entries.extend(entries)

    return all_entries

# =========================================================
# SUPABASE
# =========================================================

def upsert_to_supabase(entries):

    if not entries:
        print("NO ENTRIES")
        return

    url = f"{REST_BASE_URL}/{SUPABASE_TABLE}"

    print("================================")
    print("SUPABASE DEBUG")
    print("================================")
    print("RAW URL:")
    print(SUPABASE_URL)
    print()
    print("REST URL:")
    print(REST_BASE_URL)
    print()
    print("FINAL URL:")
    print(url)
    print("================================")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    params = {
        "on_conflict": "year,contest_title,shard,passcode"
    }

    resp = requests.post(
        url,
        headers=headers,
        params=params,
        json=entries,
        timeout=60
    )

    if resp.status_code >= 400:
        print("SUPABASE ERROR")
        print(resp.status_code)
        print(resp.text)

    resp.raise_for_status()

    print(f"UPSERTED {len(entries)} ROWS")

# =========================================================
# MAIN
# =========================================================

def main():

    print("================================")
    print("WALL OF FAME SCRAPER")
    print("================================")

    entries = scrape_wall_of_fame()

    print(f"PARSED {len(entries)} ENTRIES")

    print("SAMPLE:")
    print(entries[:5])

    upsert_to_supabase(entries)

    print("DONE")

# =========================================================

if __name__ == "__main__":
    main()
