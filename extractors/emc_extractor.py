import re
from datetime import datetime
from playwright.sync_api import TimeoutError


def format_to_standard_date(date_str):
    if not date_str or date_str in ["NOT FOUND", "FAILED TO EXTRACT"]:
        return "NOT FOUND"

    formats = [
        "%b-%d-%Y %H:%M",  # Matches OCT-14-2026 16:00
        "%b-%d-%Y",        # Matches OCT-14-2026
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]

    cleaned = date_str.strip()
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass

    return date_str


EVERGREEN_URL = "https://ct.shipmentlink.com/servlet/TDB1_CargoTracking.do"


def track_emc(p, booking_number):
    # Launches standard Playwright Chromium browser (No debugging mode / CDP)
    browser = p.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"]
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    try:
        # 1. Open Tracking Page
        page.goto(EVERGREEN_URL, wait_until="domcontentloaded")

        # 2. Accept Cookies if present
        try:
            accept_btn = page.get_by_text("Accept All", exact=True)
            if accept_btn.is_visible(timeout=3000):
                accept_btn.click()
        except TimeoutError:
            pass

        # 3. Select Booking No. Radio Button & Input Booking Number
        try:
            page.get_by_role("radio", name="Booking No.").check(timeout=3000)
        except Exception:
            page.locator("#nav-quick").get_by_text("Booking No.").click()

        page.locator("#NO").click()
        page.locator("#NO").fill("")
        page.locator("#NO").fill(booking_number)

        # 4. Submit Search
        page.get_by_role("button", name="Submit").click()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)

        # ------------------------------------------------------
        # 5. Extract Vessel & Voyage directly from DOM Table Cell
        # ------------------------------------------------------
        vessel_name = "EVERGREEN VESSEL"
        voyage_code = "UNKNOWN"

        try:
            # Query the <td> cell right next to <th>Vessel Voyage</th>
            raw_vv_text = page.evaluate("""() => {
                const ths = Array.from(document.querySelectorAll('th'));
                const vvHeader = ths.find(th => th.innerText.includes('Vessel Voyage'));
                if (vvHeader && vvHeader.nextElementSibling) {
                    return vvHeader.nextElementSibling.innerText;
                }
                return '';
            }""")

            if raw_vv_text:
                # Strip Chinese characters in parentheses e.g. (長理輪)
                clean_vv = re.sub(r"[\(\（][^\)\〕]*[\)\）]", "", raw_vv_text).strip()

                # Match format: "CMA CGM JEAN GABRIEL MTE030W19" or "EVER LOGIC 1239-087W"
                match = re.search(r"^(.*?)\s+([A-Z0-9\-]+)$", clean_vv)
                if match:
                    vessel_name = match.group(1).strip()
                    voyage_code = match.group(2).strip()
                else:
                    vessel_name = clean_vv
        except Exception as e:
            print(f"    Notice: Vessel/Voyage parse issue ({e})")

        # ------------------------------------------------------
        # 6. Extract POL & Cut Off Date from Page Text
        # ------------------------------------------------------
        body_text = page.locator("body").inner_text()

        # POL Extraction -> "Port of Loading OAKLAND, CA (US)"
        pol_name = "UNKNOWN"
        pol_match = re.search(r"Port of Loading\s+([A-Za-z\s,]+(?:\([A-Z]{2}\))?)", body_text, re.I)
        if pol_match:
            pol_name = pol_match.group(1).strip()
            pol_name = re.sub(r"\s*\([A-Z]{2}\)", "", pol_name).strip()

        # Cut Off Date Extraction -> "Cut Off Date OCT-14-2026"
        doc_cutoff = "NOT FOUND"
        cutoff_match = re.search(r"Cut Off Date\s+([A-Za-z]{3}-\d{2}-\d{4})", body_text, re.I)
        if cutoff_match:
            # Defaults time to 16:00 if only date is provided
            doc_cutoff = cutoff_match.group(1).strip() + " 16:00"

        return {
            "vessel": vessel_name,
            "voyage": voyage_code,
            "pol": pol_name,
            "doc_si_cutoff": format_to_standard_date(doc_cutoff),
        }

    finally:
        context.close()
        browser.close()