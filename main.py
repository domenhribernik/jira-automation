import os
import json
import base64
from datetime import date, datetime, timedelta
from typing import Tuple, List
import time
import requests
import gspread
import logging
from pathlib import Path
from oauth2client.service_account import ServiceAccountCredentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler

JIRA_URL = "https://cwcyprus-sales.atlassian.net"
JIRA_EMAIL = "webadmin@cwcyprus.com"
JIRA_API_TOKEN = Path("JiraToken.txt").read_text().strip()
JIRA_PROJECT_KEY = "SALES"
DEFAULT_ASSIGNED_USER = "70121:bed40c39-1b16-4eff-a88c-809250e73b31"

TRANSITIONS = {
    "lapsed": 2,
    "new web order": 3,
    "in progress": 4,
    "outcome": 5,
    "new lead": 6
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

def setup_logging(log_file: str = "app.log"):
    """Set up logging configuration."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / log_file

    logging.basicConfig(
        level=logging.INFO,  # Log messages of level INFO and above
        format="%(asctime)s - %(levelname)s - %(message)s",  # Format
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(),
        ],
    )
    print(f"Logging setup complete. Logs will be saved to: {log_path}")

def authenticate_google_sheets():
    """Authenticate and return a Google Sheets client."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds: ServiceAccountCredentials = ServiceAccountCredentials.from_json_keyfile_name(
            GOOGLE_SHEETS_CREDENTIALS_FILE, scope
        )
        client: gspread.Client = gspread.authorize(creds)
        return client
    except Exception as e:
        logging.error(f"❌ Failed to authenticate Google Sheets: {e}")
        raise

def read_google_sheet(client, sheet):
    """Read a Google Sheet and return it as a pandas DataFrame."""
    try:
        worksheet = client.open(GOOGLE_SHEET_NAME).worksheet(sheet)
        data: list[list[str]] = worksheet.get_all_values()
        df: pd.DataFrame = pd.DataFrame(data[1:], columns=data[0])
        return df
    except Exception as e:
        logging.error(f"❌ Failed to read Google Sheet '{sheet}': {e}")
        raise

def clear_google_sheet(client, sheet):
    """Clear all rows in a Google Sheet except the header."""
    try:
        worksheet = client.open(GOOGLE_SHEET_NAME).worksheet(sheet)
        all_data: list[list[str]] = worksheet.get_all_values()
        if len(all_data) > 1:
            num_columns: int = len(all_data[0])
            worksheet.batch_clear([f"A2:{chr(64 + num_columns)}{len(all_data)}"])
            logging.info(f"Sheet '{sheet}' cleared except for header.")
    except Exception as e:
        logging.error(f"❌ Failed to clear Google Sheet '{sheet}': {e}")
        raise

def search_issues(status): #? Max 5000 issues with key and id params, pagination needed for more
    """Search for issues in Jira and return their IDs, keys, and summaries."""
    params = {
        "jql": f"project = 'SALES' AND status = '{status}'",
        "fields": "id,key,summary",  #? Returned from specific issue search
        "maxResults": 1000,
    }
    
    response = requests.get(f"{JIRA_URL}/rest/api/3/search/jql", params=params, headers=HEADERS)

    if response.ok:
        issues = response.json().get("issues", [])

        issue_ids = [issue["id"] for issue in issues]
        issue_keys = [issue["key"] for issue in issues]
        issue_names = [issue["fields"]["summary"] for issue in issues]
        
        logging.info(f"Found {len(issue_ids)} issues")
        return issue_ids, issue_keys, issue_names
    else:
        logging.error(f"❌ Failed to search issues: {response.text} status: {response.status_code}")
        return []

def get_bulk_issues(issues): #TODO if needed find a way to get more than 100 issues (custom paging)
    """Get bulk issues from Jira and return their custom fields and assignees."""
    if issues == []:
        return []

    payload = {
        "fields": [ #? Fields to include in the response
            "customfield_10082",
            "assignee",
        ],
        "issueIdsOrKeys": issues
    }
    issues_data = {}

    try:
        response = requests.post(f"{JIRA_URL}/rest/api/3/issue/bulkfetch", headers=HEADERS, json=payload)
        for issue in response.json().get('issues', []):
            issue_key = issue['key']
            customfield_10082 = issue['fields'].get('customfield_10082')
            assignee_account_id = issue['fields'].get('assignee', {}).get('accountId') if issue['fields'].get('assignee') else None
            
            issues_data[issue_key] = (customfield_10082, assignee_account_id)
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Failed to get bulk issues: {response.text} status: {response.status_code} error: {e}")
    return issues_data

