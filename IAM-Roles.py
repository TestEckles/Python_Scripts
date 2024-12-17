# Summary:
# This script retrieves all IAM users and roles across multiple AWS profiles.
# It uses pagination to fetch IAM entities efficiently and consolidates the results into a single Excel file.
# The output includes the principal ID, type (User or Role), name, and ARN of each IAM entity.
# The final report is saved to the user's Downloads folder with a timestamped filename.

import boto3
from openpyxl import Workbook
from pathlib import Path
from datetime import datetime
import os

def get_all_profiles():
    """Get all configured AWS profiles."""
    session = boto3.Session()
    return session.available_profiles

def get_iam_entities(profile):
    """Retrieve all IAM users and roles."""
    session = boto3.Session(profile_name=profile)
    iam_client = session.client('iam')

    entities = []

    # Get all IAM users
    paginator = iam_client.get_paginator('list_users')
    for page in paginator.paginate():
        for user in page['Users']:
            entities.append({
                'PrincipalId': user['UserId'],
                'Type': 'User',
                'Name': user['UserName'],
                'ARN': user['Arn']
            })

    # Get all IAM roles
    paginator = iam_client.get_paginator('list_roles')
    for page in paginator.paginate():
        for role in page['Roles']:
            entities.append({
                'PrincipalId': role['RoleId'],
                'Type': 'Role',
                'Name': role['RoleName'],
                'ARN': role['Arn']
            })

    return entities

def save_to_excel(data):
    """Save the data to an Excel file."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Principal Mappings"

    if data:
        headers = list(data[0].keys())
        ws.append(headers)
        for entry in data:
            ws.append(list(entry.values()))
    else:
        ws.append(["No data found"])

    downloads_path = str(Path.home() / "Downloads")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Principal_Mappings_{timestamp}.xlsx"
    file_path = os.path.join(downloads_path, filename)
    wb.save(file_path)
    print(f"Data saved to {file_path}")

def main():
    profiles = get_all_profiles()
    if not profiles:
        print("No AWS profiles found. Configure them using 'aws configure'.")
        return

    all_principal_data = []

    for profile in profiles:
        try:
            print(f"Fetching data for profile: {profile}")
            entities = get_iam_entities(profile)
            all_principal_data.extend(entities)
        except Exception as e:
            print(f"Error fetching data for profile {profile}: {e}")

    save_to_excel(all_principal_data)

if __name__ == "__main__":
    main()

