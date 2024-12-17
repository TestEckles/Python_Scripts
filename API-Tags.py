# Summary:
# This script retrieves all API Gateways (REST APIs) and their associated tags in the AWS account configured for a specific profile.
# It dynamically collects all unique tag keys and consolidates the API details and tags into a CSV file.
# The output includes API ID, name, description, creation date, resource ARN, and tag values.
# The final CSV file is saved to a specified path in the user's Downloads folder.

import boto3
import os
import csv

# Create a session using the specific profile
session = boto3.Session(profile_name='34258018649')

def list_api_gateways_with_tags():
    client = session.client('apigateway')
    tagging_client = session.client('resourcegroupstaggingapi')
    api_gateways = []
    all_tags_keys = set()  # Store all unique tag keys
    
    try:
        # Fetch the list of all REST APIs (API Gateway resources)
        paginator = client.get_paginator('get_rest_apis')
        for page in paginator.paginate():
            for api in page['items']:
                resource_arn = f"arn:aws:apigateway:{session.region_name}::/restapis/{api['id']}"
                
                # Fetch tags for the API Gateway
                tags_response = tagging_client.get_resources(
                    ResourceARNList=[resource_arn]
                )
                
                tags = {}
                if tags_response['ResourceTagMappingList']:
                    for tag in tags_response['ResourceTagMappingList'][0].get('Tags', []):
                        tags[tag['Key']] = tag['Value']
                        all_tags_keys.add(tag['Key'])  # Keep track of all tag keys
                
                # Store API Gateway details along with tags
                api_gateways.append({
                    'id': api['id'],
                    'name': api.get('name', 'Unnamed API'),
                    'description': api.get('description', 'No description available'),
                    'created_date': api['createdDate'].strftime('%Y-%m-%d'),
                    'resource_arn': resource_arn,
                    'tags': tags  # Add current tags as a dictionary
                })
    except Exception as e:
        print(f"Error fetching API Gateway data: {e}")
    
    return api_gateways, all_tags_keys

def save_to_csv(api_gateways, all_tags_keys, file_path):
    # Define the base fieldnames (API Gateway details)
    fieldnames = ['id', 'name', 'description', 'created_date', 'resource_arn']
    
    # Add the dynamic tag keys as additional columns
    fieldnames.extend(sorted(all_tags_keys))  # Sort for consistency

    # Save the list of API Gateways to a CSV file
    with open(file_path, mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        
        for api_gateway in api_gateways:
            row = {
                'id': api_gateway['id'],
                'name': api_gateway['name'],
                'description': api_gateway['description'],
                'created_date': api_gateway['created_date'],
                'resource_arn': api_gateway['resource_arn'],
            }
            
            # Add tag values to the row
            for tag_key in all_tags_keys:
                row[tag_key] = api_gateway['tags'].get(tag_key, 'None')  # Fill with 'None' if tag is missing
            
            writer.writerow(row)

if __name__ == '__main__':
    # List all API Gateways in the account with their tags
    api_gateways, all_tags_keys = list_api_gateways_with_tags()
    
    # Save CSV to the specific Downloads folder
    downloads_path = '/Users/saraeck/Downloads/api_gateways_with_tags.csv'  # Your actual Downloads path
    
    # Save the list to CSV
    save_to_csv(api_gateways, all_tags_keys, downloads_path)
    
    print(f"API Gateways and their tags saved to {downloads_path}")

