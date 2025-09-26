import requests
from bs4 import BeautifulSoup
import json, base64
import re
from datetime import datetime, timezone
from os import path, makedirs
from pathlib import Path

from github import Github

from common import _L, DEBUG, DIRNAME, INFO

SHIFTCODESJSONPATH = "data/shiftcodes.json"

webpages = [
    {
        "game": "Borderlands 4",
        "sourceURL": "https://mentalmars.com/game-news/borderlands-4-shift-codes/",
        "platform_ordered_tables": ["universal"],
    },
    {
        "game": "Borderlands: Game of the Year Edition",
        "sourceURL": "https://mentalmars.com/game-news/borderlands-golden-keys/",
        "platform_ordered_tables": ["universal", "universal", "universal"],
    },
    {
        "game": "Borderlands 2",
        "sourceURL": "https://mentalmars.com/game-news/borderlands-2-golden-keys/",
        "platform_ordered_tables": [
            "universal",
            "universal",
            "universal",
            "pc",
            "xbox",
            "Playstation",
            "universal",
            "discard",
        ],
    },
    {
        "game": "Borderlands 3",
        "sourceURL": "https://mentalmars.com/game-news/borderlands-3-golden-keys/",
        "platform_ordered_tables": [
            "universal",
            "discard",
            "universal",
            "universal",
            "universal",
            "discard",
            "discard",
            "discard",
            "discard",
        ],
    },
    {
        "game": "Borderlands The Pre-Sequel",
        "sourceURL": "https://mentalmars.com/game-news/bltps-golden-keys/",
        "platform_ordered_tables": [
            "universal",
            "universal",
            "pc",
            "Playstation",
            "xbox",
            "discard",
            "discard",
            "discard",
            "discard",
            "discard",
            "discard",
            "discard",
            "discard",
            "discard",
            "discard",
            "discard",
            "discard",
        ],
    },
    {
        "game": "Tiny Tina's Wonderlands",
        "sourceURL": "https://mentalmars.com/game-news/tiny-tinas-wonderlands-shift-codes/",
        "platform_ordered_tables": ["universal", "universal", "universal"],
    },
]


def remap_dict_keys(dict_keys):
    # Map a variety of possible table heading variations to a small set of
    # canonical keys. This is intentionally fuzzy: many pages prefix the
    # heading with the game name (e.g. 'Borderlands 4 SHiFT Code') or use
    # slightly different wording like 'Expire Date'. Match case-insensitively
    # using substring checks so we don't miss these variants.
    mapped = {}
    for key, value in dict_keys.items():
        if key is None:
            continue
        k = key.strip().lower()
        # handle "expired" specifically before the more generic "expire" check
        if "expired" in k:
            new_key = "expired"
        elif "shift code" in k or ("shift" in k and "code" in k):
            new_key = "code"
        elif "expire" in k:
            new_key = "expires"
        elif "reward" in k:
            new_key = "reward"
        else:
            # preserve the original heading if it doesn't match any known
            # canonical field — downstream code will either handle it or
            # ignore it.
            new_key = key
        mapped[new_key] = value
    return mapped


# convert headings to standard headings
def cleanse_codes(codes):
    clean_codes = []
    for code in codes:

        # standardise the table headings
        clean_code = remap_dict_keys(code)

        # Clean up text from expiry date
        if "expires" in clean_code:
            clean_code.update(
                {"expires": clean_code.get("expires").replace("Expires: ", "")}
            )
        else:
            clean_code.update({"expires": "Unknown"})

        # Mark expired as expired
        if "expired" in clean_code:
            val = clean_code.get("expired")
            # treat any value that is not exactly False, "false", "no", "0", or "" (case-insensitive) as True
            clean_code.update(
                {"expired": str(val).strip().lower() not in ["false", "no", "0", ""]}
            )
        else:
            clean_code.update({"expired": False})

        # convert expiries to dates
        # TODO

        clean_codes.append(clean_code)

    return clean_codes


