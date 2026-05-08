# FULL CLOUD SCRAPER V2

    return max(score, 0)


def normalize_scores():
    max_score = max(compute_score(b) for b in BASES.values())

    for base in BASES.values():
        raw = compute_score(base)
        base["score"] = round((raw / max_score) * 100)


def push_supabase():
    url = f"{SUPABASE_URL}?on_conflict=code"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    payload = []

    for b in BASES.values():
        payload.append({
            "code": b["code"],
            "server": b["server"],
            "name": b["name"],
            "style": b["style"],
            "venue": b["venue"],
            "tag1": b["tag1"],
            "tag2": b["tag2"],
            "sources": b["sources"],
            "score": b["score"],
            "updated_at": NOW.isoformat(),
            "last_seen_at": NOW.isoformat(),
            "is_missing": False
        })

    r = requests.post(url, headers=headers, json=payload)

    print(r.status_code)
    print(r.text)


def main():
    for gid, sheet_type in SHEETS.items():
        load_google_sheet(gid, sheet_type)

    normalize_scores()

    print(f"Loaded {len(BASES)} bases")

    push_supabase()


if __name__ == "__main__":
    main()
