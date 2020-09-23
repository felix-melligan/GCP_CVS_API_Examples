import os
import time
import requests
import json
import google.auth
import google.auth.transport.requests
from google.auth import jwt
from google.oauth2 import service_account
from google.oauth2 import id_token

# Set variables
service_account_json = {}
project_number = "012345678"
audience = 'https://cloudvolumesgcp-api.netapp.com'
server = 'https://cloudvolumesgcp-api.netapp.com'

# Small utility function to convert bytes to gibibytes


def convertToGiB(bytes):
    return round(bytes/1024/1024/1024, 1)

# Small utility function to convert gibibytes to bytes


def convertToBytes(gibibytes):
    return gibibytes*1024*1024*1024

# Use service account json file with correct permissions to authenticate and get headers


def get_headers(service_account_json):
    # Create credential object from private key
    svc_creds = service_account.Credentials.from_service_account_info(service_account_json)

    # Create jwt
    jwt_creds = jwt.Credentials.from_signing_credentials(
        svc_creds, audience=audience)

    # Issue request to get auth token
    request = google.auth.transport.requests.Request()
    jwt_creds.refresh(request)

    # Extract token
    id_token = jwt_creds.token

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + id_token.decode('utf-8')
    }

    return headers

# Get a list of volumes


def get_volumes_list(headers):
    # Get all volumes from all regions
    get_url = server + "/v2/projects/" + \
        str(project_number) + "/locations/-/Volumes"

    # Issue the request to the server
    print("Get request: {}".format(get_url))
    r = requests.get(get_url, headers=headers)

    # Load the json response into a dict
    r_dict = r.json()

    # Prepare vol list
    volumes = []

    # Add vols to list
    for vol in r_dict:
        volumes.append(vol)

    return volumes

# Compare volume capacity used vs allocated and return volumes that need to be expanded


def get_small_volumes(volumes_list):
    volumes_need_resizing_list = []

    for volume in volumes_list:
        if volume["usedBytes"] > volume["quotaInBytes"]:
            print("Resize volume:\n\tVolume name: {}\tCapacity Used: {}\tAllocated Capacity: {}\tPercentage Used: {}%".format(volume["name"], convertToGiB(volume["usedBytes"]), convertToGiB(volume["quotaInBytes"]), round(volume["usedBytes"]/volume["quotaInBytes"]*100, 2)))
            volumes_need_resizing_list.append(volume)

    return volumes_need_resizing_list

# Go through volume list and call API to increase volumes


def size_up_volumes(volumes_need_resizing_list, headers):
    successful_responses = []
    
    for volume in volumes_need_resizing_list:
        response = edit_volume_size(volume, headers)
        time.sleep(10)
        if response.ok:
            successful_responses.append(response)
        else:
            print(response)

    print("Volumes Resized successfully: {}".format(len(successful_responses)))
            

# Resize Volume up to nearest gibibyte


def edit_volume_size(volume, headers):
    post_headers = {
        'Content-Type': "application/json",
        'Authorization': headers["Authorization"],
        'cache-control': "no-cache",
    }

    volumeURL = server + "/v2/projects/" + str(project_number) + "/locations/" + volume["region"] + "/Volumes/" + volume["volumeId"]

    new_capacity = round(convertToBytes(convertToGiB(volume["usedBytes"])))

    payload = json.dumps({"quotaInBytes": new_capacity})

    print("POST Request: {}".format(volumeURL))

    response = requests.request("PUT", volumeURL, data=payload, headers=post_headers)

    return response

# Main method


def main():
    print("---Script Start---")
    headers = get_headers(service_account_json)
    volumes = get_volumes_list(headers)
    volumes_need_resizing = get_small_volumes(volumes)
    print("Volumes that need resizing: {}".format(len(volumes_need_resizing)))
    if len(volumes_need_resizing) != 0:
        size_up_volumes(volumes_need_resizing, headers)
    print("---Script End---")


main()
