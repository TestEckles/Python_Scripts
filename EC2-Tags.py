# Summary:
# This script retrieves EC2 instance IDs and their associated tags across multiple AWS profiles in a specified region.
# It consolidates the results into an Excel file, creating a worksheet for each AWS profile.
# Each worksheet lists instance IDs along with their respective tag keys and values as columns.
# The final Excel file is saved in the user's Downloads folder with a predefined filename.

import boto3
import json
import xlsxwriter
from botocore.exceptions import ClientError
import re

REGION = "us-east-1"  # Set the default region you want to query

def get_ec2_instances_with_tags(profile):
    session = boto3.Session(profile_name=profile, region_name=REGION)
    ec2_client = session.client("ec2")
    try:
        instances = []
        response = ec2_client.describe_instances()
        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                instances.append({
                    "InstanceId": instance["InstanceId"],
                    "Tags": instance.get("Tags", []),
                })
        return instances
    except ClientError as error:
        print(f"Failed to describe instances for profile {profile}: {error}")
        return []

def sanitize_worksheet_name(name):
    name = re.sub(r"_account$", "", name)  # Remove '_account' suffix
    return name[:31].replace("/", "-").replace("\\", "-")

def main():
    session = boto3.Session()
    profiles = session.available_profiles  # Remove limit to process all profiles
    
    # Create an Excel workbook and add worksheets for each profile
    output_path = "/Users/saraeck/Downloads/ec2final.xlsx"
    workbook = xlsxwriter.Workbook(output_path)
    worksheet_names = set()
    
    for profile in profiles:
        print(f"Fetching EC2 instances for profile: {profile}")
        instances = get_ec2_instances_with_tags(profile)
        
        # Create a new worksheet for each profile with a unique name
        worksheet_name = sanitize_worksheet_name(profile)
        original_name = worksheet_name
        suffix = 1
        while worksheet_name in worksheet_names:
            worksheet_name = f"{original_name}_{suffix}"
            suffix += 1
        worksheet_names.add(worksheet_name)
        
        worksheet = workbook.add_worksheet(worksheet_name)
        worksheet.write(0, 0, "InstanceId")
        
        # Collect all tag keys to create columns for each tag key
        all_tag_keys = set()
        for instance in instances:
            for tag in instance.get("Tags", []):
                all_tag_keys.add(tag["Key"])
        all_tag_keys = sorted(all_tag_keys)
        
        # Write tag keys as column headers
        col = 1
        tag_key_to_col = {}
        for tag_key in all_tag_keys:
            worksheet.write(0, col, tag_key)
            tag_key_to_col[tag_key] = col
            col += 1
        
        # Write instance details to the worksheet
        row = 1
        for instance in instances:
            worksheet.write(row, 0, instance["InstanceId"])
            for tag in instance.get("Tags", []):
                tag_key = tag["Key"]
                tag_value = tag["Value"]
                if tag_key in tag_key_to_col:
                    worksheet.write(row, tag_key_to_col[tag_key], tag_value)
            row += 1
    
    workbook.close()
    print(f"EC2 instances and tags saved to {output_path}")

if __name__ == "__main__":
    main()

