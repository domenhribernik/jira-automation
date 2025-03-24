import csv

def filter_missing_images(input_file, output_file):
    with open(input_file, mode='r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        filtered_rows = [row for row in reader if not row['Images'] and '-OS' not in row['Categories']]

    with open(output_file, mode='w', newline='', encoding='utf-8') as csvfile:
        fieldnames = filtered_rows[0].keys() if filtered_rows else []
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_rows)

if __name__ == "__main__":
    input_file = 'test scripts/input.csv'  # Replace with your input CSV file path
    output_file = 'test scripts/output.csv'  # Replace with your desired output CSV file path
    filter_missing_images(input_file, output_file)