import re

# =========================================================
# SERVERS
# =========================================================

SERVER_ALIASES = {

    "torch": "Torchbearer",
    "torchbearer": "Torchbearer",

    "excel": "Excelsior",
    "excelsior": "Excelsior",

    "ever": "Everlasting",
    "everlasting": "Everlasting",

    "reunion": "Reunion",

    "indom": "Indomitable",
    "indomitable": "Indomitable",

    "victory": "Victory"
}

# =========================================================
# HELPERS
# =========================================================

def clean(text):

    if not text:
        return ""

    text = text.replace("\xa0", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_server(server):

    s = clean(server).lower()

    for k, v in SERVER_ALIASES.items():

        if s.startswith(k):
            return v

    return server


def extract_field(text, labels):

    for label in labels:

        pattern = (
            re.escape(label)
            + r"\s*(.+?)(?=\n[A-Z][^\n]{0,40}:|\Z)"
        )

        m = re.search(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL
        )

        if m:

            value = clean(m.group(1))

            value = value.split("Edited")[0]

            value = value.split("Posted")[0]

            return value

    return ""


def clean_category(category):

    if not category:
        return ""

    category = clean(category)

    category = category.split(
        "Contributing builders"
    )[0]

    category = category.split(
        "Any additional information"
    )[0]

    category = category.split(
        "Special or Hidden Features"
    )[0]

    category = category.split(
        "Is flight or teleportation"
    )[0]

    category = category.split(
        "Description"
    )[0]

    category = category.split(
        "Where does this fit?"
    )[-1]

    category = clean(category)

    return category


# =========================================================
# SINGLE BASE PARSER
# =========================================================

def parse_single_base(block):

    sg_name = extract_field(block, [

        "Supergroup Name:",
        "Base or SG Name:",
        "Your base’s name:"
    ])

    shard = extract_field(block, [

        "Shard/Server:",
        "Shard:",
        "The shard it is located on:"
    ])

    code = extract_field(block, [

        "Base Code:",
        "Passcode:",
        "The passcode for entry:"
    ])

    category = extract_field(block, [

        "Category to list base in:",
        "Category for Contest:",
        "The category your base is entering under:"
    ])

    # fallback serveur via phrase libre
    if not shard:

        lower = block.lower()

        for alias, full in SERVER_ALIASES.items():

            if alias in lower:
                shard = full
                break

    shard = normalize_server(shard)

    category = clean_category(category)

    # nettoyage code
    code_match = re.search(
        r"[A-Z0-9]+-\d+",
        code,
        re.IGNORECASE
    )

    if code_match:
        code = code_match.group(0)

    data = {

        "supergroup_name": clean(sg_name),
        "shard": clean(shard),
        "base_code": clean(code),
        "category": clean(category)
    }

    return data

# =========================================================
# MULTI BASE EXTRACTION
# =========================================================

def extract_bases(

    post_text,
    topic_title,
    topic_url,
    page_number,
    author=None
):

    if not post_text:
        return []

    raw = post_text.replace("\r", "\n")

    blocks = re.split(

        r"(?=Supergroup Name:|Base or SG Name:|Your base’s name:)",
        raw,
        flags=re.IGNORECASE
    )

    results = []

    for block in blocks:

        block = block.strip()

        if not block:
            continue

        parsed = parse_single_base(block)

        if not parsed["base_code"]:
            continue

        parsed["source_topic"] = topic_title
        parsed["source_url"] = topic_url
        parsed["source_page"] = page_number
        parsed["post_author"] = author
        parsed["raw_post"] = block

        results.append(parsed)

    return results
