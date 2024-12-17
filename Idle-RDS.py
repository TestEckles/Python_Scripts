# Summary:
# This script identifies idle Amazon RDS instances based on low activity metrics (e.g., CPU, IOPS, Network Throughput)
# over the past 30 days. It checks RDS instances across multiple AWS profiles and specified regions.
# Instances are considered idle if all activity metrics fall below predefined thresholds.
# Results, including instance details and idle status, are saved to an Excel file in the user's Downloads folder.
# The script uses threading for parallel processing of AWS profiles and regions.

import boto3
from datetime import datetime, timezone, timedelta
from openpyxl import Workbook
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

# Configuration
REGIONS = ["us-east-1", "eu-west-1"]  # Add more regions as needed
IDLE_DAYS = 30  # Days to check for idle activity
DOWNLOADS_FOLDER = os.path.expanduser("~/Downloads")
MAX_THREADS = 10
METRIC_THRESHOLDS = {
    "DatabaseConnections": 1,
    "ReadIOPS": 5,
    "WriteIOPS": 5,
    "CPUUtilization": 5,
    "NetworkReceiveThroughput": 1024,  # in bytes
    "NetworkTransmitThroughput": 1024,  # in bytes
}

def get_all_profiles():
    """Get all configured AWS profiles."""
    session = boto3.Session()
    return session.available_profiles

def fetch_paginated_results(client, method, key, **kwargs):
    """Fetch results from a paginated API call."""
    paginator = client.get_paginator(method)
    results = []
    for page in paginator.paginate(**kwargs):
        results.extend(page[key])
    return results

def get_cluster_role(profile, region, db_instance_id):
    """Identify the cluster role of an RDS instance."""
    session = boto3.Session(profile_name=profile)
    rds_client = session.client("rds", region_name=region)

    try:
        clusters = fetch_paginated_results(rds_client, "describe_db_clusters", "DBClusters")
        for cluster in clusters:
            for member in cluster["DBClusterMembers"]:
                if member["DBInstanceIdentifier"] == db_instance_id:
                    return member["IsClusterWriter"]  # True for Writer, False for Reader
    except Exception as e:
        print(f"Error fetching cluster role for {db_instance_id}: {str(e)}")
    return None

def get_rds_metrics(profile, region, db_instance_id):
    """Retrieve multiple RDS metrics to identify idleness."""
    session = boto3.Session(profile_name=profile)
    cloudwatch_client = session.client("cloudwatch", region_name=region)

    idle = True
    for metric, threshold in METRIC_THRESHOLDS.items():
        try:
            response = cloudwatch_client.get_metric_statistics(
                Namespace="AWS/RDS",
                MetricName=metric,
                Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_instance_id}],
                StartTime=datetime.now(timezone.utc) - timedelta(days=IDLE_DAYS),
                EndTime=datetime.now(timezone.utc),
                Period=3600 * 24,
                Statistics=["Average"],
            )
            datapoints = response.get("Datapoints", [])
            if any(point["Average"] > threshold for point in datapoints):
                idle = False
                break
        except Exception as e:
            print(f"Error fetching {metric} for {db_instance_id}: {str(e)}")
    return idle

def get_idle_rds_instances(profile, region, idle_days):
    """Check RDS instances for idleness using cluster role and multi-metrics."""
    session = boto3.Session(profile_name=profile)
    rds_client = session.client("rds", region_name=region)
    sts_client = session.client("sts")
    account_id = sts_client.get_caller_identity()["Account"]

    idle_instances = []

    try:
        db_instances = fetch_paginated_results(rds_client, "describe_db_instances", "DBInstances")
        for db_instance in db_instances:
            db_instance_id = db_instance["DBInstanceIdentifier"]
            
            # Skip instances that are not writers
            cluster_role = get_cluster_role(profile, region, db_instance_id)
            if cluster_role is False:  # Reader/Standby instance
                print(f"Skipping standby instance: {db_instance_id}")
                continue
            
            # Check if metrics indicate idle
            if get_rds_metrics(profile, region, db_instance_id):
                idle_instances.append({
                    "DBInstanceIdentifier": db_instance_id,
                    "DBInstanceClass": db_instance["DBInstanceClass"],
                    "Engine": db_instance["Engine"],
                    "Region": region,
                    "AccountName": profile,
                    "AccountNumber": account_id,
                    "IdleStatus": "No significant activity",
                })
    except Exception as e:
        print(f"Error fetching idle RDS instances for profile {profile} in region {region}: {str(e)}")

    return idle_instances

def save_to_excel(idle_instances):
    """Save the data to an Excel file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(DOWNLOADS_FOLDER, f"idle_rds_instances_{timestamp}.xlsx")

    wb = Workbook()
    ws = wb.active
    ws.title = "Idle RDS Instances"

    if idle_instances:
        headers = list(idle_instances[0].keys())
        ws.append(headers)
        for instance in idle_instances:
            ws.append(list(instance.values()))
    else:
        ws.append(["No idle RDS instances found"])

    wb.save(output_file)
    print(f"Data saved to {output_file}")

def main():
    profiles = get_all_profiles()
    if not profiles:
        print("No AWS profiles found. Configure them using 'aws configure'.")
        return

    all_idle_instances = []

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [
            executor.submit(get_idle_rds_instances, profile, region, IDLE_DAYS)
            for profile in profiles for region in REGIONS
        ]

        for future in as_completed(futures):
            try:
                result = future.result()
                all_idle_instances.extend(result)
            except Exception as e:
                print(f"Error occurred: {str(e)}")

    # Summary Report
    print(f"Processed profiles: {profiles}")
    print(f"Processed regions: {REGIONS}")
    print(f"Total idle RDS instances found: {len(all_idle_instances)}")

    save_to_excel(all_idle_instances)

if __name__ == "__main__":
    main()

