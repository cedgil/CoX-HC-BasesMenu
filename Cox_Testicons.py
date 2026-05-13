import re
import math
import requests
from bs4 import BeautifulSoup
from collections import defaultdict

# =========================================================
# CONFIG
# =========================================================

OUTPUT_FILE = "icons_debug.mnu"

# ---------------------------------------------------------
# MACRO IMAGE PAGE
# ---------------------------------------------------------

MACRO_IMAGE_URL = (
    "https://homecoming.wiki/wiki/Macro_image_(Slash_Command)"
)

# ---------------------------------------------------------
# ICON IMAGE CATEGORY
# ---------------------------------------------------------

ICON_CATEGORY_URL = (
    "https://homecoming.wiki/wiki/Category:Icon_Images"
)

HEADERS = {
    "User-Agent": "HC-Icon-Scraper/1.0"
}

PAGE_SIZE = 40

# =========================================================
# STORAGE
# =========================================================

ICON_CATEGORIES = defaultdict(list)

# =========================================================
# HELPERS
# =========================================================

def clean(text):
    return (text or "").strip()


def chunked(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def sanitize_menu_name(name):
    return re.sub(r'[^A-Za-z0-9_]', '_', name)


# =========================================================
# MACRO IMAGE SCRAPER
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

    # récupère :
    # /macro_image "XXX" "Tooltip" "Command"

    matches = re.findall(
        r'/macro_image\s+"([^"]+)"\s+"Tooltip"\s+"Command"',
        text
    )

    unique = sorted(set(matches))

    print(f"{len(unique)} macro images found")

    for icon in unique:

        # catégorie = préfixe avant _
        if "_" in icon:
            category = icon.split("_")[0]
        else:
            category = "Misc"

        ICON_CATEGORIES[f"Macro - {category}"].append(icon)


# =========================================================
# ICON IMAGE CATEGORY SCRAPER
# =========================================================

def scrape_icon_category_page(url, category_name):

    print(f"SCRAPING: {url}")

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=60
    )

    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # -----------------------------------------------------
    # récupérer tous les liens image
    # -----------------------------------------------------

    links = soup.find_all("a")

    found = []

    for a in links:

        title = clean(a.get("title"))

        if not title:
            continue

        # éviter pollution wiki
        if any(x in title.lower() for x in [
            "category:",
            "special:",
            "template:",
            "help:",
            "file:"
        ]):
            continue

        # garder uniquement trucs plausibles
        if re.match(r"^[A-Za-z0-9_\-\.]+$", title):

            found.append(title)

    found = sorted(set(found))

    print(f"{len(found)} icons found")

    for icon in found:
        ICON_CATEGORIES[category_name].append(icon)


def scrape_icon_images():

    print("================================")
    print("SCRAPING ICON IMAGE CATEGORIES")
    print("================================")

    r = requests.get(
        ICON_CATEGORY_URL,
        headers=HEADERS,
        timeout=60
    )

    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # -----------------------------------------------------
    # récupérer sous-pages A-T
    # -----------------------------------------------------

    links = soup.find_all("a")

    subpages = []

    for a in links:

        href = a.get("href", "")
        title = clean(a.get_text())

        if re.match(r"^[A-Z]$", title):

            full_url = "https://homecoming.wiki" + href

            subpages.append((title, full_url))

    subpages = sorted(set(subpages))

    print(f"{len(subpages)} subpages found")

    # -----------------------------------------------------
    # scraper chaque page
    # -----------------------------------------------------

    for letter, url in subpages:

        scrape_icon_category_page(
            url,
            f"Wiki - {letter}"
        )


# =========================================================
# MENU GENERATION
# =========================================================

def write_locked_option(f, icon_name):

    display = icon_name[:80]

    f.write('\t\tLockedOption\n')
    f.write('\t\t{\n')
    f.write(f'\t\t\tDisplayName "{display}"\n')
    f.write('\t\t\tCommand ""\n')
    f.write(f'\t\t\tIcon "{icon_name}"\n')
    f.write('\t\t}\n')


def write_icon_page(f, page_name, icons):

    f.write(f'\t\tMenu "{page_name}"\n')
    f.write('\t\t{\n')

    f.write(f'\t\t\tTitle "{page_name.upper()}"\n')
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
        # categories
        # -------------------------------------------------

        for category in sorted(ICON_CATEGORIES.keys()):

            icons = sorted(set(
                ICON_CATEGORIES[category]
            ))

            if not icons:
                continue

            # ---------------------------------------------
            # pagination
            # ---------------------------------------------

            pages = list(chunked(
                icons,
                PAGE_SIZE
            ))

            if len(pages) == 1:

                f.write(f'\tMenu "{category}"\n')
                f.write('\t{\n')

                f.write(f'\t\tTitle "{category.upper()}"\n')
                f.write('\t\tDIVIDER\n')

                for icon in pages[0]:
                    write_locked_option(f, icon)

                f.write('\t}\n')

            else:

                f.write(f'\tMenu "{category}"\n')
                f.write('\t{\n')

                f.write(f'\t\tTitle "{category.upper()}"\n')
                f.write('\t\tDIVIDER\n')

                for idx, page in enumerate(
                    pages,
                    start=1
                ):

                    page_name = (
                        f"Page {idx}"
                    )

                    write_icon_page(
                        f,
                        page_name,
                        page
                    )

                f.write('\t}\n')

        f.write('}\n')

    print(f"Menu written to: {OUTPUT_FILE}")


# =========================================================
# MAIN
# =========================================================

def main():

    scrape_macro_images()

    scrape_icon_images()

    generate_menu()

    print("================================")
    print("DONE")
    print("================================")


if __name__ == "__main__":

    main()
