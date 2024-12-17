# Summary:
# This script fetches cost and usage data from AWS Cost Explorer for the selected timeframes (daily, weekly, or monthly).
# It calculates cost comparisons between current and previous periods, including cost differences and percentage changes.
# The results are saved into an Excel file with separate sheets for each comparison type (Daily, Weekly, and Monthly).

import boto3
import datetime
import pandas as pd
import os

# AWS Cost Explorer client
client = boto3.client('ce', region_name='us-east-1')

# Set up date ranges
today = datetime.datetime.now().date()
yesterday = today - datetime.timedelta(days=1)
last_14_days = today - datetime.timedelta(days=14)
current_month_start = today.replace(day=1)
previous_month_end = current_month_start - datetime.timedelta(days=1)
previous_month_start = previous_month_end.replace(day=1)

# Function to fetch cost data
def fetch_cost_data(start_date, end_date, granularity):
    return client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date.strftime('%Y-%m-%d'),
            'End': end_date.strftime('%Y-%m-%d')
        },
        Granularity=granularity,
        Metrics=['UnblendedCost'],
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SERVICE'}
        ]
    )

# Main script logic
try:
    print("What type of cost comparison would you like to see?")
    print("1. Daily")
    print("2. Weekly")
    print("3. Monthly")
    print("4. All")
    choice = input("Enter your choice (1/2/3/4): ").strip()

    # Path for the output Excel file with a unique timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(os.path.expanduser("~/Downloads"), f'cost_comparison_{timestamp}.xlsx')

    # Initialize an Excel writer
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:

        # Daily Comparison
        if choice in ['1', '4']:
            today_response = fetch_cost_data(today, today + datetime.timedelta(days=1), 'DAILY')
            yesterday_response = fetch_cost_data(yesterday, today, 'DAILY')

            today_costs = {group['Keys'][0]: float(group['Metrics']['UnblendedCost']['Amount'])
                           for result in today_response['ResultsByTime'] for group in result['Groups']}
            yesterday_costs = {group['Keys'][0]: float(group['Metrics']['UnblendedCost']['Amount'])
                               for result in yesterday_response['ResultsByTime'] for group in result['Groups']}

            daily_comparison = [
                [service,
                 round(today_cost, 2),
                 round(yesterday_costs.get(service, 0.0), 2),
                 round(today_cost - yesterday_costs.get(service, 0.0), 2),
                 round(((today_cost - yesterday_costs.get(service, 0.0)) / yesterday_costs.get(service, 0.0) * 100) if yesterday_costs.get(service, 0.0) != 0 else 0, 2)]
                for service, today_cost in today_costs.items()
            ]

            daily_df = pd.DataFrame(daily_comparison, columns=['Service', 'Today Cost', 'Yesterday Cost', 'Cost Difference', 'Percentage Change (%)'])
            daily_df.to_excel(writer, sheet_name='Daily', index=False)

        # Weekly Comparison
        if choice in ['2', '4']:
            response = fetch_cost_data(last_14_days, today, 'DAILY')
            daily_costs = {}

            for result in response['ResultsByTime']:
                date = result['TimePeriod']['Start']
                for group in result['Groups']:
                    service = group['Keys'][0]
                    cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    if service not in daily_costs:
                        daily_costs[service] = {}
                    daily_costs[service][date] = cost

            week_1_start, week_1_end = last_14_days, last_14_days + datetime.timedelta(days=7)
            week_2_start, week_2_end = week_1_end, today

            weekly_costs = [{}, {}]
            for service, costs in daily_costs.items():
                weekly_costs[0][service] = sum(cost for date, cost in costs.items() if week_1_start.strftime('%Y-%m-%d') <= date < week_1_end.strftime('%Y-%m-%d'))
                weekly_costs[1][service] = sum(cost for date, cost in costs.items() if week_2_start.strftime('%Y-%m-%d') <= date < week_2_end.strftime('%Y-%m-%d'))

            weekly_comparison = [
                [service,
                 round(weekly_costs[1].get(service, 0.0), 2),
                 round(weekly_costs[0].get(service, 0.0), 2),
                 round(weekly_costs[1].get(service, 0.0) - weekly_costs[0].get(service, 0.0), 2),
                 round(((weekly_costs[1].get(service, 0.0) - weekly_costs[0].get(service, 0.0)) / weekly_costs[0].get(service, 0.0) * 100) if weekly_costs[0].get(service, 0.0) != 0 else 0, 2)]
                for service in set(weekly_costs[0].keys()).union(weekly_costs[1].keys())
            ]

            weekly_df = pd.DataFrame(weekly_comparison, columns=['Service', 'Current Week Cost', 'Previous Week Cost', 'Cost Difference', 'Percentage Change (%)'])
            weekly_df.to_excel(writer, sheet_name='Weekly', index=False)

        # Monthly Comparison
        if choice in ['3', '4']:
            current_month_response = fetch_cost_data(current_month_start, today, 'DAILY')
            previous_month_response = fetch_cost_data(previous_month_start, previous_month_end + datetime.timedelta(days=1), 'DAILY')

            current_month_costs = {}
            previous_month_costs = {}

            for result in current_month_response['ResultsByTime']:
                for group in result['Groups']:
                    service = group['Keys'][0]
                    current_month_costs[service] = current_month_costs.get(service, 0.0) + float(group['Metrics']['UnblendedCost']['Amount'])

            for result in previous_month_response['ResultsByTime']:
                for group in result['Groups']:
                    service = group['Keys'][0]
                    previous_month_costs[service] = previous_month_costs.get(service, 0.0) + float(group['Metrics']['UnblendedCost']['Amount'])

            monthly_comparison = [
                [service,
                 round(current_month_costs.get(service, 0.0), 2),
                 round(previous_month_costs.get(service, 0.0), 2),
                 round(current_month_costs.get(service, 0.0) - previous_month_costs.get(service, 0.0), 2),
                 round(((current_month_costs.get(service, 0.0) - previous_month_costs.get(service, 0.0)) / previous_month_costs.get(service, 0.0) * 100) if previous_month_costs.get(service, 0.0) != 0 else 0, 2)]
                for service in set(current_month_costs.keys()).union(previous_month_costs.keys())
            ]

            monthly_df = pd.DataFrame(monthly_comparison, columns=['Service', 'Current Month Cost', 'Previous Month Cost', 'Cost Difference', 'Percentage Change (%)'])
            monthly_df.to_excel(writer, sheet_name='Monthly', index=False)

    print(f"Cost comparison has been saved to {output_path}")

except boto3.exceptions.NoCredentialsError:
    print("AWS credentials not found. Please configure your AWS credentials and try again.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")

