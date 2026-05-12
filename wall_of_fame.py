#!/usr/bin/env python3
import os
import re
import json
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
from datetime import datetime

WALL_OF_FAME_URL = "https://forums.homecomingservers.com/topic/44842-wall-of-fame/"

# SUPABASE_URL peut être soit https://xyz.supabase.co soit https://xyz.supabase.co/rest/v1
_raw_url = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SUPABASE_TABLE = "base_contest_entries"

if _raw_url.endswith("/rest/v1"):
    REST_BASE_URL = _raw_url
else:
    REST_BASE_URL = _raw_url + "/rest/v1"

SHARDS = ["Everlasting", "Excelsior", "Torchbearer", "Indomitable", "Reunion", "Victory"]


def fetch_wall_of_fame_html() -> str:
    headers = {
        "User-Agent": "SugagabeWallOfFameScraper/1.2 (https://github.com/...)"
    }
    resp = requests.get(WALL_OF_FAME_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_main_text(html: str) -> str:
    """
    Récupère le texte du premier post (le mur de la gloire).
    On prend le <main>, c'est plus robuste que de chercher l'article par data-role.
    """
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    text = main.get_text(separator="\n", strip=True)
    return text


YEAR_RE = re.compile(r"~+\s*(\d{4})\s*~+")
STAR_TITLE_RE = re.compile(r"⭐([^⭐]+)⭐")


def split_by_year(text: str) -> Dict[int, str]:
    years: Dict[int, str] = {}
    matches = list(YEAR_RE.finditer(text))
    for i, m in enumerate(matches):
        year = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        years[year] = text[start:end]
    return years


def split_contest_sections(year_block: str) -> List[Dict[str, str]]:
    sections: List[Dict[str, str]] = []
    matches = list(STAR_TITLE_RE.finditer(year_block))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(year_block)
        chunk = year_block[start:end]
        sections.append({"title": title, "text": chunk})
    return sections


def normalize_whitespace(s: str) -> str:
    s = s.replace("\u00a0", " ")
    s = s.replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    return s


def canonicalize_pipes_and_codes(text: str) -> str:
    """
    Le HTML du forum donne souvent :
      Excelsior\n| DIVINE-29035 |\nElysian Temple\n| By ...
      Everlasting |\nFAECAVE-31825\n| Fae Caverns |\nBy\n@Aalya

    On aplatit ça en :
      Excelsior | DIVINE-29035 | Elysian Temple | By ...
      Everlasting | FAECAVE-31825 | Fae Caverns | By ...
    """
    # 1) remplace '\n| ' par ' | '
    text = re.sub(r"\n\|\s*", " | ", text)

    # 2) remplace '|\nCODE' par '| CODE'
    text = re.sub(r"\|\s*\n([A-Z0-9-]+)", r"| \1", text)

    return text


def parse_entries_from_section(year: int, contest_title: str, section_text: str) -> List[Dict]:
    entries: List[Dict] = []
    text = normalize_whitespace(section_text)
    text = canonicalize_pipes_and_codes(text)

    # On aide un peu le split en forçant des retours à la ligne avant certains motifs
    for shard in SHARDS:
        text = re.sub(rf"\s*{shard}\s*:", f"\n{shard}:", text)
        text = re.sub(rf"\s*{shard}\s*\|", f"\n{shard} |", text)

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    current_shard = None

    shard_header_re = re.compile(rf"^({'|'.join(SHARDS)})\s*:\s*(.*)$")
    entry_with_shard_re = re.compile(
        rf"^({'|'.join(SHARDS)})\s*\|\s*([A-Z0-9-]+)\s*\|\s*([^|]+)\|"
    )
    entry_no_shard_re = re.compile(r"^([A-Z0-9-]+)\s*\|\s*([^|]+)\|")

    for line in lines:
        # 1) 'Shard: CODE | NAME | ...'
        m_header = shard_header_re.match(line)
        if m_header:
            current_shard = m_header.group(1)
            rest = m_header.group(2).strip()
            if rest:
                m_entry = entry_no_shard_re.match(rest)
                if m_entry:
                    code = m_entry.group(1).strip()
                    base = m_entry.group(2).strip()
                    entries.append(
                        {
                            "year": year,
                            "contest_title": contest_title,
                            "shard": current_shard,
                            "passcode": code,
                            "base_name": base,
                        }
                    )
            continue

        # 2) 'Shard | CODE | NAME | ...'
        m_with_shard = entry_with_shard_re.match(line)
        if m_with_shard:
            shard = m_with_shard.group(1).strip()
            code = m_with_shard.group(2).strip()
            base = m_with_shard.group(3).strip()
            entries.append(
                {
                    "year": year,
                    "contest_title": contest_title,
                    "shard": shard,
                    "passcode": code,
                    "base_name": base,
                }
            )
            current_shard = shard
            continue

        # 3) 'CODE | NAME | ...' (avec current_shard défini)
        m_no_shard = entry_no_shard_re.match(line)
        if m_no_shard and current_shard:
            code = m_no_shard.group(1).strip()
            base = m_no_shard.group(2).strip()
            entries.append(
                {
                    "year": year,
                    "contest_title": contest_title,
                    "shard": current_shard,
                    "passcode": code,
                    "base_name": base,
                }
            )
            continue

    return entries


def scrape_wall_of_fame() -> List[Dict]:
    html = fetch_wall_of_fame_html()
    main_text = extract_main_text(html)
    years_blocks = split_by_year(main_text)

    all_entries: List[Dict] = []

    for year, block in years_blocks.items():
        sections = split_contest_sections(block)
        for sec in sections:
            contest_title = sec["title"]
            section_text = sec["text"]
            entries = parse_entries_from_section(year, contest_title, section_text)
            all_entries.extend(entries)

    return all_entries


def upsert_to_supabase(entries: List[Dict]) -> None:
    if not entries:
        print("No entries to upsert.")
        return

    url = f"{REST_BASE_URL}/{SUPABASE_TABLE}"
    print(f"Posting to Supabase URL: {url}")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",  # upsert
    }
    params = {
        "on_conflict": "year,contest_title,shard,passcode",
    }

    resp = requests.post(url, headers=headers, params=params, data=json.dumps(entries))
    try:
        resp.raise_for_status()
    except Exception:
        print("Supabase error:", resp.status_code, resp.text)
        raise

    print(f"Upserted {len(entries)} rows into {SUPABASE_TABLE}.")


def main():
    print("Secrets chargés OK")
    print(f"[{datetime.utcnow().isoformat()}] Starting Wall of Fame scrape...")
    entries = scrape_wall_of_fame()
    print(f"Parsed {len(entries)} entries.")
    print("Sample entries:", entries[:5])
    upsert_to_supabase(entries)
    print("Done.")


if __name__ == "__main__":
    main()
