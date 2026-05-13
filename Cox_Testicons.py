```python
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
    "User-Agent": "HC-Icon-Scraper/2.0"
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
# MACRO IMAGES
# =========================================================

def scrape_macro_images():

    print("================================")
    print("SCRAPING MACRO IMAGES")
    print("================================")

    r = requests.get(
        MACRO_IMAGE_URL,
        headers=HEADERS,
        timeout=60
    )

    r.raise_for_status()

    text = r.text

    matches = re.findall(
        r'/macro_image\s+"([^"]+)"\s+"Tooltip"\s+"Command"',
        text
    )

    unique = sorted(set(matches))

    print()
    print(f"TOTAL MACRO IMAGES: {len(unique)}")
    print()

    print("FIRST 50:")
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
# CATEGORY PAGE
# =========================================================

def scrape_icon_page(letter, url):

    print("================================")
    print(f"SCRAPING PAGE {letter}")
    print(url)
    print("================================")

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=60
    )

    r.raise_for_status()

    html = r.text

    # -----------------------------------------------------
    # récupérer titres wiki
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

        # exclusions
        lowered = title.lower()

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

    print("FIRST 30:")
    for icon in valid[:30]:
        print(icon)

    print()

    ICON_CATEGORIES[f"Wiki {letter}"].extend(valid)


# =========================================================
# WIKI CATEGORY
# =========================================================

def scrape_icon_categories():

    print("================================")
    print("SCRAPING WIKI CATEGORY")
    print("================================")

    r = requests.get(
        ICON_CATEGORY_URL,
        headers=HEADERS,
        timeout=60
    )

    r.raise_for_status()

    html = r.text

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
# MENU
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

            if len(pages) == 1:

                for icon in pages[0]:
                    write_locked_option(f, icon)

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
```
