import re

from config import (
    SHARD_ALIASES,
    CATEGORY_MAP
)

# =========================================================

PASSCODE_RE = re.compile(
    r"\b[A-Z0-9]{2,}-\d+\b",
    re.I
)

# =========================================================

STOP_WORDS = [

    "description",
    "special or hidden",
    "base owner",
    "base builder",
    "contributing builders",
    "additional information",
    "is flight",
    "edited",
    "posted"
]

# =========================================================

FIELD_VARIANTS = {

    "name": [
        "supergroup name",
        "base or sg name",
        "base name",
        "your base’s name",
        "your base's name"
    ],

    "shard": [
        "shard/server",
        "server",
        "shard",
        "the shard it is located on"
    ],

    "code": [
        "base code",
        "passcode",
        "the passcode for entry"
    ],

    "category": [
        "category",
        "category for contest",
        "category to list base in",
        "the category your base is entering under",
        "where does this fit"
    ]
}

# =========================================================

def clean(v):

    if not v:
        return None

    v = re.sub(r"\s+", " ", v).strip()

    return v or None

# =========================================================

def normalize_shard(text):

    if not text:
        return None

    t = text.lower()

    for k, v in SHARD_ALIASES.items():

        if k in t:
            return v

    return None

# =========================================================

def normalize_category(text):

    if not text:
        return None

    t = text.lower()

    for k, v in CATEGORY_MAP.items():

        if k in t:
            return v

    return clean(text[:50])

# =========================================================

def trim_noise(value):

    if not value:
        return None

    lower = value.lower()

    for stop in STOP_WORDS:

        pos = lower.find(stop)

        if pos > 0:
            value = value[:pos]

    value = re.split(r"\bEdited\b", value)[0]

    return clean(value)

# =========================================================

def extract_field(text, labels):

    lines = text.splitlines()

    for idx, line in enumerate(lines):

        lower = line.lower()

        for label in labels:

            if label in lower:

                after = line.split(":", 1)

                if len(after) > 1:

                    value = after[1].strip()

                    if value:
                        return value

                if idx + 1 < len(lines):
                    return lines[idx + 1].strip()

    return None

# =========================================================

def infer_shard(text):

    lower = text.lower()

    for k, v in SHARD_ALIASES.items():

        if k in lower:
            return v

    return None

# =========================================================

def parse_post(text):

    name = extract_field(
        text,
        FIELD_VARIANTS["name"]
    )

    shard = extract_field(
        text,
        FIELD_VARIANTS["shard"]
    )

    code = extract_field(
        text,
        FIELD_VARIANTS["code"]
    )

    category = extract_field(
        text,
        FIELD_VARIANTS["category"]
    )

    if code:

        m = PASSCODE_RE.search(code)

        if m:
            code = m.group(0)

    if not shard:
        shard = infer_shard(text)

    shard = normalize_shard(shard)

    category = normalize_category(
        trim_noise(category)
    )

    return {
        "supergroup_name": trim_noise(name),
        "shard": shard,
        "base_code": clean(code),
        "category": category
    }
