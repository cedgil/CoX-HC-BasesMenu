import re
import requests
from collections import defaultdict

# =========================================================
# CONFIG
# =========================================================

OUTPUT_FILE = "icons_debug.mnu"

MACRO_IMAGE_URL = (
    "https://homecoming.wiki/wiki/Macro_image_(Slash_Command)"
)

ICON_CATEGORY_URL = (
    "https://homecoming.wiki/wiki/Category:Icon_Images"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

PAGE_SIZE = 40

# =========================================================
# STORAGE
# =========================================================

ICON_CATEGORIES = defaultdict(list)

# =========================================================
# HELPERS
# =========================================================

def clean(v):
    return (v or "").strip()


def chunked(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

# =========================================================
# HTTP DEBUG
# =========================================================

def fetch_url(url):

    print("================================")
    print("FETCHING URL")
    print(url)
    print("================================")

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=60
    )

    print("STATUS:", r.status_code)
    print("FINAL URL:", r.url)
    print("CONTENT TYPE:", r.headers.get("content-type"))

    print()
    print("HTML PREVIEW:")
    print(r.text[:2000])
    print()

    r.raise_for_status()

    return r.text

# =========================================================
# MACRO IMAGES
# =========================================================

def scrape_macro_images():

    print("================================")
    print("SCRAPING MACRO IMAGES")
    print("================================")

    text = fetch_url(MACRO_IMAGE_URL)

    # -----------------------------------------------------
    # récupère :
    # /macro_image "XXX" "Tooltip" "Command"
    # -----------------------------------------------------

    matches = re.findall(
        r'/macro_image\s+"([^"]+)"\s+"Tooltip"\s+"Command"',
        text
    )

    unique = sorted(set(matches))

    print()
    print(f"TOTAL MACRO IMAGES: {len(unique)}")
    print()

    print("FIRST 50 MACRO IMAGES:")
    for icon in unique[:50]:
        print(icon)

    print()

    for icon in unique:

        if "_" in icon:
            category = icon.split("_")[0]
        else:
            category = "Misc"

        ICON_CATEGORIES[f"Macro {category}"].append(icon)

# =========================================================
# WIKI ICON PAGES
# =========================================================

def scrape_icon_page(letter, url):

    print("================================")
    print(f"SCRAPING PAGE {letter}")
    print("================================")

    html = fetch_url(url)

    # -----------------------------------------------------
    # récupérer tous les title=""
    # -----------------------------------------------------

    matches = re.findall(
        r'title="([^"]+)"',
        html
    )

    valid = []

    for title in matches:

        title = clean(title)

        if not title:
            continue

        lowered = title.lower()

        # exclusions
        if any(x in lowered for x in [
            "category:",
            "template:",
            "special:",
            "help:",
            "file:",
            "mediawiki",
            "semantic"
        ]):
            continue

        # garder noms plausibles
        if re.match(r'^[A-Za-z0-9_\-\.]+$', title):

            valid.append(title)

    valid = sorted(set(valid))

    print()
    print(f"FOUND {len(valid)} ICONS")
    print()

    print("FIRST 50 ICONS:")
    for icon in valid[:50]:
        print(icon)

    print()

    ICON_CATEGORIES[f"Wiki {letter}"].extend(valid)

# =========================================================
# CATEGORY SCRAPER
# =========================================================

def scrape_icon_categories():

    print("================================")
    print("SCRAPING ICON IMAGE CATEGORY")
    print("================================")

    html = fetch_url(ICON_CATEGORY_URL)

    # -----------------------------------------------------
    # trouver pages A-Z
    # -----------------------------------------------------

    subpages = re.findall(
        r'href="([^"]+/Icon_Images/([A-Z]))"',
        html
    )

    found = []

    for href, letter in subpages:

        url = "https://homecoming.wiki" + href

        found.append((letter, url))

    found = sorted(set(found))

    print()
    print(f"SUBPAGES FOUND: {len(found)}")
    print()

    for letter, url in found:
        print(letter, url)

    print()

    # -----------------------------------------------------
    # scraper chaque page
    # -----------------------------------------------------

    for letter, url in found:

        scrape_icon_page(letter, url)

# =========================================================
# MENU GENERATION
# =========================================================

def write_locked_option(f, icon_name):

    f.write('\t\tLockedOption\n')
    f.write('\t\t{\n')
    f.write(f'\t\t\tDisplayName "{icon_name}"\n')
    f.write('\t\t\tCommand ""\n')
    f.write(f'\t\t\tIcon "{icon_name}"\n')
    f.write('\t\t}\n')


def write_page(f, page_name, icons):

    f.write(f'\t\tMenu "{page_name}"\n')
    f.write('\t\t{\n')

    f.write(f'\t\t\tTitle "{page_name}"\n')
    f.write('\t\t\tDIVIDER\n')

    for icon in icons:

        write_locked_option(f, icon)

    f.write('\t\t}\n')


def generate_menu():

    print("================================")
    print("GENERATING MENU")
    print("================================")

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        f.write('Menu "IconBrowser"\n')
        f.write('{\n')

        f.write('\tTitle "ICON BROWSER"\n')
        f.write('\tDIVIDER\n')

        # -------------------------------------------------
        # catégories
        # -------------------------------------------------

        for category in sorted(ICON_CATEGORIES.keys()):

            icons = sorted(set(
                ICON_CATEGORIES[category]
            ))

            if not icons:
                continue

            print()
            print(f"{category}: {len(icons)} icons")

            pages = list(chunked(
                icons,
                PAGE_SIZE
            ))

            f.write(f'\tMenu "{category}"\n')
            f.write('\t{\n')

            f.write(f'\t\tTitle "{category}"\n')
            f.write('\t\tDIVIDER\n')

            # ---------------------------------------------
            # pagination
            # ---------------------------------------------

            if len(pages) == 1:

                for icon in pages[0]:

                    write_locked_option(
                        f,
                        icon
                    )

            else:

                for idx, page in enumerate(
                    pages,
                    start=1
                ):

                    write_page(
                        f,
                        f"Page {idx}",
                        page
                    )

            f.write('\t}\n')

        f.write('}\n')

    print()
    print(f"MENU WRITTEN: {OUTPUT_FILE}")

# =========================================================
# MAIN
# =========================================================

def main():

    scrape_macro_images()

    scrape_icon_categories()

    generate_menu()

    print()
    print("================================")
    print("DONE")
    print("================================")


if __name__ == "__main__":

    main()
