# Document Cut-off Date Tracker

**Automated Shipping Documentation Cut-Off Tracking with Python, Playwright & Google Sheets**

Document Cutoff Date Tracker is a Python-based web automation and data pipeline designed to retrieve document cut-off dates from supported ocean carrier portals and synchronize tracking results with Google Sheets.

Built for logistics and shipping documentation workflows, the project reduces repetitive manual tracking, standardizes extracted dates, and helps teams monitor shipment documentation deadlines from a centralized dashboard.

## Key Features

* **Multi-Carrier Automation:** Carrier-specific extractors for supported shipping line websites.
* **Persistent Browser Sessions:** Connects to an existing Chrome session through the Chrome DevTools Protocol (CDP) when required.
* **Two-Pass Retry Mechanism:** Reprocesses unresolved bookings to improve extraction reliability.
* **Google Sheets Integration:** Reads booking data and writes tracking results using `gspread` and the Google Sheets API.
* **Date Standardization:** Converts supported date formats into a consistent `DD-MMM-YY` format.
* **Modular Architecture:** Separates carrier-specific extraction logic from browser utilities, date formatting, and spreadsheet operations.
* **Centralized Tracking:** Organizes retrieved cut-off information for easier shipment monitoring.

> **Important:** Extraction success depends on carrier website availability, session validity, page structure, and access restrictions. Missing cut-off dates should be treated as unresolved until verified.

## Supported Carriers

| Carrier                     | Code     | Browser / Extraction Strategy                  |
| --------------------------- | -------- | ---------------------------------------------- |
| Yang Ming                   | `YML`    | Standard Playwright browser                    |
| CMA CGM                     | `CMA`    | Persistent Chrome session via CDP              |
| Wan Hai Lines               | `WANHAI` | Persistent Chrome session via CDP              |
| Ocean Network Express (ONE) | `ONE`    | Standard browser session with popover handling |
| Evergreen                   | `EMC`    | Targeted DOM-based extraction                  |

*Carrier workflows reflect the current project configuration and may require updates when website layouts or access requirements change.*

## Project Structure

```text
Doc-Cut-Tracker/
├── extractors/
│   ├── cma_extractor.py
│   ├── emc_extractor.py
│   ├── one_extractor.py
│   ├── wanhai_extractor.py
│   └── yml_extractor.py
├── utils/
│   ├── browser_launcher.py
│   ├── date_formatter.py
│   └── sheets_handler.py
├── .gitignore
├── main.py
├── README.md
└── service_account.json   # Local credentials; never commit
```

* `extractors/` — Contains carrier-specific tracking and data extraction logic.
* `utils/browser_launcher.py` — Handles browser startup and remote browser connections.
* `utils/date_formatter.py` — Normalizes extracted date values.
* `utils/sheets_handler.py` — Manages Google Sheets interactions.
* `main.py` — Coordinates the tracking workflow and retries unresolved records.

The `service_account.json` file must be created locally and must not be committed to the repository.

## Getting Started

### Prerequisites

Before installing the project, ensure you have:

* Python 3.10 or later
* Google Chrome installed on Windows
* Git installed and available in your terminal
* A Google Cloud service account with Google Sheets API access
* Access to the Google Sheet used for tracking shipment cut-off dates

### 1. Clone the Repository

Open Git Bash, PowerShell, or the VS Code terminal and run:

