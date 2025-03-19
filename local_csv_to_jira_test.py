import requests
import pandas as pd
import base64

# Jira Credentials
JIRA_URL = "https://cwcyprus-sales.atlassian.net"
JIRA_EMAIL = "webadmin@cwcyprus.com"
with open("JiraToken.txt", "r") as file:
    JIRA_API_TOKEN = file.read().strip()

# Jira Project and API Endpoint
JIRA_PROJECT_KEY = "SALES"
JIRA_API_ENDPOINT = f"{JIRA_URL}/rest/api/3/issue"

auth = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()

# Read the CSV File
csv_file_path = r"C:\Users\user\Downloads\jira-automation\data.csv"
df = pd.read_csv(csv_file_path, dtype=str, quotechar='"', skipinitialspace=True)

# Function to create an issue in Jira
def create_jira_issue(summary, description, purchase_date, label):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth}"
    }
    
    # Jira issue payload
    issue_data = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": description
                            }
                        ]
                    }
                ]
            },
            "issuetype": {"name": "Task"},
            "customfield_10015": purchase_date,
            "labels": [label] if label else []
        }
    }

    response = requests.post(JIRA_API_ENDPOINT, headers=headers, json=issue_data)
    
    if response.status_code == 201:
        print(f"Issue created: {summary}")
    else:
        print(f"Failed to create issue: {response.text}")

def main():
    for _, row in df.iterrows():
        create_jira_issue(row.iloc[0],  # Summary
                          row.iloc[1],  # Description
                          row.iloc[2],  # Purchase Date
                          row.iloc[3])  # Labels

if __name__ == "__main__":
    main()
