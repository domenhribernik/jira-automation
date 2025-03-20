import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import date, datetime

# Google Sheets API Setup
GOOGLE_SHEETS_CREDENTIALS_FILE = "credentials.json"
GOOGLE_SHEET_NAME = "Jira Sales API"
GOOGLE_SHEET_TAB_NAME = "Sheet1" 

def authenticate_google_sheets():
    # Define the scope
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Authenticate using the credentials file
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    return client

def read_google_sheet(client):
    sheet = client.open(GOOGLE_SHEET_NAME).worksheet(GOOGLE_SHEET_TAB_NAME)
    data = sheet.get_all_values()
    pd.set_option('display.max_columns', None)  # Show all columns
    pd.set_option('display.expand_frame_repr', False)  # Prevent line wrapping
    pd.set_option('display.max_rows', None)  # Show all rows
    df = pd.DataFrame(data[1:], columns=data[0])  # First row as headers
    return df

def formate_date(date):
    parsed_date = datetime.strptime(date, "%m/%d/%Y")
    return parsed_date.strftime("%Y-%m-%d")

def main():
    client = authenticate_google_sheets()
    df = read_google_sheet(client)
    for index, row in df.iterrows():
        last_date = formate_date(row['Last Transaction Date'])
        days_diff = (date.today() - datetime.strptime(last_date, "%Y-%m-%d").date()).days
        if days_diff < 90:
            continue
        print(f"\nRow {index + 1}:")
        print(f"Customer Name: {row['Customer Name']}")
        print(f"Last Transaction Amount: {row['Last Transaction Amount']}")
        print(f"Email: {row['Email']}")
        print(f"SMS: {row['SMS']}")
        print(f"Today: {date.today()}")
        print(f"Last Transaction Date: {last_date}")
        print(f"Days since last transaction: {days_diff}")
        print("=" * 50)  # Separator for readability

if __name__ == "__main__":
    main()