# Summary:
# This script checks for AWS Load Balancers (ELBv2) and their Target Groups across all configured AWS profiles.
# It identifies unhealthy targets, empty Target Groups, and Load Balancers with no attached Target Groups.
# The script runs concurrently for multiple profiles using threads and saves the results into an Excel file.
# The output includes resource details such as resource name, status, and associated AWS account.

import boto3
import pandas as pd
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, EndpointConnectionError, ClientError
from botocore.config import Config
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random
import os
from datetime import datetime

# Step 1: Authenticate with all accounts using aws-sso-util
os.system("aws-sso-util login --all")

# Step 2: Get all AWS profiles configured in the environment
session = boto3.Session()
available_profiles = session.available_profiles

# Store results in a dictionary
results = {}
region = 'us-east-1'  # Replace with your desired region

# Specify the path to the Downloads folder
downloads_path = os.path.expanduser("~/Downloads")

def backoff_retry(func, *args, retries=10, initial_delay=10, **kwargs):
    """ Helper function to retry a function with exponential backoff """
    delay = initial_delay
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except ClientError as e:
            if e.response['Error']['Code'] == 'Throttling':
                print(f"Throttling error encountered. Retrying in {delay} seconds (attempt {attempt + 1} of {retries})...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise
    raise Exception(f"Max retries reached for function: {func.__name__}")

def add_random_delay():
    delay = random.uniform(2, 5)  # Add a delay between 2 to 5 seconds
    print(f"Adding a random delay of {delay:.2f} seconds before moving to the next profile...")
    time.sleep(delay)

def find_unhealthy_targets_and_empty_target_groups(profile):
    account_name = profile  # Use the profile name as-is for results
    session_data = []
    try:
        # Create a session using the current profile with AWS SDK retry configuration
        retry_config = Config(
            retries={
                'max_attempts': 10,
                'mode': 'standard'
            }
        )
        session = boto3.Session(profile_name=profile)
        elbv2 = session.client('elbv2', region_name=region, config=retry_config)

        # Step 1: Check all target groups
        paginator = backoff_retry(elbv2.get_paginator, 'describe_target_groups')
        for page in backoff_retry(paginator.paginate):
            target_groups = page['TargetGroups']
            for tg in target_groups:
                tg_arn = tg['TargetGroupArn']
                tg_name = tg['TargetGroupName']
                try:
                    target_health_descriptions = backoff_retry(elbv2.describe_target_health, TargetGroupArn=tg_arn)['TargetHealthDescriptions']
                    if not target_health_descriptions:
                        session_data.append({
                            'Resource': 'Target Group',
                            'Name': tg_name,
                            'Status': 'No Targets'
                        })
                    else:
                        # Check for unhealthy targets
                        for target in target_health_descriptions:
                            if target['TargetHealth']['State'] == 'unhealthy':
                                session_data.append({
                                    'Resource': 'Target Group',
                                    'Name': tg_name,
                                    'Status': f'Unhealthy: {target["TargetHealth"]["Reason"]}'
                                })
                except ClientError as e:
                    session_data.append({
                        'Resource': 'Target Group',
                        'Name': tg_name,
                        'Status': f'Error: {str(e)}'
                    })

        # Step 2: Check all load balancers for unhealthy targets or empty target groups
        lb_paginator = backoff_retry(elbv2.get_paginator, 'describe_load_balancers')
        for lb_page in backoff_retry(lb_paginator.paginate):
            load_balancers = lb_page['LoadBalancers']
            for lb in load_balancers:
                lb_arn = lb['LoadBalancerArn']
                lb_name = lb['LoadBalancerName']
                try:
                    tg_attachments = backoff_retry(elbv2.describe_target_groups, LoadBalancerArn=lb_arn)['TargetGroups']
                    if not tg_attachments:
                        session_data.append({
                            'Resource': 'Load Balancer',
                            'Name': lb_name,
                            'Status': 'No Target Groups'
                        })
                    else:
                        for tg in tg_attachments:
                            tg_health_descriptions = backoff_retry(elbv2.describe_target_health, TargetGroupArn=tg['TargetGroupArn'])['TargetHealthDescriptions']
                            if not tg_health_descriptions:
                                session_data.append({
                                    'Resource': 'Load Balancer',
                                    'Name': lb_name,
                                    'Status': f'Empty Target Group: {tg["TargetGroupName"]}'
                                })
                            else:
                                for target in tg_health_descriptions:
                                    if target['TargetHealth']['State'] == 'unhealthy':
                                        session_data.append({
                                            'Resource': 'Load Balancer',
                                            'Name': lb_name,
                                            'Status': f'Associated Target Group: {tg["TargetGroupName"]} has Unhealthy target(s)'
                                        })
                except ClientError as e:
                    session_data.append({
                        'Resource': 'Load Balancer',
                        'Name': lb_name,
                        'Status': f'Error: {str(e)}'
                    })

        # Store results for the account in the dictionary
        results[account_name] = session_data
        print(f"Completed checks for AWS Profile: {profile}.")  # Indicate profile completion
    except (NoCredentialsError, PartialCredentialsError):
        print(f"Unable to locate credentials for profile: {profile}")
    except EndpointConnectionError as e:
        print(f"Endpoint connection error for profile: {profile} in region: {region} - {str(e)}")
    except Exception as e:
        print(f"Error occurred for profile: {profile} - {str(e)}")

if __name__ == "__main__":
    # Track the last profile
    last_profile = available_profiles[-1]

    # Step 3: Use ThreadPoolExecutor to parallelize the process
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_profile = {executor.submit(find_unhealthy_targets_and_empty_target_groups, profile): profile for profile in available_profiles}

        for future in as_completed(future_to_profile):
            profile = future_to_profile[future]
            try:
                future.result()
            except Exception as exc:
                print(f'{profile} generated an exception: {exc}')
            finally:
                # Add delay only if it's not the last profile
                if profile != last_profile:
                    add_random_delay()
                else:
                    print(f"Finished processing the last profile: {profile}. No delay added.")

    # Step 4: Create an Excel output file with a timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_output_path = os.path.join(downloads_path, f'LoadBalancer_TargetGroup_Report_{timestamp}.xlsx')
    all_data = []
    for account, data in results.items():
        for entry in data:
            entry['Account'] = account  # Add account name to each entry
            all_data.append(entry)
    
    df = pd.DataFrame(all_data)
    df.to_excel(excel_output_path, index=False, sheet_name='Report')
    print(f"Excel report saved to: {excel_output_path}")

    print("All checks completed successfully.")

