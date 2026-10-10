import re
from datetime import datetime


def format_to_standard_date(date_str):
    if not date_str or date_str in ["NOT FOUND", "FAILED TO EXTRACT"]:
        return "NOT FOUND"

    formats = [
        "%Y/%m/%d %H:%M:%S",  # Matches 2026/09/17 12:00:00
        "%Y/%m/%d %H:%M",     # Matches 2026/09/17 12:00
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d",           # Matches 2026/09/17
        "%Y-%m-%d",
    ]

    cleaned = date_str.strip()
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            try:
                return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d 00:00")
            except ValueError:
                pass

    return date_str


WANHAI_MAIN_URL = "https://www.wanhai.com/views/Main.xhtml"
WANHAI_TRACKING_LIST_URL = "https://www.wanhai.com/views/cargo_track_v2/tracking_data_list.xhtml"


def track_wanhai(p, booking_number, target_pol=None):
    is_cdp = False
    try:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]

        # Purge extra tabs from previous runs
        while len(context.pages) > 1:
            try:
                context.pages[-1].close()
            except Exception:
                break

        page1 = context.new_page()
        is_cdp = True
    except Exception:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page1 = context.new_page()

    created_pages = [page1]

    try:
        # STEP 1: Open Main page & query booking number
        page1.goto(WANHAI_MAIN_URL, wait_until="domcontentloaded")
        page1.wait_for_timeout(2000)

        target_context = page1
        for frame in page1.frames:
            if "cargo" in frame.url.lower() or "track" in frame.url.lower():
                target_context = frame
                break

        search_input = target_context.locator("input[type='text'], input[name*='Search']").first
        if search_input.is_visible(timeout=5000):
            search_input.click()
            search_input.fill("")
            search_input.fill(booking_number)

            query_btn = target_context.locator("input[type='submit'], button:has-text('Query')").first
            if query_btn.is_visible():
                query_btn.click()
            else:
                target_context.keyboard.press("Enter")

            page1.wait_for_timeout(3500)

        # STEP 2: Open tracking_data_list.xhtml in a fresh tab (Page 2 tab)
        page2 = context.new_page()
        created_pages.append(page2)
        page2.goto(WANHAI_TRACKING_LIST_URL, wait_until="domcontentloaded")
        page2.wait_for_timeout(2500)

        # STEP 3: Click Booking Data / B/L Data on Page 2 tab to trigger Page 3
        page3 = None
        try:
            link_selector = "a:has-text('Booking Data'), a:has-text('B/L Data')"
            detail_link = page2.locator(link_selector).first

            if detail_link.is_visible(timeout=5000):
                with context.expect_page(timeout=8000) as popup_info:
                    detail_link.click()

                page3 = popup_info.value
                created_pages.append(page3)
                page3.wait_for_load_state("domcontentloaded")
                page3.wait_for_timeout(2500)
        except Exception as e:
            print(f"    Notice: Transition to Page 3 detail skipped ({e})")

        # Fallback tab selection if expect_page didn't grab the handle
        if not page3 and len(context.pages) > len(created_pages):
            page3 = context.pages[-1]

        target_page = page3 if page3 else page2
        body_text = target_page.locator("body").inner_text()

        # STEP 4: Parse final details
        vessel_name = "WAN HAI VESSEL"
        voyage_code = "UNKNOWN"
        pol_name = target_pol if target_pol and target_pol != "UNKNOWN" else "UNKNOWN"
        doc_cutoff = "NOT FOUND"

        # Extract Vessel Name
        vessel_match = re.search(r"Vessel\s+Name\s+([A-Za-z0-9\s]+?)(?=\s+Voyage|\n|$)", body_text, re.I)
        if vessel_match and vessel_match.group(1).strip() not in ["More detail", "Vessel"]:
            vessel_name = vessel_match.group(1).strip()

        # Extract Voyage Code
        voyage_match = re.search(r"Voyage\s+([A-Z0-9]+)", body_text, re.I)
        if voyage_match and voyage_match.group(1).strip() not in ["Vessel", "More detail"]:
            voyage_code = voyage_match.group(1).strip()

        # Extract POL
        pol_match = re.search(r"Port\s+of\s+Loading\s+([A-Za-z\s]+)", body_text, re.I)
        if pol_match and pol_name == "UNKNOWN":
            pol_name = pol_match.group(1).strip()

        # Extract Doc Cutoff Date
        cutoff_match = re.search(
            r"Doc\s+Cutoff\s+Date\s+(\d{4}/\d{2}/\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)",
            body_text,
            re.IGNORECASE,
        )
        if cutoff_match:
            doc_cutoff = cutoff_match.group(1).strip()

        # STEP 5: Close all created tabs cleanly for the current booking loop
        if is_cdp:
            for p_tab in created_pages:
                try:
                    p_tab.close()
                except Exception:
                    pass

        return {
            "vessel": vessel_name,
            "voyage": voyage_code,
            "pol": pol_name,
            "doc_si_cutoff": format_to_standard_date(doc_cutoff),
        }

    finally:
        if not is_cdp:
            context.close()
            browser.close()