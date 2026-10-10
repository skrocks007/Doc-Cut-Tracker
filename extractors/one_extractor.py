import re
from datetime import datetime
from playwright.sync_api import TimeoutError


def format_to_standard_date(date_str):
    if not date_str or date_str in ["NOT FOUND", "FAILED TO EXTRACT"]:
        return "NOT FOUND"

    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%Y/%m/%d %H:%M",
    ]

    cleaned = date_str.strip()
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass

    return date_str


ONE_URL = "https://www.one-line.com/one-ecom/manage-shipment/cargo-tracking"


def extract_cutoff_from_popup(page2, target_pol):
    clean_pol = target_pol.split(",")[0].strip().upper()

    # Wait for schedule ports to load
    page2.wait_for_selector("div[class*='VesselResultItem_root'], a[data-cy='new-schedule-port-name']", timeout=12000)

    # Dispatch mouse events directly via JS DOM targeting based on DevTools screenshot
    success = page2.evaluate("""(polName) => {
        // 1. Get all root port containers
        const roots = Array.from(document.querySelectorAll("div[class*='VesselResultItem_root']"));
        
        let targetRoot = null;
        for (const root of roots) {
            const portLink = root.querySelector('a[data-cy="new-schedule-port-name"], a');
            if (portLink && portLink.innerText.toUpperCase().includes(polName)) {
                targetRoot = root;
                break;
            }
        }

        if (!targetRoot) return false;

        // 2. Find cut-off button strictly inside THIS port's root container
        const cutoffBtn = targetRoot.querySelector('[data-cy="cut-off-button"]') || 
                          Array.from(targetRoot.querySelectorAll('div, span, button')).find(el => el.innerText.trim() === 'Cut Off');

        if (!cutoffBtn) return false;

        // 3. Scroll into center view
        cutoffBtn.scrollIntoView({ block: 'center', inline: 'center' });

        // 4. Trigger hover popover by dispatching mouse events directly on the element
        const opts = { bubbles: true, cancelable: true, view: window };
        cutoffBtn.dispatchEvent(new MouseEvent('mousemove', opts));
        cutoffBtn.dispatchEvent(new MouseEvent('mouseover', opts));
        cutoffBtn.dispatchEvent(new MouseEvent('mouseenter', opts));

        return true;
    }""", clean_pol)

    if not success:
        raise RuntimeError(f"Could not trigger hover for port '{clean_pol}' on Page 2")

    # Wait for black tooltip overlay to render into DOM
    page2.wait_for_timeout(2000)

    # Read active tooltip text
    body_text = page2.locator("body").inner_text()
    doc_match = re.search(r"Doc\s*Cut\s*off\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", body_text, re.IGNORECASE)

    return doc_match.group(1) if doc_match else "NOT FOUND"


def track_one(p, booking_number, target_pol=None):
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    try:
        page.goto(ONE_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # 1. Skip Popover
        try:
            skip_btn = page.get_by_role("button", name="Skip").first
            skip_btn.wait_for(state="visible", timeout=4000)
            skip_btn.click(force=True)
            page.wait_for_timeout(1000)
        except Exception:
            page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const skip = btns.find(b => b.innerText.trim() === 'Skip');
                if (skip) skip.click();
            }""")
            page.wait_for_timeout(1000)

        # 2. Fill Search Input
        try:
            search_input = page.get_by_test_id("tnt-search-multiple-input")
            search_input.wait_for(state="visible", timeout=5000)
            search_input.click()
            search_input.fill("")
            search_input.fill(booking_number)

            search_btn = page.get_by_test_id("tnt-search-multiple-button")
            search_btn.click()
            page.wait_for_timeout(4000)
        except Exception as e:
            print(f"    Notice: Search error ({e})")

        # 3. Extract POL, Vessel, Voyage from Page 1
        vessel_name = "ONE VESSEL"
        voyage_code = "UNKNOWN"
        extracted_pol = "UNKNOWN"

        try:
            pol_text = page.evaluate("""() => {
                const polDiv = document.querySelector("div[class*='SailingTable_port-of-loading-td'] div, div[class*='port-of-loading'] div");
                return polDiv ? polDiv.innerText : '';
            }""")
            if pol_text:
                extracted_pol = pol_text.split(",")[0].strip()
        except Exception:
            pass

        final_pol = target_pol.strip() if target_pol and target_pol != "UNKNOWN" else extracted_pol

        vessel_anchor = page.locator("a[target='_blank']").first
        if vessel_anchor.count() > 0 and vessel_anchor.is_visible():
            raw_vessel = vessel_anchor.inner_text().strip()
            vv_match = re.search(r"^([A-Za-z\s]+?)\s+([0-9]{3,4}[A-Z])", raw_vessel)
            if vv_match:
                vessel_name = vv_match.group(1).strip()
                voyage_code = vv_match.group(2).strip()
            else:
                vessel_name = raw_vessel.split("(")[0].strip()

        # 4. Open Page 2 Schedule Popup
        doc_si_cutoff = "NOT FOUND"

        try:
            with page.expect_popup(timeout=8000) as popup_info:
                vessel_anchor.click()
            page2 = popup_info.value
            page2.wait_for_load_state("domcontentloaded")

            # Wait for "Fetching result" loader screen to clear
            try:
                fetching = page2.get_by_text("Fetching result", exact=False)
                if fetching.is_visible(timeout=3000):
                    fetching.wait_for(state="hidden", timeout=15000)
            except TimeoutError:
                pass

            page2.wait_for_timeout(3000)

            # Extract Cut-off matching Page 1 POL
            doc_si_cutoff = extract_cutoff_from_popup(page2, final_pol)

        except Exception as e:
            print(f"    Notice: Cut-off extraction failed ({e})")

        return {
            "vessel": vessel_name,
            "voyage": voyage_code,
            "pol": final_pol,
            "doc_si_cutoff": format_to_standard_date(doc_si_cutoff),
        }

    finally:
        context.close()
        browser.close()