def scrape_codes(webpage):
    _L.info(
        "Requesting webpage for "
        + webpage.get("game")
        + ": "
        + webpage.get("sourceURL")
    )
    r = requests.get(webpage.get("sourceURL"))
    # record the time we scraped the URL
    scrapedDateAndTime = datetime.now(timezone.utc)
    _L.info(" Collected at: " + str(scrapedDateAndTime))
    # print(r.content)

    soup = BeautifulSoup(
        r.content, "html.parser"
    )  # If this line causes an error, run 'pip install html5lib' or install html5lib
    # print(soup.prettify())

    # Extract all the `figure` tags from the HTML noting the following XPATH was originally expected
    #    /html/body/div[2]/div/div[4]/div[1]/div/div/article/div[5]/figure[2]/table/
    figures = soup.find_all("figure")

    _L.info(" Expecting tables: " + str(len(webpage.get("platform_ordered_tables"))))
    _L.info(" Collected tables: " + str(len(figures)))

    # headers = []
    code_tables = []

    table_count = 0
    for figure in figures:
        # Prevent IndexError if there are more figures than expected
        if table_count >= len(webpage.get("platform_ordered_tables")):
            _L.warning(
                f"More tables found ({len(figures)}) than expected ({len(webpage.get('platform_ordered_tables'))}) for {webpage.get('game')}. Skipping extra tables."
            )
            break

        _L.info(
            " Parsing for table #"
            + str(table_count)
            + " - "
            + webpage.get("platform_ordered_tables")[table_count]
        )

        # Don't parse any tables marked to discard
        if webpage.get("platform_ordered_tables")[table_count] == "discard":
            table_count += 1
            continue

        table_html = figure.find(lambda tag: tag.name == "table")

        table_header = []
        code_table = []

        # Convert the HTML table into a Python Dict:
        # Tip from: https://stackoverflow.com/questions/11901846/beautifulsoup-a-dictionary-from-an-html-table
        table_header = [header.text for header in table_html.find_all("th")]
        table_header.append(
            "expired"
        )  # expired codes have a strikethrough ('s') tag and are found last
        code_table = [
            {
                table_header[i]: cell.text
                for i, cell in enumerate(row.find_all({"td", "s"}))
            }
            for row in table_html.find("tbody").find_all("tr")
        ]

        # If we find more tables on the webpage than we were expecting, error
        if table_count + 1 > len(webpage.get("platform_ordered_tables")):
            _L.error("ERROR: There are more tables on the webpage than configured")
            # TODO _L.error("ERROR: Unexpected table has headings of: " + header)
            # Skip to the next table iteration
            continue

        # Clean the results up
        code_table = cleanse_codes(code_table)
        code_tables.append(
            {
                "game": webpage.get("game"),
                "platform": webpage.get("platform_ordered_tables")[table_count],
                "sourceURL": webpage.get("sourceURL"),
                "archived": scrapedDateAndTime,
                "raw_table_html": str(table_html),
                "codes": code_table,
            }
        )

        # print("Table Number: " + str(table_count))
        # print("HEADER CLEAN: " + str(table_count))
        # print(headers_clean)
        # print("HEADER: " + str(i) + " : " + header)
        # print("RESULT: " + str(i)+ " : " + table)

        table_count += 1
    _L.debug(json.dumps(code_tables, indent=2, default=str))
    return code_tables


# Check to see if the new code existed in previous codes, and if so return the previous code's archive date.
def getPreviousCodeArchived(new_code, new_game, previous_codes):
    # WHY: On a fresh run, data/shiftcodes.json can be empty/invalid so the loader returns None.
    # Guard against None/wrong shape so we don't index previous_codes[0] on a non-list.
    # WHY: Be strict about the expected shape so we don't index previous_codes[0] on something weird (e.g., {}, [None], etc.).
    if isinstance(previous_codes, list) and previous_codes and isinstance(previous_codes[0], dict):
        # Also guard the "codes" key; default to [] so iteration is safe.
        for previous_code in previous_codes[0].get("codes", []):
            if (new_code.get("code") == previous_code.get("code")) and (
                new_game == previous_code.get("game")
            ):
                _L.debug(" Code already existed, reverting archived datestamp")
                return previous_code.get("archived")
    return None
    

# Retrieve the previous full code entry (if any) so we can preserve fields like "expired"
def getPreviousCodeEntry(new_code, new_game, previous_codes):
    # WHY: On first/empty runs, previous_codes can be None or the wrong shape.
    # Guard so we don't index previous_codes[0] on a non-list.
    if not isinstance(previous_codes, list) or not previous_codes:
        return None
    container = previous_codes[0]
    if not isinstance(container, dict):
        return None
    # Safe default: .get("codes", []) avoids KeyError / None iteration
    for previous_code in container.get("codes", []):
        if (new_code.get("code") == previous_code.get("code")) and (
            new_game == previous_code.get("game")
        ):
            return previous_code
    return None


