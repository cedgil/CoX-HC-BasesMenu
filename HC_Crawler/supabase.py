import requests

from datetime import datetime, timezone

from config import (
    REST_BASE_URL,
    TABLE_NAME,
    HEADERS
)

# =========================================================

def compute_icon(category):

    if not category:
        return "Base_Portal"

    c = category.lower()

    if "realism" in c:
        return "MissionArchitect"

    if "fantasy" in c:
        return "Croatoa"

    if "arcane" in c:
        return "Mystic"

    if "tech" in c or "sci" in c:
        return "TechLabs"

    if "club" in c:
        return "PocketD"

    if "hub" in c:
        return "Base_Transport"

    if "nature" in c:
        return "Eden"

    if "maze" in c:
        return "Tunnels"

    if "floating" in c:
        return "ShadowShard"

    if "novice" in c:
        return "TrainingRoom"

    return "Base_Portal"

# =========================================================

def upsert_base(data):

    url = f"{REST_BASE_URL}/{TABLE_NAME}"

    now = datetime.now(
        timezone.utc
    ).isoformat()

    payload = {
        "supergroup_name": data["supergroup_name"],
        "shard": data["shard"],
        "base_code": data["base_code"],
        "category": data["category"],

        "icon": compute_icon(
            data["category"]
        ),

        "source_topic": data["source_topic"],
        "source_url": data["source_url"],
        "source_page": data["source_page"],

        "post_author": data["post_author"],

        "raw_post": data["raw_post"],

        "scraped_at": now,
        "updated_at": now
    }

    params = {
        "on_conflict": "base_code,shard"
    }

    r = requests.post(
        url,
        headers=HEADERS,
        params=params,
        json=payload,
        timeout=60
    )

    print(r.status_code)

    if r.status_code >= 400:
        print(r.text)
