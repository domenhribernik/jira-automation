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

# Jira Credentials
JIRA_URL = "https://cwcyprus-sales.atlassian.net"
JIRA_EMAIL = "webadmin@cwcyprus.com"
with open("JiraToken.txt", "r") as file:
    JIRA_API_TOKEN = file.read().strip()

# Jira Project and API Endpoint
JIRA_PROJECT_KEY = "SALES"
TRANSITIONS = {
    "Lapsed": 2,
    "New Web Orders": 3,
    "In Progress": 4,
    "Outcome": 5,
    "New lead": 6
}

auth = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()

# Google Sheets API Setup
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
        "fields": "id,key"  # Request only the 'id' and 'key' fields
    }
    
    response = requests.get(f"{JIRA_URL}/rest/api/2/search", params=params, headers=HEADERS)

    if response.ok:
        issues = response.json().get("issues", [])

        issue_ids = [issue["id"] for issue in issues]  # List of issue IDs
        issue_keys = [issue["key"] for issue in issues]  # List of issue Keys
        
        print(f"Found {len(issue_ids)} issues")
        return issue_ids, issue_keys
    else:
        print(f"❌ Failed to search issues: {response.text} status: {response.status_code}")
        return []


def get_bulk_issues(issues): #! Max 100 issues
    payload = {
        "fields": [ #? Fields to include in the response
            "summary",
            "customfield_10082"
        ],
        "issueIdsOrKeys": issues
    }

    response = requests.post(f"{JIRA_URL}/rest/api/3/issue/bulkfetch", headers=HEADERS, json=payload)
    if response.ok:
        return response.json()['issues']
    else:
        print(f"❌ Failed to get bulk issues: {response.text} status: {response.status_code}")
        return []

def get_bulk_changelog(status):
    pass 

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

def get_last_in_progress_transition(issue_key, changelog):
    for change in reversed(changelog):
        created = change['created']
        for item in change.get('items', []):
            if item.get('field') == 'status' and item.get('toString') == 'In Progress':
                return created

    return None

def schedule_in_progress_emails(): # TODO implement bulk import for changelog
    issues, keys  = search_issues("In Progress")
    message = ""
    email_receiver = ""
    issue_count = len(issues)
    scheduled_emails = []
    issues_data = {issue['key']: issue['fields']['customfield_10082'] for issue in get_bulk_issues(issues)}

    for key in keys:
        response = requests.get(f"{JIRA_URL}/rest/api/3/issue/{key}/changelog", headers=HEADERS)

        if response.ok:           
            date = issues_data.get(key)
            if date is not None:
                issue_count -= 1
                continue
            
            date = get_last_in_progress_transition(key, response.json().get('values', [])) #! Check if this works after bulk import
            last_change_date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%f%z")
            last_change = (datetime.now(last_change_date.tzinfo) - last_change_date)
            seconds_since_last_change = last_change.total_seconds()
            send_email_time_seconds = 3 * 24 * 60 * 60 - math.floor(seconds_since_last_change)
            today_timestamp = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

            email_receiver = response.json()['values'][-1]['author']['emailAddress']
            message = f"This is a reminder to follow up on the issue {keys}. Message was scheduled on {datetime.fromtimestamp(math.floor(send_email_time_seconds + today_timestamp))} \n\nJira Automatic Email"

            print(key)
            print(email_receiver)
            print(message)
 
            payload = {
                "fields": {
                    "customfield_10082": datetime.fromtimestamp(send_email_time_seconds + today_timestamp).strftime("%Y-%m-%d")
                }
            }

            # label_response = requests.put(f"{JIRA_URL}/rest/api/3/issue/{keys[i]}", headers=HEADERS, data=json.dumps(payload))

            # if label_response.status_code == 204:
            #     print(f"✅ Labels updated successfully for {keys[i]}")
            #     scheduled_emails.append((keys[i], message, email_receiver, send_email_time_seconds))
            # else:
            #     print(f"❌ Failed to update labels: {label_response.status_code}, {label_response.text}")
            
        else:
            print(f"❌ Failed to search issues: {response.text} status: {response.status_code}")
    print(f"Returned {issue_count} emails to be scheduled.")
    return scheduled_emails

def schedule_emails():
    emails_to_send = schedule_in_progress_emails()
    for issue_key, message, email_receiver, delay_seconds in emails_to_send:
        run_date = datetime.now() + timedelta(seconds=delay_seconds)
        print(run_date)
        scheduler.add_job(
            send_email,
            'date',
            run_date=datetime.now() + timedelta(seconds=5),
            args=[issue_key, message, email_receiver]
        )
        print(f"Email scheduled for issue {issue_key} for {email_receiver} in {delay_seconds} seconds.")

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
    schedule_in_progress_emails()

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
        seconds=15
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
