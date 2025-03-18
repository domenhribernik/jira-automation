import requests
from datetime import date, datetime, timedelta
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import base64
import math
from apscheduler.schedulers.background import BackgroundScheduler
import json
import sys
import os

JIRA_URL = "https://cwcyprus-sales.atlassian.net"
JIRA_EMAIL = "webadmin@cwcyprus.com"
with open("JiraToken.txt", "r") as file:
    JIRA_API_TOKEN = file.read().strip()

JIRA_PROJECT_KEY = "SALES"
TRANSITIONS = {
    "Lapsed": 2,
    "New Web Orders": 3,
    "In Progress": 4,
    "Outcome": 5,
    "New lead": 6
}

with open('users.json', 'r') as file:
    USERS = json.load(file)

auth = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()

GOOGLE_SHEETS_CREDENTIALS_FILE = "credentials.json"
GOOGLE_SHEET_NAME = "Jira Sales API"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = "domen.hribernik4@gmail.com"
with open("GmailToken.txt", "r") as file:
    EMAIL_PASSWORD = file.read().strip()


HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Basic {auth}"
}

scheduler = BackgroundScheduler()
scheduler.start()

def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    return client

def read_google_sheet(client, sheet):
    sheet = client.open(GOOGLE_SHEET_NAME).worksheet(sheet)
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

def search_issues(status): #TODO Implement pagination for large datasets
    params = {
        "jql": f"project = 'SALES' AND status = '{status}'",
        "fields": "id,key"  #? Returned from specific issue search
    }
    
    response = requests.get(f"{JIRA_URL}/rest/api/2/search", params=params, headers=HEADERS)

    if response.ok:
        issues = response.json().get("issues", [])

        issue_ids = [issue["id"] for issue in issues]
        issue_keys = [issue["key"] for issue in issues]
        
        print(f"Found {len(issue_ids)} issues")
        return issue_ids, issue_keys
    else:
        print(f"❌ Failed to search issues: {response.text} status: {response.status_code}")
        return []


def get_bulk_issues(issues): #! Max 100 issues
    payload = {
        "fields": [ #? Fields to include in the response
            "summary",
            "customfield_10082",
            "assignee",
        ],
        "issueIdsOrKeys": issues
    }
    issues_data = {}

    response = requests.post(f"{JIRA_URL}/rest/api/3/issue/bulkfetch", headers=HEADERS, json=payload)
    if response.ok:
        for issue in response.json().get('issues', []):
            issue_key = issue['key']
            customfield_10082 = issue['fields'].get('customfield_10082')
            assignee_account_id = issue['fields'].get('assignee', {}).get('accountId') if issue['fields'].get('assignee') else None
            
            issues_data[issue_key] = (customfield_10082, assignee_account_id)
    else:
        print(f"❌ Failed to get bulk issues: {response.text} status: {response.status_code}")
    return issues_data

def get_bulk_changelog(issues):
    payload = {
        "issueIdsOrKeys": issues,
        "fieldIds": [
            "status"
        ],
        "maxResults": 1000
    }
    filtered_data = []

    response = requests.post(f"{JIRA_URL}/rest/api/3/changelog/bulkfetch", headers=HEADERS, json=payload)
    if response.ok:
        for issue in response.json()['issueChangeLogs']:
            issue_id = issue["issueId"]
            transitions = []

            for history in issue.get("changeHistories", []):
                for item in history.get("items", []):
                    if item["field"] == "status":
                        transitions.append({
                            "author": history["author"]["displayName"],
                            "date": history["created"],
                            "from": item["fromString"],
                            "to": item["toString"],
                            "field": item["field"]
                        })
            if transitions:
                filtered_data.append({
                    "issueId": issue_id,
                    "transitions": transitions
                })
    else:
        print(f"❌ Failed to get bulk changelogs: {response.text} status: {response.status_code}")

    for issue in filtered_data:
        issue["transitions"].sort(key=lambda x: x["date"], reverse=True)
    return filtered_data

