# Summary:
# This script retrieves last accessed details for IAM roles in the AWS account configured for a specific profile.
# It generates a service access report using AWS Access Advisor and calculates the days since each service was last accessed.
# For each role, the script displays the service name, last accessed date, and days since last activity.

import boto3
import time
from datetime import datetime, timedelta

# Initialize the boto3 IAM client with the specific profile
session = boto3.Session(profile_name='912')
iam = session.client('iam')

# Function to get last accessed information for a limited number of IAM roles and display as days
def get_iam_roles_last_accessed():
    # List a limited number of IAM roles (e.g., first 3 roles)
    response = iam.list_roles(MaxItems=3)

    # Loop through each role and get access advisor information
    for role in response['Roles']:
        role_name = role['RoleName']
        
        # Generate the last accessed report
        access_advisor = iam.generate_service_last_accessed_details(
            Arn=role['Arn']
        )
        
        job_id = access_advisor['JobId']
        
        # Wait for the job to complete (checking every 10 seconds)
        while True:
            job_status = iam.get_service_last_accessed_details(JobId=job_id)
            if job_status['JobStatus'] == 'COMPLETED':
                break
            else:
                time.sleep(10)  # Wait before checking the status again
        
        # Fetch the last accessed details after the job completes
        last_accessed_details = iam.get_service_last_accessed_details(JobId=job_id)

        # Check if 'ServicesLastAccessed' key exists
        if 'ServicesLastAccessed' in last_accessed_details:
            print(f"Role: {role_name}")
            for service in last_accessed_details['ServicesLastAccessed']:
                service_name = service['ServiceName']
                last_authenticated = service.get('LastAuthenticated', None)
                
                if last_authenticated:
                    # Calculate days since last accessed directly
                    days_ago = (datetime.utcnow() - last_authenticated).days
                    print(f"  Service: {service_name}, Last Accessed: {days_ago} days ago")
                else:
                    print(f"  Service: {service_name}, Last Accessed: Never")
            print()
        else:
            print(f"Role: {role_name}, No services accessed.")
            print()

# Call the function to test with a few roles
get_iam_roles_last_accessed()

