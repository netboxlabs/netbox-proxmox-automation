#!/usr/bin/env python3

import os, sys, re
import argparse
import yaml
import base64
import requests

from requests.auth import HTTPBasicAuth

# adapted from sol1 implementation
from helpers.netbox_objects import NetboxWebhooks, NetboxEventRules

from helpers.netbox_proxmox_api import NetBoxProxmoxAPIHelper


def create_authorization_header(username = None, password = None):
    awx_api_login_str = f"{username}:{password}"
    awx_api_login_str_auth = base64.b64encode(awx_api_login_str.encode('utf-8')).decode('utf-8')
    
    return f"Authorization: Basic {awx_api_login_str_auth}"


def setup_http_basic_auth(username = None, password = None):
    return HTTPBasicAuth(username, password)


def do_awx_rest_api(awx_url = None, uri_in = None, auth_in = None, ssl_verify=True):
    if uri_in.startswith('/'):
        uri_in = re.sub(r'^\/', '', uri_in)

    if not uri_in.endswith('/'):
        uri_in += '/'

    full_url = f"{awx_url}{uri_in}"

    response = requests.get(full_url, headers = {'Content-Type': 'application/json'}, auth=auth_in, verify=ssl_verify)

    if response.status_code == 200:
        return response.json()['results']
    
    return None


def awx_get_project_info(base_url=None, auth_in = None, ssl_verify = None, awx_project_name = None):
    results = do_awx_rest_api(base_url, 'projects', auth_in, ssl_verify)

    if not results:
        raise ValueError("Missing results for projects")

    filtered_data = [item for item in results if item['summary_fields']['last_update']['name'] == awx_project_name]

    if len(filtered_data) != 1:
        raise ValueError(f"Unable to find results for AWX project ({awx_project_name})")
    
    return filtered_data[0]['id']


def awx_get_job_templates_info(base_url=None, auth_in = None, ssl_verify = None, awx_project_id=0):
    awx_collected_job_templates = {}

    results = do_awx_rest_api(base_url, 'job_templates', auth_in, ssl_verify)

    if not results:
        raise ValueError("Missing results for job_templates")
    
    filtered_data = [item for item in results if item['summary_fields']['project']['id'] == awx_project_id]

    if not len(filtered_data):
        raise ValueError(f"Unable to find results for AWX project ID ({awx_project_id})")

    for job_template in filtered_data:
        awx_collected_job_templates[job_template['id']] = job_template['name']

    return awx_collected_job_templates


def get_arguments():
    # Initialize the parser
    parser = argparse.ArgumentParser(description="Import Netbox and Proxmox Configurations")

    # Add arguments for URL and Token
    parser.add_argument("--config", required=True, help="YAML file containing the configuration")

    # Parse the arguments
    args = parser.parse_args()

    # Return the parsed arguments
    return args


def __netbox_make_slug(in_str):
    return re.sub(r'\W+', '-', in_str).lower()


def netbox_create_webhook(netbox_url, netbox_api_token, payload):
    created_webhook = NetboxWebhooks(netbox_url, netbox_api_token, payload)
    print(created_webhook, created_webhook.obj)
    return dict(created_webhook.obj)['id'], dict(created_webhook.obj)['name']


def main():
    netbox_webhook_payload = {}
    collected_netbox_webhook_payload = {}

    args = get_arguments()

    app_config_file = args.config

    with open(app_config_file) as yaml_cfg:
        try:
            app_config = yaml.safe_load(yaml_cfg)
        except yaml.YAMLError as exc:
            raise ValueError(exc)
        except IOError as ioe:
            raise ValueError(ioe)

    netbox_url = f"{app_config['netbox_api_config']['api_proto']}://{app_config['netbox_api_config']['api_host']}:{app_config['netbox_api_config']['api_port']}/"
    netbox_api_token = f"{app_config['netbox_api_config']['api_token']}"

    if app_config['automation_type'] not in ['flask', 'ansible_automation']:
        raise ValueError(f"Unknown automation_type in {app_config_file}: {app_config['automation_type']}")

    if not app_config['automation_type'] in app_config:
        raise ValueError(f"No known configuration for {app_config['automation_type']}")

    print(app_config, netbox_url, netbox_api_token)

    # init NetBox Proxmox API integration
    p = NetBoxProxmoxAPIHelper(app_config)

    if app_config['automation_type'] == 'ansible_automation':
        awx_project_name = app_config['ansible_automation']['project_name']

        awx_url_v2_api = f"{app_config['ansible_automation']['http_proto']}://{app_config['ansible_automation']['host']}:{app_config['ansible_automation']['http_port']}/api/v2/"

        if not awx_url_v2_api.endswith('/'):
            awx_url_v2_api += '/'

        print(awx_url_v2_api)

        auth_in = setup_http_basic_auth(app_config['ansible_automation']['username'], app_config['ansible_automation']['password'])

        awx_project_id = awx_get_project_info(awx_url_v2_api, auth_in, app_config['ansible_automation']['ssl_verify'], awx_project_name)

        print(awx_project_id)

        awx_job_templates = awx_get_job_templates_info(awx_url_v2_api, auth_in, app_config['ansible_automation']['ssl_verify'], awx_project_id)

        if not awx_job_templates:
            raise ValueError("Unable to find any matching AWX job templates")

        awx_job_templates = dict(sorted(awx_job_templates.items()))

        netbox_webhook_additional_headers = create_authorization_header(app_config['ansible_automation']['username'], app_config['ansible_automation']['password'])

        for awx_job_template in awx_job_templates:
            print(awx_job_template, awx_job_templates[awx_job_template])
            netbox_webhook_name = f"{awx_job_templates[awx_job_template]}-{re.sub(r'_', '-', app_config['automation_type'])}"
            netbox_webhook_url = f"{awx_url_v2_api}job_templates/{awx_job_template}/launch/"

            print(f"{awx_job_templates[awx_job_template]} -> {netbox_webhook_url} {netbox_webhook_name}")
            netbox_webhook_payload['ssl_verification'] = app_config['ansible_automation']['ssl_verify']
            netbox_webhook_payload['http_method'] = 'POST'
            netbox_webhook_payload['http_content_type'] = 'application/json'
            netbox_webhook_payload['name'] = netbox_webhook_name
            netbox_webhook_payload['payload_url'] = netbox_webhook_url
            netbox_webhook_payload['additional_headers'] = netbox_webhook_additional_headers

            print(netbox_webhook_payload)

            netbox_webhook_id, netbox_webhook_name_returned = netbox_create_webhook(netbox_url, netbox_api_token, netbox_webhook_payload)
            collected_netbox_webhook_payload[netbox_webhook_id] = netbox_webhook_name_returned

        print(collected_netbox_webhook_payload)


if __name__ == "__main__":
    main()

    