```bash
git clone https://github.com/skrocks007/Doc-Cut-Tracker.git
cd Doc-Cut-Tracker
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate the environment using the command for your terminal.

**Git Bash**

```bash
source venv/Scripts/activate
```

**PowerShell**

```powershell
.\venv\Scripts\Activate.ps1
```

**Windows Command Prompt**

```cmd
venv\Scripts\activate.bat
```

Once activated, the terminal should display `(venv)`.

### 3. Install Dependencies

Upgrade `pip` and install the required packages:

```bash
python -m pip install --upgrade pip
pip install playwright gspread google-auth
```

Install the Chromium browser used by Playwright:

```bash
playwright install chromium
```

If the project includes a `requirements.txt` file, you can install its dependencies instead with:

```bash
pip install -r requirements.txt
```

## Configuration

### 1. Set Up Google Sheets API Access

The application uses a Google Cloud service account to access the tracking spreadsheet.

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project or select an existing project.
3. Enable the **Google Sheets API**.
4. Create a service account under **IAM & Admin → Service Accounts**.
5. Generate a JSON key and save it securely as `service_account.json`.
6. Place the file in the project root directory, unless the application is configured to use another path.
7. Open your Google Sheet and share it with the service account email address.
8. Grant Editor permission if the application needs to update spreadsheet values.

Verify that the spreadsheet ID, worksheet name, and column mappings match the configuration expected by the application.

**Credential security**

* Never commit `service_account.json` to GitHub.
* Confirm that `.gitignore` excludes the credentials file.
* Never publish service account private keys, passwords, browser cookies, or session tokens.
* If a key is accidentally exposed, revoke it and generate a replacement.

Google Sheets API usage is subject to Google Cloud quotas and applicable account limits.

### 2. Launch Chrome in Remote Debugging Mode

CMA CGM and Wan Hai workflows may require an existing browser session. Start Chrome with remote debugging enabled before running the tracker.

**Windows PowerShell**

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="C:\chrome_dev_profile"
```

**Windows Command Prompt**

```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome_dev_profile"
```

If Chrome is installed in a different location, update the executable path.

**Browser session notes:**

* Keep Chrome running while the tracker is executing.
* Complete any required login manually.
* Use a dedicated browser profile rather than your regular Chrome profile.
* Ensure the browser launcher is configured to connect to the correct debugging endpoint.
* Keep port `9222` restricted to trusted local access. A remote debugging endpoint can expose sensitive browser data and authenticated sessions.

This step is needed only for carrier extractors configured to use CDP.

## Running the Tracker

After completing the installation and configuration, activate the virtual environment and execute:

```bash
python main.py
```

The application will start the configured tracking workflow, process the available booking records, retry unresolved results where supported, and synchronize data with Google Sheets according to the implementation.

Before running the tracker, verify that:

* Booking numbers are populated correctly.
* The Google Sheet is accessible to the service account.
* Required browser sessions are running.
* Carrier websites are accessible.
* The configured worksheet and columns are correct.

## Troubleshooting

| Problem                        | Recommended Action                                                                                    |
| ------------------------------ | ----------------------------------------------------------------------------------------------------- |
| `ModuleNotFoundError`          | Activate the virtual environment and install the dependencies.                                        |
| Playwright browser not found   | Run `playwright install chromium`.                                                                    |
| Google Sheets permission error | Share the spreadsheet with the service account email and verify its permissions.                      |
| Credentials file not found     | Check the filename and the path expected by the application.                                          |
| Chrome connection refused      | Start Chrome with remote debugging enabled and confirm port `9222` is available.                      |
| Booking details not found      | Verify the booking number and check the carrier website manually.                                     |
| Cut-off date not extracted     | Review the shipment details, carrier page structure, and extraction logs.                             |
| CAPTCHA or access restriction  | Follow the carrier's authorized verification process; do not attempt to circumvent security controls. |
| Incorrect date format          | Verify the extracted source value and date normalization logic.                                       |
| Google Sheets updates fail     | Check API access, spreadsheet sharing, quotas, and network connectivity.                              |

## Reliability & Data Validation

Shipping cut-off dates are time-sensitive. The tracker should distinguish between successfully extracted dates and unresolved results.

Recommended practices include:

* Preserve a clear status for missing or failed extractions.
* Avoid converting missing dates into valid-looking dates.
* Log the booking number and carrier when extraction fails.
* Verify critical cut-off deadlines against the carrier's official information.
* Review extraction logic when a carrier changes its website.
* Avoid excessive requests and respect carrier website terms and access requirements.

## License

This project is licensed under the MIT License.

Copyright (c) 2025 Shubham Kumar

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Author

**Shubham Kumar**

GitHub: [@skrocks007](https://github.com/skrocks007)

---

*Automating shipment documentation tracking, one booking at a time.*
