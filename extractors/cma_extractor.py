import re
from datetime import datetime

PORT_ALIASES = {
    "LAX/LGB": "LOS ANGELES",
    "LAX": "LOS ANGELES",
    "LGB": "LONG BEACH",
    "OAK": "OAKLAND",
    "NYC": "NEW YORK",
    "SAV": "SAVANNAH",
    "CHI": "CHICAGO",
}


def format_to_standard_date(date_str):
    if not date_str or date_str in ["NOT FOUND", "FAILED TO EXTRACT"]:
        return "NOT FOUND"

    formats = [
        "%d-%b-%Y %I:%M %p",  # Matches 29-SEP-2026 05:00 PM
        "%d-%b-%Y %H:%M",     # Matches 29-SEP-2026 17:00
        "%b-%d-%Y %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
    ]

    cleaned = date_str.strip()
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass

    return date_str


CMA_URL = "https://www.cma-cgm.com/ebusiness/tracking"


def track_cma(p, booking_number, target_pol=None):
    is_cdp = False
    try:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.new_page()
        is_cdp = True
    except Exception:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

    try:
        page.goto(CMA_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # 1. Fill Search Input
        try:
            search_input = page.get_by_role("textbox").first
            if search_input.is_visible(timeout=5000):
                search_input.click()
                search_input.fill("")
                search_input.fill(booking_number)
                page.keyboard.press("Enter")
                page.wait_for_timeout(3500)
        except Exception as e:
            print(f"    Notice: Search input issue ({e})")

        # Wait for Page 1 results table
        try:
            page.wait_for_selector("tbody tr", timeout=10000)
        except Exception:
            page.wait_for_timeout(3000)

        # ------------------------------------------------------
        # 1.5. Expand "Display Previous Moves" if present
        # ------------------------------------------------------
        try:
            prev_moves_link = page.locator("a[aria-label='Display Previous Moves'], a:has-text('Display Previous Moves')").first
            if prev_moves_link.count() > 0 and prev_moves_link.is_visible(timeout=3000):
                prev_moves_link.click()
                page.wait_for_timeout(2000)
        except Exception as e:
            print(f"    Notice: No 'Display Previous Moves' link or already expanded ({e})")

        # ------------------------------------------------------
        # 2. Extract POL from Page 1 (Badge or Row Location)
        # ------------------------------------------------------
        extracted_pol = "UNKNOWN"
        body_text_p1 = page.locator("body").inner_text()

        pol_badge_match = re.search(r"POL\s*\n?\s*([A-Za-z\s]+?)(?:,\s*[A-Z]{2}|\(|\n|$)", body_text_p1, re.I)
        if pol_badge_match and "TRACKING" not in pol_badge_match.group(1):
            extracted_pol = pol_badge_match.group(1).strip()
        else:
            try:
                row_loc = page.locator("tbody tr").first.locator("td").nth(2).inner_text()
                extracted_pol = row_loc.split("\n")[0].split(",")[0].strip()
            except Exception:
                pass

        final_pol = target_pol.strip() if target_pol and target_pol != "UNKNOWN" else extracted_pol

        # ------------------------------------------------------
        # 3. Click Voyage Link to Navigate to Page 2 Schedule
        # ------------------------------------------------------
        try:
            voyage_anchor = page.locator("tbody tr td a:nth-of-type(2)").first
            if voyage_anchor.is_visible(timeout=4000):
                voyage_anchor.click()
            else:
                page.evaluate("""() => {
                    const row = document.querySelector('tbody tr');
                    if (row) {
                        const links = row.querySelectorAll('a');
                        if (links.length >= 2) links[1].click();
                        else if (links.length === 1) links[0].click();
                    }
                }""")

            page.wait_for_timeout(3500)
        except Exception as e:
            print(f"    Notice: Page 2 transition skipped ({e})")

        # ------------------------------------------------------
        # 4. Extract Vessel & Voyage directly from ul.resume-filter (DOM)
        # ------------------------------------------------------
        vessel_name = "CMA VESSEL"
        voyage_code = "UNKNOWN"

        try:
            # Direct DOM extraction from ul.resume-filter as seen in DevTools
            header_data = page.evaluate("""() => {
                const ul = document.querySelector('ul.resume-filter');
                if (!ul) return null;
                const lis = ul.querySelectorAll('li');
                
                let voy = '';
                let ves = '';
                
                if (lis.length >= 1) {
                    const voyElem = lis[0].querySelector('strong');
                    if (voyElem) voy = voyElem.innerText.strip ? voyElem.innerText.strip() : voyElem.innerText;
                }
                if (lis.length >= 2) {
                    const vesElem = lis[1].querySelector('strong') || lis[1].querySelector('a');
                    if (vesElem) ves = vesElem.innerText.strip ? vesElem.innerText.strip() : vesElem.innerText;
                }
                
                return { voyage: voy.trim(), vessel: ves.trim() };
            }""")

            if header_data:
                if header_data.get("voyage"):
                    voyage_code = header_data["voyage"]
                if header_data.get("vessel"):
                    vessel_name = header_data["vessel"]
        except Exception as e:
            print(f"    Notice: Direct DOM extraction error ({e})")

        # Fallback to RegEx if DOM query returned empty
        if vessel_name == "CMA VESSEL" or voyage_code == "UNKNOWN":
            p2_body_text = page.locator("body").inner_text()
            header_match = re.search(
                r"Voyage\s+([A-Z0-9]+)\s*(?:•|\s+)\s*Vessel\s+([A-Za-z0-9\s]+?)(?=\s*(?:•|Modify|\n|$))",
                p2_body_text,
                re.IGNORECASE,
            )
            if header_match:
                if voyage_code == "UNKNOWN":
                    voyage_code = header_match.group(1).strip()
                if vessel_name == "CMA VESSEL":
                    vessel_name = header_match.group(2).strip()

        # Clean Vessel Name formatting
        vessel_name = vessel_name.split("\n")[0].strip()
        vessel_name = re.sub(r"^(?:CA|US|[A-Z]{2})\s+|\b(?:EVERPORT|TERMINAL|PORT)\b\s*", "", vessel_name, flags=re.I).strip()

        # ------------------------------------------------------
        # 5. Extract SI Cut-off Date for Target POL (Page 2 Table)
        # ------------------------------------------------------
        p2_body_text = page.locator("body").inner_text()
        doc_cutoff = "NOT FOUND"

        if final_pol.upper() in p2_body_text.upper():
            port_section = re.split(rf"{final_pol}", p2_body_text, flags=re.IGNORECASE)[-1]
            date_matches = re.findall(r"(\d{2}-[A-Za-z]{3}-\d{4}\s+\d{2}:\d{2}\s+[AP]M)", port_section)

            if len(date_matches) >= 7:
                doc_cutoff = date_matches[6].strip()
            elif len(date_matches) >= 6:
                doc_cutoff = date_matches[5].strip()
            elif len(date_matches) > 0:
                doc_cutoff = date_matches[-1].strip()

        if is_cdp:
            try:
                page.close()
            except Exception:
                pass

        return {
            "vessel": vessel_name,
            "voyage": voyage_code,
            "pol": final_pol,
            "doc_si_cutoff": format_to_standard_date(doc_cutoff),
        }

    finally:
        if not is_cdp:
            context.close()
            browser.close()