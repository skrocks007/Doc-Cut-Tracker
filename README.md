# Automated Shipping ETA Tracker

An automated Web Scraping and Data Pipeline tool built with Python and Playwright. It extracts estimated time of arrival (ETA) dates directly from carrier portals and updates a centralized Google Sheet.

## Supported Carriers
- **Yang Ming (YML)**
- **CMA CGM** (via Chrome CDP Session)
- **Wan Hai Lines** (via Chrome CDP Session)
- **ONE (Ocean Network Express)**
- **Evergreen (EMC)**

## Features
- Dynamic DOM extraction targeting destination Port of Discharging ETAs.
- Automated onboarding popover handling and cookie banner dismissal.
- Two-pass execution: Initial full sweep followed by a single retry pass for unresolved rows.
- Standardized date formatting utility (`DD-MMM-YY`).
- Direct Google Sheets API sync via `gspread`.

## Setup Instructions

1. Clone the repository:
   ```bash
   git clone [https://github.com/skrocks007/shipment_tracker.git](https://github.com/skrocks007/shipment_tracker.git)
   cd shipment_tracker

2. Set Up Virtual Environment & Dependencies
    Create Virtual Environment:
    Bash
    python -m venv venv

    Activate Virtual Environment:
    Git Bash (VS Code Default):

    Bash
    source venv/Scripts/activate

    PowerShell:

    .\venv\Scripts\activate

    Install Required Packages:
    Bash
    pip install playwright gspread google-auth

    Install Playwright Chromium Browser:
    Bash
    playwright install chromium

3. Configure Credentials & Debug Chrome
    1.Google Sheets API: Place your service_account.json file in the root project directory.

    2.Chrome Debug Mode (Required for CMA & Wan Hai):
    Launch Chrome with remote debugging enabled on port 9222:

    Windows:

    DOS
    "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome_dev_profile"
    
4. Run the Pipeline
    Bash
    python main.py