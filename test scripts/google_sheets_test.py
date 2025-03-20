import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# Google Sheets API Setup
GOOGLE_SHEETS_CREDENTIALS_FILE = "credentials.json"  # Path to your downloaded JSON file
GOOGLE_SHEET_NAME = "Jira Sales API"  # Name of the Google Sheet
GOOGLE_SHEET_TAB_NAME = "Sheet1"  # Name of the tab in the Google Sheet

# Authenticate with Google Sheets
def authenticate_google_sheets():
    # Define the scope
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Authenticate using the credentials file
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    return client

# Function to read data from Google Sheets
def read_google_sheet(client):
    # Open the Google Sheet
    sheet = client.open(GOOGLE_SHEET_NAME).worksheet(GOOGLE_SHEET_TAB_NAME)
    
    # Get all data as a list of lists
    data = sheet.get_all_values()
    
    # Convert to a pandas DataFrame
    df = pd.DataFrame(data[1:], columns=data[0])  # First row as headers
    return df

# Main function
def main():
    # Authenticate with Google Sheets
    client = authenticate_google_sheets()
    
    # Read data from Google Sheets
    df = read_google_sheet(client)
    
    # Display the DataFrame
    print("Data from Google Sheets:")
    print(df)
    
    # Save to CSV (optional)
    df.to_csv("data_from_google_sheets.csv", index=False)
    print("Data saved to 'data_from_google_sheets.csv'")

if __name__ == "__main__":
    main()