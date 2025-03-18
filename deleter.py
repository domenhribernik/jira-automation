import requests
import base64
import json

JIRA_URL = "https://cwcyprus-sales.atlassian.net"
JIRA_EMAIL = "webadmin@cwcyprus.com"
with open("JiraToken.txt", "r") as file:
    JIRA_API_TOKEN = file.read().strip()

PROJECT_KEY = "SALES"

if input("Are you sure you want to delete all issues in the project? (y/n): ").lower() != "y":
    print("Exiting...")
    exit()

auth = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
headers = {
    "Authorization": f"Basic {auth}",
    "Content-Type": "application/json"
}

search_url = f"{JIRA_URL}/rest/api/3/search?jql=project={PROJECT_KEY}&maxResults=100"
response = requests.get(search_url, headers=headers)
issues = response.json().get("issues", [])


issue_ids = [issue["id"] for issue in issues]

payload = json.dumps( {
  "selectedIssueIdsOrKeys": issue_ids,
  "sendBulkNotification": False
} )

delete_url = f"{JIRA_URL}/rest/api/3/bulk/issues/delete"
    
delete_response = requests.post(delete_url, headers=headers, data=payload)

if delete_response.ok:
    print(f"Issues deleted successfully.")
else:
    print(f"Failed to delete: {delete_response.text}")
    
