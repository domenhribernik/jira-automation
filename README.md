# jira-automation

## Overview

This project reads data from Google Sheets or a local CSV file and uploads each column as a Jira issue after filtering the data. The issues are then sorted into the correct Kanban status. The program also reads the issues already in a status to avoid duplication. Currently, it works for the following rows:
- Customer Name
- Last Transaction Date
- Last Transaction Amount
- Email
- SMS

## Features

- Read data from Google Sheets or a local CSV file
- Filter and upload data as Jira issues
- Sort issues into the correct Kanban status
- Avoid duplication by checking existing issues

## Usage

1. Ensure you have the necessary credentials and access to the Google Sheets or the local CSV file. You need to add a Jira token and Google credentials. You can follow an online tutorial to create your own sheet and add it into the constants.
2. The current supported columns are:
    - Customer Name
    - Last Transaction Date
    - Last Transaction Amount
    - Email
    - SMS
3. Run the `main.py` script to start the process.


## Setup

1. Clone the repository.
2. Install the required libraries using `pip install -r requirements.txt`.
3. Configure your Google Sheets and Jira credentials in the script.

## Running the Script

```bash
python main.py
```

## License

This project is licensed under the CC-BY-NC-ND License.