# Restructure the normalised dictionary to the denormalised structure autoshift expects
def generateAutoshiftJSON(website_code_tables, previous_codes, include_expired):
    autoshiftcodes = []
    # WHY: If loader returned None/garbage, treat as "no previous codes" so helpers stay safe.
    if not isinstance(previous_codes, list):
        previous_codes = []
    newcodecount = 0
    for code_tables in website_code_tables:
        for code_table in code_tables:
            for code in code_table.get("codes"):

                # Validate and normalize the code field: only accept codes that
                # match five groups of five alphanumeric characters separated by
                # hyphens (e.g. AAAAA-BBBBB-CCCCC-DDDDD-EEEEE). Anything else
                # should be excluded from the output.
                raw_code = code.get("code")
                if raw_code:
                    raw_code = raw_code.strip().upper()
                else:
                    raw_code = None

                code_pattern = re.compile(r"^[A-Z0-9]{5}(?:-[A-Z0-9]{5}){4}$")
                if not raw_code or not code_pattern.fullmatch(raw_code):
                    _L.debug(
                        "Skipping non-matching shift code for %s on %s: %s",
                        code_table.get("game"),
                        code_table.get("platform"),
                        raw_code,
                    )
                    # skip rows that do not contain a valid code
                    continue

                # Skip the code if its expired and we're not to include expired
                if not include_expired and code.get("expired"):
                    continue

                # Extract out the previous archived date if the key existed previously
                archived = getPreviousCodeArchived(
                    code, code_table.get("game"), previous_codes
                )
                
                # WHY: Preserve 'expired' from a previous run when the newly scraped row
                # doesn't have a real expiry (e.g. "Unknown" or empty). This prevents
                # flipping an already-expired code back to active just because the source
                # now shows no explicit expiry.
                prev_entry = getPreviousCodeEntry(code, code_table.get("game"), previous_codes)
                if prev_entry and prev_entry.get("expired"):
                    new_expires = (code.get("expires") or "").strip()
                    if new_expires.lower() in ("", "unknown"):
                        code["expired"] = True
                # end preserve logic
                
                # WHY: Prefer identity check 'is None' with the singleton None (PEP 8) and avoid truthiness pitfalls.
                if archived is None:
                    # New code
                    archived = code_table.get("archived")
                    newcodecount += 1
                    # If any critical fields are missing, capture context for debugging and continue
                    if code.get("code") is None or code.get("reward") is None:
                        _L.error(
                            "Parsed code row missing fields for game=%s platform=%s: %s",
                            code_table.get("game"),
                            code_table.get("platform"),
                            code,
                        )
                        # write debugging info to a file for inspection
                        try:
                            debug_record = {
                                "game": code_table.get("game"),
                                "platform": code_table.get("platform"),
                                "sourceURL": code_table.get("sourceURL"),
                                "archived": str(code_table.get("archived")),
                                "row": code,
                            }
                            makedirs(path.join(DIRNAME, "data"), exist_ok=True)
                            fn = path.join(DIRNAME, "data", "debug_problem_rows.json")
                            # append JSON objects one per line so it's easy to inspect
                            with open(fn, "a") as df:
                                df.write(json.dumps(debug_record, default=str) + "\n")
                        except Exception as e:
                            _L.error("Failed to write debug file: %s", e)
                    # Use logger formatting (avoids concatenation when values may be None)
                    _L.info(
                        " Found new code: %s %s for %s on %s",
                        code.get("code"),
                        code.get("reward"),
                        code_table.get("game"),
                        code_table.get("platform"),
                    )

                if code_table.get("platform") == "pc":
                    autoshiftcodes.append(
                        {
                            "code": code.get("code"),
                            "type": "shift",
                            "game": code_table.get("game"),
                            "platform": "steam",
                            "reward": code.get("reward"),
                            "archived": archived,
                            "expires": code.get("expires"),
                            "expired": code.get("expired"),
                            "link": code_table.get("sourceURL"),
                        }
                    )
                    autoshiftcodes.append(
                        {
                            "code": code.get("code"),
                            "type": "shift",
                            "game": code_table.get("game"),
                            "platform": "epic",
                            "reward": code.get("reward"),
                            "archived": archived,
                            "expires": code.get("expires"),
                            "expired": code.get("expired"),
                            "link": code_table.get("sourceURL"),
                        }
                    )
                else:
                    autoshiftcodes.append(
                        {
                            "code": code.get("code"),
                            "type": "shift",
                            "game": code_table.get("game"),
                            "platform": code_table.get("platform"),
                            "reward": code.get("reward"),
                            "archived": archived,
                            "expires": code.get("expires"),
                            "expired": code.get("expired"),
                            "link": code_table.get("sourceURL"),
                        }
                    )

    # Add the metadata section:
    generatedDateAndTime = datetime.now(timezone.utc)
    metadata = {
        "version": "2",
        "description": "GitHub Alternate Source for Shift Codes",
        "attribution": "Data provided by https://mentalmars.com",
        "permalink": "https://raw.githubusercontent.com/zarmstrong/autoshift-codes/main/shiftcodes.json",
        "generated": {"human": generatedDateAndTime},
        "newcodecount": newcodecount,
    }

    autoshift = [{"meta": metadata, "codes": autoshiftcodes}]

    return autoshift
    # return json.dumps(autoshiftcodes,indent=2, default=str)