# Function to create an issue in Jira
def create_jira_issues(df, existing_elements, check_date=True):
    bulk_issue_data = {
        "issueUpdates": []
    }

    for _, row in df.iterrows():
        if row['Customer Name'] in existing_elements:
            continue
        last_date = datetime.strptime(row['Last Transaction Date'], "%m/%d/%Y").strftime("%Y-%m-%d")
        days_diff = (date.today() - datetime.strptime(last_date, "%Y-%m-%d").date()).days
        if days_diff < 90 and check_date:
            continue
        print(f"Days since last transaction: {days_diff}")

        company_name = row['Customer Name']
        customer_name = row['Customer Name']
        transaction_amount = row['Last Transaction Amount']
        email = row['Email']
        sms = row['SMS']
    
        issue_payload = {
            "fields": {
                "issuetype": {"id": 10001}, # Lead hardcoded
                "project": {"key": JIRA_PROJECT_KEY},
                "summary": str(customer_name),
                "customfield_10050": str(last_date), 
                "customfield_10052": str(transaction_amount),
                "customfield_10041": str(company_name),
                "customfield_10043": str(customer_name),
                "customfield_10042": str(sms),
                "customfield_10039": str(email)
            }
        }

        bulk_issue_data["issueUpdates"].append(issue_payload)
    # print(json.dumps(bulk_issue_data, indent=4))

    if bulk_issue_data["issueUpdates"] == []:
        print("No issues to create.")
        return []

    response = requests.post(f"{JIRA_URL}/rest/api/3/issue/bulk", headers=HEADERS, json=bulk_issue_data)
    
    if response.ok:
        print(f"✅ Issues created: {len(bulk_issue_data["issueUpdates"])}")
    else:
        print(f"❌ Failed to create issue: {response.text}")

    keys = [issue['key'] for issue in response.json()['issues']]
    print(keys)
    return keys

def get_transitions(key):
    response = requests.get(f"{JIRA_URL}/rest/api/3/issue/{key}/transitions", headers=HEADERS)

    if response.ok:
        print(f"Transitions for issue {key}:")
        print(response.json())
    else:
        print(f"Failed to get transitions: {response.text}")

def transition_jira_issues(transition, keys):
    transition_payload = {
        "bulkTransitionInputs": [
            { 
                "selectedIssueIdsOrKeys": keys, 
                "transitionId": transition
            }
        ],
        "sendBulkNotification": False
    }

    for key in keys:
        response = requests.post(f"{JIRA_URL}/rest/api/3/bulk/issues/transition", json=transition_payload, headers=HEADERS) #! Implement bulk transition

        if response.ok:
            print(f"✅ Issue {key} moved to 'Lapsed'")
        else:
            print(f"❌ Failed to transition issue: {response.text} status: {response.status_code}")

def clear_google_sheet(client, sheet):
    sheet = client.open(GOOGLE_SHEET_NAME).worksheet(sheet)
    all_data = sheet.get_all_values()
    if len(all_data) > 1:
        num_columns = len(all_data[0]) 
        sheet.batch_clear([f"A2:{chr(64+num_columns)}"])
        print(f"Sheet '{sheet}' cleared except for header.")

def check_for_new_orders(sheet):
    print("Checking for new orders...")
    client = authenticate_google_sheets()
    df = read_google_sheet(client, sheet)

    if df is not None and not df.empty:
        keys = create_jira_issues(df, [], check_date=False)
        transition_jira_issues(TRANSITIONS.get("New Web Orders", 0), keys)
        clear_google_sheet(client, sheet)
    else:
        print("No new orders found.")