def get_bulk_changelog(issues): #? Max 1000 transitions per page, for more paging needed
    """"Get bulk changelogs from Jira and return the transitions for each issue."""
    if issues == []:
        return []
    
    filtered_data = []
    payload = {
        "issueIdsOrKeys": issues,
        "fieldIds": [
            "status"
        ],
        "maxResults": 1000
    }

    try:
        response = requests.post(f"{JIRA_URL}/rest/api/3/changelog/bulkfetch", headers=HEADERS, json=payload)
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
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Failed to get bulk changelogs: {response.text} status: {response.status_code} error: {e}")

    for issue in filtered_data:
        issue["transitions"].sort(key=lambda x: x["date"], reverse=True)
    return filtered_data

def get_bulk_changelog_paging(issues): #? Implemented paging in case of large datasets, not using it because not 100% sure if it works
    if not issues:
        return []

    filtered_data = {}
    payload = {
        "issueIdsOrKeys": issues,
        "fieldIds": ["status"],
        "maxResults": 1000
    }

    while True:
        response = requests.post(f"{JIRA_URL}/rest/api/3/changelog/bulkfetch", headers=HEADERS, json=payload)

        if response.ok:
            data = response.json()
            issue_logs = data.get("issueChangeLogs", [])

            for issue in issue_logs:
                issue_id = issue["issueId"]
                transitions = [
                    {
                        "author": history["author"]["displayName"],
                        "date": history["created"],
                        "from": item["fromString"],
                        "to": item["toString"],
                        "field": item["field"]
                    }
                    for history in issue.get("changeHistories", [])
                    for item in history.get("items", [])
                    if item["field"] == "status"
                ]

                if transitions: # Merge transitions if issueId already exists
                    if issue_id in filtered_data:
                        filtered_data[issue_id].extend(transitions)
                    else:
                        filtered_data[issue_id] = transitions

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

            payload["nextPageToken"] = next_page_token

        else:
            print(f"❌ Failed to get bulk changelogs: {response.text} status: {response.status_code}")
            break
    
    # Return sorted transitions by date and merge duplicates
    return [
        {
            "issueId": issue_id,
            "transitions": sorted(transitions, key=lambda x: x["date"], reverse=True)
        }
        for issue_id, transitions in filtered_data.items()
    ]

def create_jira_issues(df, existing_elements, check_date=True):
    """Create Jira issues from a DataFrame and return their keys."""
    bulk_issue_data = {"issueUpdates": []}

    for _, row in df.iterrows():
        if row['Customer Name'] in existing_elements:
            continue

        last_date = datetime.strptime(row['Last Transaction Date'], "%m/%d/%Y").strftime("%Y-%m-%d")
        days_diff = (date.today() - datetime.strptime(last_date, "%Y-%m-%d").date()).days
        if check_date and days_diff < 90:
            continue
        logging.info(f"Creating issue for customer: {customer_name}, Days since last transaction: {days_diff}")

        company_name = row['Customer Name']
        customer_name = row['Customer Name']

        issue_payload = {
            "fields": {
                "issuetype": {"id": 10001}, #? Lead hardcoded
                "assignee": {"id": DEFAULT_ASSIGNED_USER}, #? webadmin hardcoded
                "project": {"key": JIRA_PROJECT_KEY},
                "summary": str(customer_name),
                "customfield_10050": str(last_date), 
                "customfield_10052": str(row['Last Transaction Amount']),
                "customfield_10041": str(company_name),
                "customfield_10043": str(customer_name),
                "customfield_10042": str(row['SMS']),
                "customfield_10039": str(row['Email'])
            }
        }

        bulk_issue_data["issueUpdates"].append(issue_payload)

    if bulk_issue_data["issueUpdates"] == []:
        print("No issues to create.")
        return []

    try:
        response = requests.post(f"{JIRA_URL}/rest/api/3/issue/bulk", headers=HEADERS, json=bulk_issue_data)
        keys = [issue["key"] for issue in response.json().get("issues", [])]
        logging.info(f"✅ Successfully created {len(keys)} issues: {keys}")
        return keys
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to create issue: {response.text}")
        return []

def get_transitions(key):
    response = requests.get(f"{JIRA_URL}/rest/api/3/issue/{key}/transitions", headers=HEADERS)

    if response.ok:
        print(f"Transitions for issue {key}:")
        print(response.json())
    else:
        print(f"Failed to get transitions: {response.text}")

