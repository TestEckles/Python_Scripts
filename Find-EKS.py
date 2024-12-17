# Summary:
# This script identifies EC2 instances provisioned by Karpenter that require rightsizing based on AWS Compute Optimizer recommendations.
# It also checks attached EBS volumes for rightsizing recommendations and includes instances where both the instance
# and at least one EBS volume need adjustments.
# The script processes multiple AWS profiles and regions concurrently using threading to improve efficiency.
# Results, including profile, account ID, region, instance ID, and volume IDs, are saved in an Excel file.
# The Excel file is timestamped and stored in the user's Downloads folder.

import boto3
import pandas as pd
from botocore.exceptions import ClientError, EndpointConnectionError
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from datetime import datetime

# Configure AWS regions and download path
REGIONS = ["us-east-1", "us-west-1"]  # Add regions as needed
TAG_KEY = "karpenter.sh/provisioner-name"
downloads_path = os.path.expanduser("~/Downloads")

# Store results
results = []

def backoff_retry(func, *args, retries=5, initial_delay=2, **kwargs):
    """ Helper function to retry AWS calls with exponential backoff """
    delay = initial_delay
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except ClientError as e:
            if e.response['Error']['Code'] == 'Throttling':
                print(f"Throttling error. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2
            else:
                raise
    raise Exception("Max retries reached for function call.")

def collect_karpenter_data(profile):
    """ Collect EC2 and volume recommendations for a given profile. """
    session = boto3.Session(profile_name=profile)
    account_results = []
    try:
        for region in REGIONS:
            ec2_client = session.client("ec2", region_name=region)
            compute_optimizer_client = session.client("compute-optimizer", region_name=region)

            # Get AWS Account ID
            account_id = session.client('sts').get_caller_identity()['Account']

            # Get EC2 instances with Karpenter tags
            instances = backoff_retry(
                ec2_client.describe_instances,
                Filters=[{'Name': f'tag:{TAG_KEY}', 'Values': ['*']}]
            ).get('Reservations', [])

            for reservation in instances:
                for instance in reservation['Instances']:
                    instance_id = instance["InstanceId"]
                    instance_arn = f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}"

                    # Get EC2 recommendations
                    ec2_recommendations = backoff_retry(
                        compute_optimizer_client.get_ec2_instance_recommendations,
                        instanceArns=[instance_arn]
                    ).get('instanceRecommendations', [])

                    # Check if the instance needs rightsizing
                    instance_needs_rightsizing = bool(ec2_recommendations)

                    # Get attached volumes and recommendations
                    volumes = instance.get("BlockDeviceMappings", [])
                    volume_ids_needing_rightsizing = []
                    for vol in volumes:
                        volume_id = vol["Ebs"]["VolumeId"]
                        volume_arn = f"arn:aws:ec2:{region}:{account_id}:volume/{volume_id}"
                        vol_recs = backoff_retry(
                            compute_optimizer_client.get_ebs_volume_recommendations,
                            volumeArns=[volume_arn]
                        ).get('volumeRecommendations', [])
                        if any(
                            vol_rec.get("volumeRecommendation", {}).get("volumeType") != vol_rec.get("currentConfiguration", {}).get("volumeType")
                            for vol_rec in vol_recs
                        ):
                            volume_ids_needing_rightsizing.append(volume_id)

                    # Include only if both the instance and at least one volume need rightsizing
                    if instance_needs_rightsizing and volume_ids_needing_rightsizing:
                        account_results.append({
                            "Profile": profile,
                            "AccountId": account_id,
                            "Region": region,
                            "InstanceId": instance_id,
                            "VolumeIds": ", ".join(volume_ids_needing_rightsizing)
                        })

    except (ClientError, EndpointConnectionError) as e:
        print(f"Error processing profile {profile}: {e}")
    return account_results

def save_to_excel(data):
    """ Save results to an Excel file with a summary. """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_output_path = os.path.join(downloads_path, f"Karpenter_Rightsizing_Report_{timestamp}.xlsx")

    if not data:
        print("No rightsizing recommendations found.")
        return

    summary_df = pd.DataFrame(data)
    with pd.ExcelWriter(excel_output_path) as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Summary")

    print(f"Excel report saved to: {excel_output_path}")

if __name__ == "__main__":
    # Process profiles in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_profile = {executor.submit(collect_karpenter_data, profile): profile for profile in boto3.Session().available_profiles}
        for future in as_completed(future_to_profile):
            profile = future_to_profile[future]
            try:
                results.extend(future.result())
            except Exception as e:
                print(f"Error processing profile {profile}: {e}")

    # Save results to Excel
    save_to_excel(results)
    print("Rightsizing checks completed.")