def send_email(key, message, email_receiver):

    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = email_receiver
    msg["Subject"] = f"Jira Issue {key}"
    msg.attach(MIMEText(message, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure the connection
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, email_receiver, msg.as_string())
            print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def get_last_in_progress_transition(issue_key, transitions):
    transition = transitions[0]
    created = transition['date']
    if transition['field'] == 'status' and transition['to'] == 'In Progress':
        return created

    return None

def schedule_in_progress_emails(status):
    issues, keys  = search_issues(status)
    message = ""
    email_receiver = ""
    issue_count = len(issues)
    scheduled_emails = []
    changelogs = get_bulk_changelog(issues)
    issues_data = get_bulk_issues(issues)

    for issue, key in zip(issues, keys):
        transition = next((log for log in changelogs if log['issueId'] == issue), None)['transitions']
        
        date = issues_data.get(key, (None, None))[0]
        if date is not None:
            issue_count -= 1
            continue
         
        time_of_last_change = get_last_in_progress_transition(key, transition)
        today_timestamp = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

        assignee_id = issues_data.get(key, (None, None))[1]
        email_receiver = USERS.get(assignee_id) if assignee_id else None
        message = f"This is a reminder to follow up on the issue {key}. Message was scheduled on {datetime.fromtimestamp(math.floor( today_timestamp))} + 3 days \n\nJira Automatic Email"

        print(f"Scheduled email for issue {key} to {email_receiver} in {message}")

        payload = {
            "fields": {
                "customfield_10082": datetime.fromtimestamp(today_timestamp).strftime("%Y-%m-%d")
            }
        }

        label_response = requests.put(f"{JIRA_URL}/rest/api/3/issue/{key}", headers=HEADERS, data=json.dumps(payload))

        if label_response.ok:
            print(f"✅ Labels updated successfully for {key}")
            scheduled_emails.append((key, message, email_receiver))
        else:
            print(f"❌ Failed to update labels: {label_response.status_code}, {label_response.text}")

    print(f"Returned {issue_count} emails to be scheduled.")
    return scheduled_emails

def schedule_emails(status):
    emails_to_send = schedule_in_progress_emails(status)
    delay_seconds = 30
    for issue_key, message, email_receiver in emails_to_send:
        run_date = datetime.now() + timedelta(seconds=delay_seconds) # datetime.now() + timedelta(seconds=delay_seconds)
        print(run_date)
        if email_receiver is None:
            print(f"❌ Email for issue {issue_key} has no receiver (label was still added).")
            continue
        scheduler.add_job(
            send_email,
            'date',
            run_date=run_date,
            args=[issue_key, message, email_receiver]
        )
        print(f"✉️  Email scheduled for issue {issue_key} for {email_receiver} in {delay_seconds} seconds.")

def import_lapsed_clients(sheet):
    issues, keys = search_issues("Lapsed")
    lapsed = list(map(lambda issue: issue['fields']['summary'], get_bulk_issues(issues)))
    
    df = read_google_sheet(authenticate_google_sheets(), sheet)
    keys = create_jira_issues(df, lapsed)
    transition_jira_issues(TRANSITIONS.get("Lapsed", 0), keys)

def print_task_list():
    jobs = scheduler.get_jobs()
    if not jobs:
        print("No scheduled tasks.")
    else:
        print("Scheduled Tasks:")
        for job in jobs:
            print(f"- Job ID: {job.id}, Function: {job.func.__name__}, Run Time: {job.next_run_time}")

#TODO Code refactor and cleanup
#TODO Calculate concurrency for whole project and reduce it 
def main():
    #* bulk import lapsed clients
    scheduler.add_job(
        import_lapsed_clients,
        'interval',
        weeks=1,
        args=["Lapsed"]
    )

    #* check for new orders
    scheduler.add_job(
        check_for_new_orders,
        'interval',
        minutes=15,
        args=["New Web Orders"]
    )

    #* schedule emails
    scheduler.add_job(
        schedule_emails,
        'interval',
        seconds=20,
        args=["In Progress"]
    )
    while True: # TODO Make a html ui for this
        user_input = input("Enter a command (Tasks, Delete, Exit): \n").strip().lower()
        if user_input == "tasks" or user_input == "t":
            print_task_list()
        elif user_input == "delete" or user_input == "d":
            job_id = input("Enter the Job ID to delete: \n").strip()
            scheduler.remove_job(job_id)
            print(f"Job {job_id} deleted.")
        elif user_input == "exit" or user_input == "e":
            print("Exiting program...")
            scheduler.shutdown()
            break
        else:
            print("Unknown command. Try 'tasks', 'delete' or 'exit'.") 
    

if __name__ == "__main__":
    main()
