import re
from datetime import datetime
from playwright.sync_api import TimeoutError


def format_to_standard_date(date_str):
    if not date_str or date_str in ["NOT FOUND", "FAILED TO EXTRACT"]:
        return "NOT FOUND"

    formats = [
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%b-%d-%Y %H:%M",
        "%d/%m/%Y %H:%M",
    ]

    cleaned = date_str.strip()
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass

    return date_str


YANGMING_URL = "https://www.yangming.com/en/esolution/cargo_tracking"


def track_yml(p, booking_number):
    browser = p.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"]
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    try:
        # 1. Open Landing Page
        page.goto(YANGMING_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # 2. Fill Search Input
        search_input = page.locator("input[placeholder*='Search'], input[type='text']").first
        search_input.wait_for(state="visible", timeout=8000)
        search_input.click()
        search_input.fill("")
        search_input.fill(booking_number)

        search_btn = page.locator("button:has-text('Search'), input[type='submit']").first
        if search_btn.is_visible():
            search_btn.click()
        else:
            search_input.press("Enter")

        page.wait_for_timeout(4000)

        # ------------------------------------------------------
        # 3. Extract POL (Loading Column)
        # ------------------------------------------------------
        pol_name = "UNKNOWN"
        try:
            loading_cell = page.locator("table[aria-label='Basic Information'] td[aria-colindex='2']").first
            if loading_cell.count() > 0:
                raw_pol = loading_cell.inner_text().strip()
                if raw_pol:
                    pol_name = re.sub(r"\s*\([A-Z0-9]+\)", "", raw_pol).strip()

            if pol_name == "UNKNOWN":
                body_text = page.locator("body").inner_text()
                pol_m = re.search(r"([A-Z\s]+,\s*[A-Z]{2}\s*\([A-Z0-9]+\))", body_text)
                if pol_m:
                    pol_name = re.sub(r"\s*\([A-Z0-9]+\)", "", pol_m.group(1)).strip()
        except Exception as e:
            print(f"    Notice: POL extraction error ({e})")

        # ------------------------------------------------------
        # 4. Extract Vessel Name & Voyage Code
        # ------------------------------------------------------
        vessel_name = "YANG MING VESSEL"
        voyage_code = "UNKNOWN"

        try:
            vessel_anchor = page.locator("a[href*='vessel_schedule']").first
            if vessel_anchor.count() > 0 and vessel_anchor.is_visible():
                vessel_name = vessel_anchor.inner_text().strip()

                parent_text = vessel_anchor.locator("xpath=ancestor::div[1]").inner_text()
                voy_match = re.search(r"-\s*(\d{3,4}[A-Z])", parent_text)
                if not voy_match:
                    voy_match = re.search(r"\b(\d{3,4}[A-Z])\b", parent_text)

                if voy_match:
                    voyage_code = voy_match.group(1).strip()
            else:
                body_text = page.locator("body").inner_text()
                vv_match = re.search(r"Vessel\s*Voy\s*No\.\s*:\s*([A-Za-z\s]+?)-(\d{3,4}[A-Z])", body_text, re.I)
                if vv_match:
                    vessel_name = vv_match.group(1).strip()
                    voyage_code = vv_match.group(2).strip()
        except Exception:
            pass

        # ------------------------------------------------------
        # 5. Extract DOC/ITN Cut-off Date
        # ------------------------------------------------------
        doc_cutoff = "NOT FOUND"
        target_page = page

        try:
            detail_link = page.locator("a:has-text('View Detail'), button:has-text('View Detail')").first
            if detail_link.count() > 0 and detail_link.is_visible():
                try:
                    with page.expect_popup(timeout=5000) as popup_info:
                        detail_link.click()
                    detail_page = popup_info.value
                    detail_page.wait_for_load_state("domcontentloaded")
                    detail_page.wait_for_timeout(2000)
                    target_page = detail_page
                except TimeoutError:
                    page.wait_for_timeout(2000)
        except Exception:
            pass

        # Target DOC/ITN row specifically using exact text match
        try:
            doc_row_cell = target_page.locator("tr").filter(has_text="DOC/ITN Cut-off Date").locator("td").first
            if doc_row_cell.count() > 0 and doc_row_cell.is_visible():
                doc_cutoff = doc_row_cell.inner_text().strip()
            else:
                # Regex fallback explicitly looking for DOC/ITN label
                body_final = target_page.locator("body").inner_text()
                doc_m = re.search(r"DOC/ITN\s+Cut-off\s+Date\s*[\s\t]*([\d{4}[-/\.]\d{2}[-/\.]\d{2}\s+\d{2}:\d{2})", body_final, re.I)
                if doc_m:
                    doc_cutoff = doc_m.group(1).strip()
        except Exception as e:
            print(f"    Notice: Cutoff extraction error ({e})")

        return {
            "vessel": vessel_name,
            "voyage": voyage_code,
            "pol": pol_name,
            "doc_si_cutoff": format_to_standard_date(doc_cutoff),
        }

    finally:
        context.close()
        browser.close()