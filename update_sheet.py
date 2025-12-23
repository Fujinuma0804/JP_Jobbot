import gspread
import os

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Google Sheets URL from .env
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")

def update_google_sheet(data):
    """
    Updates the Google Sheet with the given data.
    :param data: List of dictionaries containing job data.
    """
    try:
        # Check if credentials file exists
        credentials_file = "service_account.json"
        if not os.path.exists(credentials_file):
            print(f"❌ Credentials file '{credentials_file}' not found!")
            return

        # Check if Google Sheet URL is configured
        if not GOOGLE_SHEET_URL:
            print("❌ GOOGLE_SHEET_URL not found in environment variables!")
            return

        # Use modern gspread service_account method (simpler and recommended)
        client = gspread.service_account(filename=credentials_file)

        # Open the Google Sheet
        sheet = client.open_by_url(GOOGLE_SHEET_URL).sheet1

        # Prepare the data to append
        rows = []
        for job in data:
            rows.append([
                job.get("time", ""),
                job.get("dtype", ""),
                job.get("url", ""),
                job.get("price", ""),
                job.get("title", ""),
            ])
        print(f"Rows to append: {rows}")  # Debugging log

        # Append rows to the sheet
        if rows:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            print("✅ Data successfully sent to Google Sheets.")
        else:
            print("⚠️ No rows to append to Google Sheets.")

    except Exception as e:
        print(f"❌ Failed to update Google Sheets: {e}")