def transition_jira_issues(transition, keys): #? Max 1000 transitions
    """"Transition Jira issues to a new status."""
    if keys == []:
        logging.info("No issue keys provided. Skipping transition.")
        return
    
    transition_payload = {
        "bulkTransitionInputs": [
            { 
                "selectedIssueIdsOrKeys": keys, 
                "transitionId": TRANSITIONS.get(transition.lower(), 0)
            }
        ],
        "sendBulkNotification": False
    }

    try:
        response = requests.post(f"{JIRA_URL}/rest/api/3/bulk/issues/transition", json=transition_payload, headers=HEADERS) 
        for key in keys:
            logging.info(f"✅ Issue {key} moved to '{transition}'")
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Failed to transition issue: {response.text} status: {response.status_code} error: {e}")

def send_email(subject, message, email_receiver):
    """Send an email with the given subject and message to the email receiver."""
    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = email_receiver
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure the connection
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, email_receiver, msg.as_string())
            logging.info("✅ Email sent successfully!")
    except Exception as e:
        logging.error(f"❌ Failed to send email: {e}")

def send_email_jira(key, message): #TODO Jira supports sending emails, can't get it to work for now
    payload = {
        "subject": "Subject of the Email",
        "textBody": "Plain text version of the email body.",
        "htmlBody": "<h1>HTML formatted version of the email</h1>",
        "to": {
            "assignee": "true",
            "reporter": "false",
            "watchers": "false",
            "voters": "false",
            "users": [
                {
                    "accountId": "70121:bed40c39-1b16-4eff-a88c-809250e73b31"
                }
            ],
            "groups": []
        },
        "restrict": {
            "groups": [],
            "permissions": []
        }
    }

    response = requests.post(f"{JIRA_URL}/rest/api/3/issue/{key}/notify", headers=HEADERS, data=json.dumps(payload))
    if response.ok:
        print("✅ Email sent successfully!")
    else:
        print(f"❌ Failed to send email: {response.text}")

def get_email_message(summary, time_of_last_change, send_email_time): #TODO Add link to jira item
    """Return an email message with the given summary, time of last change, and send email time."""
    today_timestamp = int(datetime.now().timestamp())
    return f"""
                <html>
                <head>
                    <style>
                        body {{
                            font-family: 'Arial', 'Helvetica', sans-serif;
                            font-size: 1.6rem;
                            line-height: 1.8;
                            color: #2c2c2c;
                            margin: 20px;
                        }}
                        .content {{
                            max-width: 600px;
                        }}
                        .highlight {{
                            color: #b71c1c;
                            font-weight: bold;
                        }}
                        .footer {{
                            margin-top: 25px;
                            font-size: 14px;
                            color: #555;
                            border-top: 1px solid #ddd;
                            padding-top: 10px;
                        }}
                    </style>
                </head>
                <body>
                    <div class="content">
                        <p>This is a reminder to follow up on the lead <span class="highlight">{summary}</span>.</p>
                        <p>The issue was moved to <strong>'In Progress'</strong> on <strong>{datetime.fromtimestamp(time_of_last_change)}</strong>.</p>
                        <p>The message was scheduled for <strong>{datetime.fromtimestamp(today_timestamp + send_email_time)}</strong>, 
                        which is in <strong>{send_email_time}</strong> seconds.</p>
                        <p>Please ensure timely action on this matter.</p>
                        <div class="footer">
                            <p>This is an automated message from the Jira Automation System.</p>
                        </div>
                    </div>
                </body>
                </html>
            """

def schedule_emails_list(days_delay, status): #? 4 requests per call
    """"Schedule emails for issues in a specific status."""
    issues, keys, summarys  = search_issues(status)
    changelogs = get_bulk_changelog(issues)
    issues_data = get_bulk_issues(issues)
    today_timestamp = int(datetime.now().timestamp())
    send_email_time = 0
    scheduled_emails = []
    issues_to_update = []
    issue_count = len(issues)

    for issue, key, summary in zip(issues, keys, summarys):
        try: 
            transitions = next((log for log in changelogs if log['issueId'] == issue), None)['transitions']
            if not transitions:
                logging.warning(f"No transitions found for issue {key}. Skipping.")
                continue
            
            date = issues_data.get(key, (None, None))[0]
            if date is not None:
                issue_count -= 1
                continue
            
            transition = transitions[0]
            if transition['field'] == 'status' and transition['to'] == 'In Progress':
                time_of_last_change = int(transition['date']) // 1000
            else:
                logging.warning(f"No 'In Progress' transition found for issue {key}. Skipping.")
                continue

            time_diff_seconds = today_timestamp - time_of_last_change
            days, remainder = divmod(time_diff_seconds, 86400)
            if days < days_delay:
                send_email_time = 3*24*60*60 - time_diff_seconds

            assignee_id = issues_data.get(key, (None, None))[1]
            email_receiver = USERS.get(assignee_id) if assignee_id else None
            if not email_receiver:
                logging.warning(f"No assignee found for issue {key}. Skipping.")
                continue

            subject = f"JIRA {key} - Follow Up Reminder"
            message = get_email_message(summary, time_of_last_change, send_email_time)

            issues_to_update.append(key)
            scheduled_emails.append((key, subject, message, email_receiver, send_email_time))

        except Exception as e:
            logging.error(f"❌ Failed processing issue {key}: {e}")
            continue

    if issues_to_update == []:
        logging.info("No issues to update.")
        return []
    
    payload = {
        "editedFieldsInput": {
            "datePickerFields": [
                {
                    "date": {
                        "formattedDate": datetime.fromtimestamp(today_timestamp + send_email_time).strftime("%Y-%m-%d")
                    },
                    "fieldId": "customfield_10082"
                }
            ]
        },
        "selectedActions": ["customfield_10082"],
        "selectedIssueIdsOrKeys": issues_to_update,
        "sendBulkNotification": False
    }

    try:
        response = requests.post(f"{JIRA_URL}/rest/api/3/bulk/issues/fields", headers=HEADERS, data=json.dumps(payload))

        for key in issues_to_update:
            logging.info(f"✅ Labels updated successfully for {key}")
        
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Failed to update labels: {e}")
        return []

    logging.info(f"Returned {issue_count} emails to be scheduled.")
    return scheduled_emails