def run_migrations_on_shiftfile(shiftfile_path, previous_codes):
    """Run migrations against the loaded shiftcodes structure.

    Returns the (possibly modified) previous_codes structure and a boolean indicating if a migration was performed.
    """
    migration_performed = False
    if not previous_codes:
        return previous_codes, migration_performed

    try:
        meta = previous_codes[0].get("meta", {})
    except Exception:
        return previous_codes, migration_performed

    # If no version is set at all, initialise to version 1 and persist that
    if "version" not in meta:
        _L.info("Initial migration: setting shiftcodes file version to 1")
        previous_codes[0].setdefault("meta", {})["version"] = "1"
        try:
            with open(shiftfile_path, "w") as f:
                json.dump(previous_codes, f, indent=2, default=str)
            _L.info("Wrote initial version=1 to %s", shiftfile_path)
            migration_performed = True
        except Exception as e:
            _L.error("Failed to write initial-version shiftcodes file: %s", e)
        meta = previous_codes[0].get("meta", {})

    version = str(meta.get("version", "1"))
    # Treat "0.1" as equivalent to "1"
    if version == "0.1":
        version = "1"
        previous_codes[0]["meta"]["version"] = "1"
        try:
            with open(shiftfile_path, "w") as f:
                json.dump(previous_codes, f, indent=2, default=str)
            _L.info("Updated version 0.1 to 1 in %s", shiftfile_path)
            migration_performed = True
        except Exception as e:
            _L.error("Failed to update version from 0.1 to 1: %s", e)

    # if already >= 2 nothing to do
    if version >= "2":
        _L.debug("Shiftcodes file already at version %s, no migrations needed", version)
        return previous_codes, migration_performed

    # Migration: v1 -> v2
    if version == "1":
        _L.info("Running migration: v1 -> v2 on %s", shiftfile_path)
        # Only allow codes that match the 5x5 pattern
        pattern = re.compile(r"^[A-Z0-9]{5}(?:-[A-Z0-9]{5}){4}$")
        codes = previous_codes[0].get("codes", [])
        before_count = len(codes)
        filtered = []
        for c in codes:
            code_val = c.get("code")
            if code_val:
                code_val = str(code_val).strip().upper()
            if code_val and pattern.fullmatch(code_val):
                # keep original entry but normalise stored code to upper/stripped
                c["code"] = code_val
                filtered.append(c)
            else:
                _L.debug("Migration: dropping invalid code entry: %s", c)

        removed = before_count - len(filtered)
        previous_codes[0]["codes"] = filtered
        previous_codes[0].setdefault("meta", {})["version"] = "2"

        # Persist the migrated file back to disk
        try:
            with open(shiftfile_path, "w") as f:
                json.dump(previous_codes, f, indent=2, default=str)
            _L.info(
                "Migration complete: removed %d invalid codes, set version to 2",
                removed,
            )
            migration_performed = True
        except Exception as e:
            _L.error("Failed to write migrated shiftcodes file: %s", e)

    return previous_codes, migration_performed


def setup_argparser():
    import argparse

    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    # TODO add github repo and key here to publish to...
    parser.add_argument(
        "--schedule",
        type=str,
        const="2",
        nargs="?",
        help="Schedule interval. Append 'm' for minutes (e.g. '30m') otherwise treated as hours (e.g. '2' or '1.5').",
    )
    parser.add_argument(
        "-v", "--verbose", dest="verbose", action="store_true", help="Verbose mode"
    )
    # secret flag to allow official scraper to override the 2-hour minimum
    parser.add_argument(
        "--officialscraper",
        dest="officialscraper",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-u",
        "--user",
        default=None,
        help=("GitHub Username that hosts the repo to push into"),
    )
    parser.add_argument(
        "-r",
        "--repo",
        default=None,
        help=("GitHub Repository to push the shiftcodes into (i.e. autoshift-codes)"),
    )
    parser.add_argument(
        "-t", "--token", default=None, help=("GitHub Authentication token to use ")
    )
    return parser


