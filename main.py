import os
import sys
import time
import gspread
from playwright.sync_api import sync_playwright

# Ensure root folder is in Python path for clean imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.browser_launcher import ensure_chrome_debugging

from extractors.one_extractor import track_one
from extractors.emc_extractor import track_emc
from extractors.yml_extractor import track_yml
from extractors.cma_extractor import track_cma
from extractors.wanhai_extractor import track_wanhai
from extractors.hapag_extractor import track_hapag
from extractors.maersk_extractor import track_maersk


GOOGLE_SHEET_NAME = "Shipping Control Dashboard"
CREDENTIALS_FILE = "service_account.json"

CARRIER_MAP = {
    "ONE": track_one,
    "EMC": track_emc,
    "EVERGREEN": track_emc,
    "YML": track_yml,
    "YANG MING": track_yml,
    "CMA": track_cma,
    "CMA CGM": track_cma,
    "MAERSK": track_maersk,
    "HAPAG": track_hapag,
    "WAN HAI": track_wanhai,
    "WANHAI": track_wanhai,
}


def process_single_row(p, sheet, row_num, booking, carrier, existing_pol, is_retry=False):
    prefix = "    [RETRY PASS]" if is_retry else "-->"
    print(f"{prefix} Processing Row {row_num}: [{carrier}] {booking}")

    if carrier not in CARRIER_MAP:
        print(f"    UNSUPPORTED CARRIER: '{carrier}'. Skipping...")
        error_row = ["UNSUPPORTED CARRIER", "N/A", existing_pol, "NOT FOUND"]
        sheet.update(range_name=f"C{row_num}:F{row_num}", values=[error_row])
        return "NOT FOUND"

    tracker_func = CARRIER_MAP[carrier]

    try:
        # Pass target_pol for carriers that require or support it (ONE, CMA)
        if carrier in ["ONE", "CMA", "CMA CGM"]:
            res = tracker_func(p, booking_number=booking, target_pol=existing_pol)
        else:
            res = tracker_func(p, booking_number=booking)

        # Fall back to existing POL if extraction returns UNKNOWN
        final_pol = res["pol"] if res["pol"] and res["pol"] != "UNKNOWN" else existing_pol

        out_values = [
            res["vessel"],
            res["voyage"],
            final_pol,
            res["doc_si_cutoff"],
        ]

        # Update Google Sheet across Columns C:F
        sheet.update(range_name=f"C{row_num}:F{row_num}", values=[out_values])

        if res["doc_si_cutoff"] != "NOT FOUND":
            print(f"    SUCCESS: Row {row_num} updated with Cut-Off: {res['doc_si_cutoff']}")
        else:
            print(f"    [!] WARNING: Row {row_num} returned 'NOT FOUND' for Cut-Off.")

        return res["doc_si_cutoff"]

    except Exception as e:
        print(f"    ERROR processing row {row_num}: {e}")
        err_row = ["FAILED TO EXTRACT", "ERROR", existing_pol, "NOT FOUND"]
        sheet.update(range_name=f"C{row_num}:F{row_num}", values=[err_row])
        return "NOT FOUND"


def run_manual_automation():
    print("\n====================================")
    print("MANUAL SHIPPING DOC CUT TRACKER RUNNER")
    print("====================================\n")

    # Start Chrome Debugging Browser Session if active
    ensure_chrome_debugging()

    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    sheet = gc.open(GOOGLE_SHEET_NAME).sheet1

    col_a = sheet.col_values(1)  # Booking No.
    col_b = sheet.col_values(2)  # Shipping Line
    col_e = sheet.col_values(5)  # Existing POL
    col_f = sheet.col_values(6)  # Doc/SI Cut-Off

    # Ensure Headers on C1:F1
    headers = ["Vessel", "Voyage", "POL", "Doc/SI Cut-Off"]
    sheet.update(range_name="C1:F1", values=[headers])

    rows_to_process = []
    max_len = max(len(col_a), len(col_b))

    for idx in range(1, max_len):
        row_num = idx + 1
        booking = col_a[idx].strip() if idx < len(col_a) else ""
        carrier = col_b[idx].strip().upper() if idx < len(col_b) else ""
        existing_pol = col_e[idx].strip() if idx < len(col_e) else "UNKNOWN"
        existing_cutoff = col_f[idx].strip() if idx < len(col_f) else ""

        # Only process if booking & carrier exist AND cut-off is missing or NOT FOUND
        if booking and carrier:
            if not existing_cutoff or existing_cutoff in ["NOT FOUND", "FAILED TO EXTRACT"]:
                rows_to_process.append((row_num, booking, carrier, existing_pol))
            else:
                print(f"Skipping Row {row_num} [{booking}]: Already has valid Cut-Off ({existing_cutoff})")

    if not rows_to_process:
        print("\nAll bookings already have valid Doc Cut-off dates. Nothing to process!")
        return

    print(f"\nFound {len(rows_to_process)} booking(s) needing tracking.\n")

    retry_list = []

    with sync_playwright() as p:
        # ------------------------------------------------------
        # PASS 1: Main Extraction Run
        # ------------------------------------------------------
        print("--- STARTING PASS 1 ---")
        for row_num, booking, carrier, existing_pol in rows_to_process:
            cutoff_result = process_single_row(p, sheet, row_num, booking, carrier, existing_pol)
            
            # Queue for Retry Pass if still NOT FOUND
            if cutoff_result in ["NOT FOUND", "FAILED TO EXTRACT"]:
                retry_list.append((row_num, booking, carrier, existing_pol))

        # ------------------------------------------------------
        # PASS 2: Recheck & Retry 'NOT FOUND' Rows
        # ------------------------------------------------------
        if retry_list:
            print(f"\n\n--- STARTING RETRY PASS FOR {len(retry_list)} UNRESOLVED ROW(S) ---")
            time.sleep(3)  # Brief pause between passes

            still_failed = 0
            for row_num, booking, carrier, existing_pol in retry_list:
                retry_result = process_single_row(
                    p, sheet, row_num, booking, carrier, existing_pol, is_retry=True
                )
                if retry_result in ["NOT FOUND", "FAILED TO EXTRACT"]:
                    still_failed += 1

            print(f"\nRetry Pass Complete. ({len(retry_list) - still_failed}/{len(retry_list)}) resolved on second try.")

    print("\n====================================")
    print("TRACKING RUN COMPLETED")
    print("====================================\n")


if __name__ == "__main__":
    run_manual_automation()