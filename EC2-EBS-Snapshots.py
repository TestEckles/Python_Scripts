# Summary:
# This script fetches AWS EBS snapshots older than 80 days across specified regions for all configured AWS CLI profiles.
# It generates an Excel report containing details like Snapshot ID, account name, region, start time, and snapshot age,
# saving the report to the user's Downloads folder.

import boto3
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd

# Configurations
REGIONS = ["us-east-1", "eu-central-1"]  # Specify regions to process
DAYS = 80  # Fetch snapshots older than 80 days
DOWNLOADS_FOLDER = str(Path.home() / "Downloads")

def get_all_profiles():
    """Get all configured AWS profiles."""
    session = boto3.Session()
    return session.available_profiles  # Process all available profiles

def fetch_old_snapshots(profile, regions, days):
    """Retrieve all EBS snapshots older than a specified number of days across multiple regions."""
    session = boto3.Session(profile_name=profile)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    snapshots = []

    for region in regions:
        try:
            ec2_client = session.client("ec2", region_name=region)
            response = ec2_client.describe_snapshots(OwnerIds=['self'])

            for snapshot in response['Snapshots']:
                age = (datetime.now(timezone.utc) - snapshot['StartTime']).days
                # Include all snapshots older than the cutoff date
                if snapshot['StartTime'] < cutoff_date:
                    snapshots.append({
                        "SnapshotId": snapshot['SnapshotId'],
                        "AccountName": profile,
                        "Region": region,
                        "CreatorARN": snapshot.get("Description", "Unknown"),
                        "StartTime": snapshot['StartTime'].replace(tzinfo=None),
                        "Age (Days)": age
                    })
        except Exception as e:
            print(f"Error fetching snapshots in region {region} for profile {profile}: {e}")
    
    return snapshots

def save_to_excel(snapshots):
    """Save the snapshots data to an Excel file."""
    output_file = DOWNLOADS_FOLDER + f"/snapshots_over_80days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    snapshots_df = pd.DataFrame(snapshots)
    snapshots_df.to_excel(output_file, sheet_name="Old Snapshots", index=False)
    print(f"Data saved to {output_file}")

def main():
    profiles = get_all_profiles()  # Process all available profiles
    all_snapshots = []

    for profile in profiles:
        try:
            profile_snapshots = fetch_old_snapshots(profile, REGIONS, DAYS)
            all_snapshots.extend(profile_snapshots)
            print(f"Finished processing profile: {profile}")
        except Exception as e:
            print(f"Error processing profile {profile}: {e}")

    # Save to Excel
    save_to_excel(all_snapshots)

if __name__ == "__main__":
    main()