def scrape_polygon_bl4_codes(existing_codes_set):
    url = "https://www.polygon.com/borderlands-4-active-shift-codes-redeem/"
    try:
        _L.info("Requesting Polygon BL4 codes: " + url)
        # add a simple user-agent to reduce chance of being blocked
        r = requests.get(
            url, timeout=15, headers={"User-Agent": "autoshift-scraper/1.0"}
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")

        # 1) Try the exact id-based approach first (legacy)
        header = soup.find(
            lambda tag: tag.name in ["h1", "h2", "h3", "h4"]
            and tag.get("id") == "all-borderlands-4-shift-codes"
        )

        # 2) If not found, try to find a header whose text mentions Borderlands 4 and shift/shift codes
        if not header:
            for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
                txt = tag.get_text(" ", strip=True).lower()
                if "borderlands 4" in txt and "shift" in txt:
                    header = tag
                    break

        codes = []
        parsed_total = 0
        duplicates_existing = 0
        duplicates_inpage = 0

        # Helper to parse LI text for a code + reward
        def parse_li_text(text):
            # find a 5x5 code anywhere in the text
            code_match = re.search(r"([A-Za-z0-9]{5}(?:-[A-Za-z0-9]{5}){4})", text)
            if not code_match:
                return None
            code = code_match.group(1).upper()
            # reward is often in parentheses — if present, grab it
            reward_match = re.search(r"\(([^)]+)\)", text)
            reward = reward_match.group(1).strip() if reward_match else "Unknown"
            return {
                "code": code,
                "reward": reward,
                "expires": "Unknown",
                "expired": False,
            }

        # If we found a header, try to parse the immediate list after it
        if header:
            ul = header.find_next(["ul", "ol"])
            if ul:
                _L.debug("Polygon BL4: scanning list after detected header")
                for li in ul.find_all("li"):
                    text = li.get_text(" ", strip=True)
                    parsed = parse_li_text(text)
                    if not parsed:
                        _L.debug("Polygon BL4: could not parse li: %s", text)
                        continue
                    parsed_total += 1
                    if parsed["code"] in existing_codes_set:
                        duplicates_existing += 1
                        _L.debug(
                            "Polygon BL4: Skipping duplicate code (already present): %s",
                            parsed["code"],
                        )
                        continue
                    if any(c["code"] == parsed["code"] for c in codes):
                        duplicates_inpage += 1
                        _L.debug(
                            "Polygon BL4: Skipping duplicate code (in-page): %s",
                            parsed["code"],
                        )
                        continue
                    codes.append(parsed)
            else:
                _L.debug("Polygon BL4: header found but no following list element")

        # Fallback: scan all lists on the page if nothing matched so far
        if not codes:
            _L.debug(
                "Polygon BL4: header-based parse yielded no codes, scanning all lists as fallback"
            )
            for ul in soup.find_all(["ul", "ol"]):
                for li in ul.find_all("li"):
                    text = li.get_text(" ", strip=True)
                    parsed = parse_li_text(text)
                    if not parsed:
                        continue
                    parsed_total += 1
                    if parsed["code"] in existing_codes_set:
                        duplicates_existing += 1
                        continue
                    if any(c["code"] == parsed["code"] for c in codes):
                        duplicates_inpage += 1
                        continue
                    codes.append(parsed)

        new_count = len(codes)
        # Report new codes and duplicate counts as standard info output
        _L.info(
            "Polygon BL4: Found %d new candidate codes (parsed %d candidates, %d duplicates already present, %d duplicates in-page)",
            new_count,
            parsed_total,
            duplicates_existing,
            duplicates_inpage,
        )
        return codes
    except Exception as e:
        _L.error(f"Polygon BL4: Error scraping codes: {e}")
        return []


def scrape_ign_bl4_codes(existing_codes_set):
    """
    Parse IGN wiki for Borderlands 4 SHiFT codes.
    Strategy:
      - fetch page, scan all tables (rows) and list items for any 5x5 code pattern
      - extract reward from parentheses if present, detect 'expired' if strikethrough or text contains 'expired'
      - return list of dicts matching other parsers: {code,reward,expires,expired}
      - log counts: parsed candidates, duplicates already present, in-page duplicates, new found
    """
    url = "https://www.ign.com/wikis/borderlands-4/Borderlands_4_SHiFT_Codes"
    # always log intent to request before doing the network call so the entry appears in logs
    _L.info("Requesting IGN BL4 codes: " + url)
    try:
        r = requests.get(
            url, timeout=15, headers={"User-Agent": "autoshift-scraper/1.0"}
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")

        code_re = re.compile(r"([A-Za-z0-9]{5}(?:-[A-Za-z0-9]{5}){4})")
        codes = []
        parsed_total = 0
        duplicates_existing = 0
        duplicates_inpage = 0

        def extract_from_text(text, row_tag=None):
            m = code_re.search(text)
            if not m:
                return None
            code = m.group(1).upper()
            # reward in parentheses if present
            rm = re.search(r"\(([^)]+)\)", text)
            reward = rm.group(1).strip() if rm else "Unknown"
            # detect expired via explicit word or <s> in the provided tag if available
            expired = False
            if row_tag is not None:
                if row_tag.find("s") is not None:
                    expired = True
            if "expired" in text.lower():
                expired = True
            return {
                "code": code,
                "reward": reward,
                "expires": "Unknown",
                "expired": expired,
            }

        # 1) Scan all tables' rows
        for table in soup.find_all("table"):
            tbody = table.find("tbody") or table
            for tr in tbody.find_all("tr"):
                row_text = tr.get_text(" ", strip=True)
                parsed_total += 1
                parsed = extract_from_text(row_text, tr)
                if not parsed:
                    continue
                if parsed["code"] in existing_codes_set:
                    duplicates_existing += 1
                    continue
                if any(c["code"] == parsed["code"] for c in codes):
                    duplicates_inpage += 1
                    continue
                codes.append(parsed)

        # 2) Fallback: scan list items across the page
        for ul in soup.find_all(["ul", "ol"]):
            for li in ul.find_all("li"):
                li_text = li.get_text(" ", strip=True)
                parsed_total += 1
                parsed = extract_from_text(li_text, li)
                if not parsed:
                    continue
                if parsed["code"] in existing_codes_set:
                    duplicates_existing += 1
                    continue
                if any(c["code"] == parsed["code"] for c in codes):
                    duplicates_inpage += 1
                    continue
                codes.append(parsed)

        new_count = len(codes)
        _L.info(
            "IGN BL4: Found %d new candidate codes (parsed %d candidates, %d duplicates already present, %d duplicates in-page)",
            new_count,
            parsed_total,
            duplicates_existing,
            duplicates_inpage,
        )
        return codes
    except Exception as e:
        _L.error(f"IGN BL4: Error scraping codes: {e}")
        return []


def scrape_xsmash_codes(existing_codes_set):
    """
    Parse xsmashx88x Shift-Codes gh-pages index.html for SHiFT codes by extracting the
    ALL_CODES_CONFIG JavaScript array. Returns list of dicts: {code, reward, expires, expired}.
    """
    url = "https://raw.githubusercontent.com/xsmashx88x/Shift-Codes/refs/heads/gh-pages/index.html"
    try:
        _L.info("Requesting xsmashx88x Shift-Codes page: " + url)
        r = requests.get(
            url, timeout=15, headers={"User-Agent": "autoshift-scraper/1.0"}
        )
        r.raise_for_status()
        text = r.text

        # Find the ALL_CODES_CONFIG array block
        m = re.search(
            r"ALL_CODES_CONFIG\s*=\s*\[(.*?)\]\s*;", text, re.DOTALL | re.IGNORECASE
        )
        if not m:
            _L.debug("xsmash: ALL_CODES_CONFIG not found in page")
            return []

        array_body = m.group(1)

        # Split into individual JS object blocks by finding balanced braces roughly.
        # Simpler approach: find all occurrences of "code:" within the array and parse nearby fields.
        entry_re = re.compile(
            r"""
            \{
            (?:(?:(?!\{).)*?)?                # non-greedy consume until fields
            code\s*:\s*['"](?P<code>[A-Za-z0-9\-]+)['"]\s*,  # code field
            (?:(?:(?!\{).)*?)?
            (?:expires\s*:\s*createDate\((?P<expires>[^)]*)\))?  # optional expires createDate(...)
            (?:(?:(?!\{).)*?)
            (?:title\s*:\s*(?P<title>(?:'[^']*'|"[^"]*")))?
            """,
            re.DOTALL | re.VERBOSE | re.IGNORECASE,
        )

        candidates = []
        parsed_total = 0
        duplicates_existing = 0
        duplicates_inpage = 0

        for em in entry_re.finditer(array_body):
            parsed_total += 1
            code = em.group("code")
            if not code:
                continue
            code = code.strip().upper()

            # skip if already present
            if code in existing_codes_set:
                duplicates_existing += 1
                continue
            if any(c["code"] == code for c in candidates):
                duplicates_inpage += 1
                continue

            # extract and clean title -> reward text
            raw_title = em.group("title")
            reward = "Unknown"
            if raw_title:
                # strip surrounding quotes
                raw_title = raw_title.strip()
                if (raw_title.startswith("'") and raw_title.endswith("'")) or (
                    raw_title.startswith('"') and raw_title.endswith('"')
                ):
                    raw_title = raw_title[1:-1]
                # remove HTML tags (use BeautifulSoup)
                try:
                    reward = BeautifulSoup(raw_title, "html.parser").get_text(
                        " ", strip=True
                    )
                    # sometimes title has leading "1 : Gold Key - ..." — try to extract reward portion
                    # split off leading numeric index and colon
                    parts = reward.split(":", 1)
                    if len(parts) == 2:
                        after = parts[1].strip()
                        # take text up to first " - " or "|" as reward
                        reward = re.split(r"\s[-|]\s", after)[0].strip() or reward
                except Exception:
                    reward = raw_title

            # parse expires createDate args if present
            expires_raw = em.group("expires")
            expires_str = "Unknown"
            expired_flag = False
            if expires_raw:
                # split numbers (allow spaces)
                nums = [
                    n.strip() for n in re.split(r"\s*,\s*", expires_raw) if n.strip()
                ]
                try:
                    # map to ints where possible
                    nums_int = [int(float(n)) for n in nums[:6]]  # year,month,day,h,m,s
                    # JS months may be 0-indexed in some docs — we assume given month is 1-based unless obviously out of range
                    year = nums_int[0]
                    month = nums_int[1] if len(nums_int) > 1 else 1
                    day = nums_int[2] if len(nums_int) > 2 else 1
                    hour = nums_int[3] if len(nums_int) > 3 else 0
                    minute = nums_int[4] if len(nums_int) > 4 else 0
                    second = nums_int[5] if len(nums_int) > 5 else 0
                    # sanity: clamp month to 1..12; if month==0 assume 0-indexed and add 1
                    if month == 0:
                        month = 1
                    if month > 12:
                        # if >12, treat as 0-indexed (unlikely) by adding 1 then wrapping, but safest is cap
                        month = max(1, min(12, month))
                    try:
                        dt = datetime(
                            year, month, day, hour, minute, second, tzinfo=timezone.utc
                        )
                        expires_str = dt.isoformat()
                        # set expired flag if now > dt
                        expired_flag = datetime.now(timezone.utc) > dt
                    except Exception:
                        expires_str = expires_raw.strip()
                except Exception:
                    expires_str = expires_raw.strip()

            candidates.append(
                {
                    "code": code,
                    "reward": reward,
                    "expires": expires_str,
                    "expired": expired_flag,
                }
            )

        new_count = len(candidates)
        _L.info(
            "xsmash: Found %d new candidate codes (parsed %d candidates, %d duplicates already present, %d duplicates in-page)",
            new_count,
            parsed_total,
            duplicates_existing,
            duplicates_inpage,
        )
        return candidates
    except Exception as e:
        _L.error(f"xsmash parser: Error scraping codes: {e}")
        return []


# small helper to interpret schedule strings
def parse_schedule_arg(schedule_str):
    """
    Returns tuple (mode, value) where mode is 'minutes' or 'hours'.
    Accepts:
      - "30m" / "30M" => ('minutes', 30)
      - "2" / "1.5" / "2.0" => ('hours', 2.0)
    Returns None on invalid input.
    """
    if schedule_str is None:
        return None
    s = str(schedule_str).strip()
    if s.lower().endswith("m"):
        num = s[:-1].strip()
        try:
            minutes = int(float(num))
            if minutes <= 0:
                return None
            # enforce minimum 15 minutes
            if minutes < 15:
                _L.warning(
                    "Schedule value too short (%dm). Enforcing minimum of 15m.", minutes
                )
                minutes = 15
            return ("minutes", minutes)
        except Exception:
            return None
    else:
        try:
            hours = float(s)
            if hours <= 0:
                return None
            return ("hours", hours)
        except Exception:
            return None


def main(args):

    # Setup json output folder
    makedirs(path.join(DIRNAME, "data"), exist_ok=True)
    Path("data/shiftcodes.json").touch()

    # print(json.dumps(webpages,indent=2, default=str))
    codes_inc_expired = []
    codes_excl_expired = []
    code_tables = []

    # Read in the previous codes so we can retain timestamps and know how many are new
    with open(SHIFTCODESJSONPATH, "rb") as f:
        try:
            previous_codes = json.loads(f.read())
        except:
            previous_codes = None
            pass
    # Run any migrations on the previous codes file to bring it up to date
    previous_codes, migration_performed = run_migrations_on_shiftfile(
        SHIFTCODESJSONPATH, previous_codes
    )

    # Scrape the source webpage into a normalised Dictionary
    for webpage in webpages:
        code_tables.append(scrape_codes(webpage))

    # Convert the normalised Dictionary into the denormalised autoshift structure
    codes_inc_expired = generateAutoshiftJSON(code_tables, previous_codes, True)
    codes_excl_expired = generateAutoshiftJSON(code_tables, previous_codes, False)

    # --- Polygon BL4 scraper: run after all other parsers ---
    # Build a set of all codes already present (case-insensitive)
    existing_codes_set = set()
    for code_entry in codes_inc_expired[0].get("codes", []):
        code_val = code_entry.get("code")
        if code_val:
            existing_codes_set.add(code_val.upper())

    polygon_bl4_codes = scrape_polygon_bl4_codes(existing_codes_set)
    if polygon_bl4_codes:
        # Find the Borderlands 4 universal code_table in code_tables
        for code_table_list in code_tables:
            for code_table in code_table_list:
                if (
                    code_table.get("game") == "Borderlands 4"
                    and code_table.get("platform") == "universal"
                ):
                    # Add new codes to this table
                    code_table["codes"].extend(polygon_bl4_codes)
                    _L.info(
                        f"Polygon BL4: Added {len(polygon_bl4_codes)} codes to Borderlands 4 universal"
                    )
                    break

        # Re-generate the output JSONs with the new codes included
        codes_inc_expired = generateAutoshiftJSON(code_tables, previous_codes, True)
        codes_excl_expired = generateAutoshiftJSON(code_tables, previous_codes, False)

    # --- IGN BL4 scraper: run after Polygon (rebuild existing set from latest data) ---
    existing_codes_set = set()
    for code_entry in codes_inc_expired[0].get("codes", []):
        code_val = code_entry.get("code")
        if code_val:
            existing_codes_set.add(code_val.upper())

    # log the invocation from main so it's visible in the main flow
    _L.info("Invoking IGN BL4 parser")
    ign_bl4_codes = scrape_ign_bl4_codes(existing_codes_set)
    if ign_bl4_codes:
        for code_table_list in code_tables:
            for code_table in code_table_list:
                if (
                    code_table.get("game") == "Borderlands 4"
                    and code_table.get("platform") == "universal"
                ):
                    code_table["codes"].extend(ign_bl4_codes)
                    _L.info(
                        f"IGN BL4: Added {len(ign_bl4_codes)} codes to Borderlands 4 universal"
                    )
                    break

        # Re-generate the output JSONs with the new codes included
        codes_inc_expired = generateAutoshiftJSON(code_tables, previous_codes, True)
        codes_excl_expired = generateAutoshiftJSON(code_tables, previous_codes, False)

    # --- xsmashx88x GH-Pages scraper: run after IGN (rebuild existing set from latest data) ---
    existing_codes_set = set()
    for code_entry in codes_inc_expired[0].get("codes", []):
        code_val = code_entry.get("code")
        if code_val:
            existing_codes_set.add(code_val.upper())

    xsmash_codes = scrape_xsmash_codes(existing_codes_set)
    if xsmash_codes:
        for code_table_list in code_tables:
            for code_table in code_table_list:
                if (
                    code_table.get("game") == "Borderlands 4"
                    and code_table.get("platform") == "universal"
                ):
                    code_table["codes"].extend(xsmash_codes)
                    _L.info(
                        f"xsmash: Added {len(xsmash_codes)} codes to Borderlands 4 universal"
                    )
                    break

        # Re-generate the output JSONs with the new codes included
        codes_inc_expired = generateAutoshiftJSON(code_tables, previous_codes, True)
        codes_excl_expired = generateAutoshiftJSON(code_tables, previous_codes, False)

    _L.info("Scraping Complete. Now writing out shiftcodes.json file")

    _L.info(
        "Found "
        + str(codes_inc_expired[0].get("meta").get("newcodecount"))
        + " new codes."
    )

    # Write out the file even if no new codes so we can track last scrape time
    with open(SHIFTCODESJSONPATH, "w") as write_file:
        json.dump(codes_inc_expired, write_file, indent=2, default=str)

    # Commit the new file to GitHub publically if the args are set:
    if args.user and args.repo and args.token:
        # Only commit if there are new codes or if a migration was performed
        if (
            codes_inc_expired[0].get("meta").get("newcodecount") > 0
            or migration_performed
        ):
            _L.info("Connecting to GitHub repo: " + args.user + "/" + args.repo)
            # Connect to GitHub
            file_path = SHIFTCODESJSONPATH
            g = Github(args.token)
            repo = g.get_repo(args.user + "/" + args.repo)

            # Read in the latest file
            _L.info("Read in shiftcodes file")
            with open(file_path, "rb") as f:
                file_to_commit = f.read()

            # Push to GitHub:
            _L.info("Push and Commit")
            contents = repo.get_contents(
                "shiftcodes.json", ref="main"
            )  # Retrieve old file to get its SHA and path
            commit_msg = (
                "added new codes"
                if codes_inc_expired[0].get("meta").get("newcodecount") > 0
                else "migrated shiftcodes file"
            )
            commit_return = repo.update_file(
                contents.path,
                commit_msg,
                file_to_commit,
                contents.sha,
                branch="main",
            )  # Add, commit and push branch
            _L.info("GitHub result: " + str(commit_return))
        else:
            _L.info(
                "Not committing to GitHub as there are no new codes and no migration."
            )


if __name__ == "__main__":
    import os

    # build argument parser
    parser = setup_argparser()
    args = parser.parse_args()

    # Setup the logger
    _L.setLevel(INFO)
    if args.verbose:
        _L.setLevel(DEBUG)
        _L.debug("Debug mode on")

    # execute the main function at least once (and only once if scheduler is not set)
    main(args)

    # scheduling: accept minutes when user supplies e.g. "30m", otherwise treat as hours
    sched = parse_schedule_arg(args.schedule)
    if sched:
        mode, val = sched
        from apscheduler.schedulers.blocking import BlockingScheduler

        scheduler = BlockingScheduler()
        if mode == "hours":
            hours = float(val)
            if hours < 2:
                if getattr(args, "officialscraper", False):
                    _L.info(
                        "Official scraper override enabled; scheduling every %.2f hours",
                        hours,
                    )
                else:
                    _L.warning(
                        f"Running this tool every {hours} hours would result in too many requests.\n"
                        "Scheduling changed to run every 2 hours!"
                    )
                    hours = 2.0
            # robust: convert total hours to total minutes (rounded) then split
            total_minutes = int(round(hours * 60))
            h, m = divmod(total_minutes, 60)
            _L.info(f"Scheduling to run every {h:02}:{m:02} hours")
            scheduler.add_job(main, "interval", args=(args,), hours=hours)
        else:  # minutes
            minutes = int(val)
            hh = minutes // 60
            mm = minutes % 60
            _L.info(f"Scheduling to run every {hh:02}:{mm:02} (hh:mm)")
            scheduler.add_job(main, "interval", args=(args,), minutes=minutes)

        print(f"Press Ctrl+{'Break' if os.name == 'nt' else 'C'} to exit")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass
    else:
        # invalid or no schedule specified -> no scheduler started
        if args.schedule:
            _L.error("Invalid schedule argument provided: %s", args.schedule)

    _L.info("Goodbye.")
