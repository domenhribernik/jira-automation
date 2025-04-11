import re
import pandas as pd

def sql_to_excel(sql_file, excel_file):
    insert_pattern = re.compile(
        r"INSERT INTO `?(?P<table>\w+)`?\s*\((?P<columns>[^)]+)\)\s*VALUES\s*(?P<values>.+);", 
        re.IGNORECASE | re.DOTALL
    )
    
    all_rows = []
    columns = []

    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    match = insert_pattern.search(sql_content)
    if match:
        columns = [col.strip('` ') for col in match.group("columns").split(',')]
        values_raw = match.group("values")

        # Match each value tuple
        value_tuples = re.findall(r'\((.*?)\)', values_raw, re.DOTALL)
        for value in value_tuples:
            # Handle commas inside quotes correctly
            parsed = [v.strip().strip("'") for v in re.split(r",(?=(?:[^']*'[^']*')*[^']*$)", value)]
            all_rows.append(parsed)

    # Create DataFrame and export to Excel
    df = pd.DataFrame(all_rows, columns=columns)
    df.to_excel(excel_file, index=False, engine='openpyxl')

if __name__ == "__main__":
    sql_file = 'test scripts/zip.sql'  # Replace with your SQL file path
    excel_file = 'test scripts/zip.xlsx'  # Replace with desired Excel file path
    sql_to_excel(sql_file, excel_file)
