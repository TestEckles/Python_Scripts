# Summary:
# This script retrieves all Amazon RDS instances that use the `gp2` storage type across multiple AWS profiles and regions.
# It dynamically creates Excel worksheets for each profile-region combination, ensuring unique worksheet names.
# The output Excel file contains details such as account number, DB instance identifier, engine, allocated storage, class, storage type, and region.
# The resulting file is saved to the Downloads folder, overwriting any existing file with the same name.
# 
# Error handling is implemented to gracefully skip profiles or regions with credential issues.

import boto3
import xlsxwriter
from botocore.exceptions import ClientError
import re

def get_rds_instances_with_gp2(profile, region):
    session = boto3.Session(profile_name=profile, region_name=region)
    rds_client = session.client("rds")
    try:
        rds_instances = []
        paginator = rds_client.get_paginator('describe_db_instances')
        for page in paginator.paginate():
            for db_instance in page['DBInstances']:
                storage_type = db_instance.get('StorageType', '')
                if storage_type == 'gp2':
                    rds_instances.append({
                        "AccountNumber": profile.split('.')[0],
                        "DBInstanceIdentifier": db_instance["DBInstanceIdentifier"],
                        "Engine": db_instance["Engine"],
                        "AllocatedStorage": db_instance["AllocatedStorage"],
                        "DBInstanceClass": db_instance["DBInstanceClass"],
                        "StorageType": storage_type,
                        "Region": region
                    })
        return rds_instances
    except ClientError as error:
        if error.response['Error']['Code'] == 'InvalidClientTokenId':
            print(f"Skipping region {region} for profile {profile}: Invalid token.")
        else:
            print(f"Failed to describe instances for profile {profile} in region {region}: {error}")
        return []

def sanitize_worksheet_name(name):
    name = re.sub(r'(_account|_Account)$', '', name)  # Remove '_account' or '_Account' suffix
    name = name[:31].replace("/", "-").replace("\\", "-")  # Ensure name is <= 31 characters and valid
    return name

import os

def main():
    output_path = "/Users/saraeck/Downloads/rds_gp2_instances_overwrite.xlsx"
    if os.path.exists(output_path):
        os.remove(output_path)
        print(f"Existing file '{output_path}' has been removed.")
    session = boto3.Session()
    profiles = session.available_profiles
    regions = [
    "us-east-1", "eu-central-1"
]  # Limited to specific regions for quicker output
    
    # Create an Excel workbook and add worksheets for each profile
    output_path = "/Users/saraeck/Downloads/rds_gp2_instances_overwrite.xlsx"
    workbook = xlsxwriter.Workbook(output_path)
    worksheet_names = set()
    
    data_written = False
    total_rds_instances = 0
    
    for profile in profiles:
        for region in regions:
            print(f"Fetching RDS instances for profile: {profile} in region: {region}")
            rds_instances = get_rds_instances_with_gp2(profile, region)
            total_rds_instances += len(rds_instances)
            
            if not rds_instances:
                print(f"No RDS gp2 instances found for profile: {profile} in region: {region}")
                continue
            
            # Create a new worksheet for each profile-region combination with a unique name
            worksheet_name = sanitize_worksheet_name(f"{profile}_{region}")
            original_name = worksheet_name
            suffix = 1
            while worksheet_name in worksheet_names:
                worksheet_name = f"{original_name[:28]}_{suffix}"
                suffix += 1
            worksheet_names.add(worksheet_name)
            
            worksheet = workbook.add_worksheet(worksheet_name)
            worksheet.write(0, 0, "AccountNumber")
            worksheet.write(0, 1, "DBInstanceIdentifier")  # Write DBInstanceIdentifier
            worksheet.write(0, 2, "Engine")
            worksheet.write(0, 3, "AllocatedStorage")  # Corrected column indexing
            worksheet.write(0, 4, "DBInstanceClass")  # Ensure DBInstanceClass column is distinct
            worksheet.write(0, 5, "StorageType")  # Ensure distinct column for StorageType
            worksheet.write(0, 6, "Region")
            
            # Write instance details to the worksheet
            row = 1
            for instance in rds_instances:
                worksheet.write(row, 0, instance["AccountNumber"])
                worksheet.write(row, 1, instance["DBInstanceIdentifier"])
                worksheet.write(row, 2, instance["Engine"])
                worksheet.write(row, 3, instance["AllocatedStorage"])  # Corrected column indexing
                worksheet.write(row, 4, instance["DBInstanceClass"])  # Ensure DBInstanceClass data is written correctly
                worksheet.write(row, 5, instance["StorageType"])  # Ensure distinct column for StorageType
                worksheet.write(row, 6, instance["Region"])
                row += 1
                data_written = True
    
    workbook.close()
    
    if data_written:
        print(f"RDS gp2 instances saved to {output_path}")
    print(f"Total RDS gp2 instances found: {total_rds_instances}")
    if not data_written:
        print("No RDS gp2 instances found.")

if __name__ == "__main__":
    main()