def schedule_emails(days_delay, status): #? 4 requests per call
    """Schedule emails for issues in a specific status."""
    logging.info("=========================")
    logging.info("Scheduling emails...")
    try:
        emails_to_send = schedule_emails_list(days_delay, status)
    except Exception as e:
        logging.error(f"❌ Failed to retrieve emails to send: {e}")
        return
    delay_seconds = 5
    for issue_key, subject, message, email_receiver, send_email_delay in emails_to_send:
        try:
            run_date = datetime.now() + timedelta(seconds=delay_seconds)
            logging.info(f"Email will be sent on {run_date}")
            if email_receiver is None:
                logging.warning(f"❌ Email for issue {issue_key} has no receiver (label was still added).")
                continue
            scheduler.add_job(
                send_email,
                'date',
                run_date=run_date,
                args=[subject, message, email_receiver]
            )
            print(f"✉️  Email scheduled for issue {issue_key} for {email_receiver} in {delay_seconds} seconds.")
        except Exception as e:
            logging.error(f"❌ Failed to schedule email for issue {issue_key}: {e}")
            continue

def import_lapsed_clients(sheet): #? 3 requests per call (max 100 issues in status)
    """Import lapsed clients from a Google Sheet and transition them to status."""
    logging.info("=========================")
    logging.info("Importing lapsed clients...")

    try:
        issues, keys, lapsed = search_issues("Lapsed")
        logging.info(f"Found {len(lapsed)} existing lapsed issues.")
        
        df = read_google_sheet(authenticate_google_sheets(), sheet)
        new_keys = create_jira_issues(df, lapsed)
        if new_keys:
            logging.info(f"Created {len(new_keys)} new issues.")
            transition_jira_issues("Lapsed", new_keys)
        else:
            logging.info("No new issues to create.")
    except Exception as e:
        logging.error(f"❌ Failed to import lapsed clients: {e}")

def check_for_new_orders(sheet):
    print("Checking for new orders...")
    client = authenticate_google_sheets()
    df = read_google_sheet(client, sheet)

    if df is not None and not df.empty:
        keys = create_jira_issues(df, [], check_date=False)
        transition_jira_issues("New Web Order", keys)
        clear_google_sheet(client, sheet)
    else:
        print("No new orders found.")

def print_task_list():
    jobs = scheduler.get_jobs()
    if not jobs:
        print("No scheduled tasks.")
    else:
        print("Scheduled Tasks:")
        for job in jobs:
            print(f"- Job ID: {job.id}, Function: {job.func.__name__}, Run Time: {job.next_run_time}")

def main():
    setup_logging()

    scheduler.add_job(
        import_lapsed_clients,
        'interval',
        weeks=1,
        args=["Lapsed"]
    )
    scheduler.add_job(
        check_for_new_orders,
        'interval',
        minutes=15,
        args=["New Web Order"]
    )
    scheduler.add_job(
        schedule_emails,
        'interval',
        minutes=15,
        args=[3, "In Progress"]
    )

    while True: # TODO Make a django and html ui for this
        user_input = input("Enter a command (Tasks, Delete, Exit): \n").strip().lower()
        if user_input == "tasks" or user_input == "t":
            print_task_list()
        elif user_input == "delete" or user_input == "d":
            print_task_list()
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
