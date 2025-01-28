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
        if not job_template['playbook'] in awx_collected_job_templates:
            awx_collected_job_templates[job_template['playbook']] = {}

        awx_collected_job_templates[job_template['playbook']]['name'] = job_template['name']
        awx_collected_job_templates[job_template['playbook']]['id'] = job_template['id']

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


def netbox_create_webhook(netbox_url, netbox_api_token, payload):
    created_webhook = NetboxWebhooks(netbox_url, netbox_api_token, payload)
    return dict(created_webhook.obj)['id'], dict(created_webhook.obj)['name']


def netbox_create_event_rule(netbox_url, netbox_api_token, payload):
    created_event_rule = NetboxEventRules(netbox_url, netbox_api_token, payload)
    return dict(created_event_rule.obj)['id'], dict(created_event_rule.obj)['name']


def main():
    netbox_webhook_payload = {}
    netbox_event_rule_payload = {}
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

    if not 'automation_type' in app_config:
        raise ValueError("app_config is missing definition for 'automation_type'")
    
    if app_config['automation_type'] not in ['flask_application', 'ansible_automation']:
        raise ValueError(f"Unknown automation_type in {app_config_file}: {app_config['automation_type']}")

    if not app_config['automation_type'] in app_config:
        raise ValueError(f"No known configuration for {app_config['automation_type']}")
    
    netbox_proxmox_event_rules = {
            'proxmox-clone-vm-and-set-resources': {
                'enabled': True,
                'action_type': 'webhook',
                'action_object_type': 'extras.webhook',
                'action_object_id': -1,
                'object_types': [
                    "virtualization.virtualmachine"
                ],
                'event_types': [
                    "object_created"
                ],
                'conditions': {
                    "and": [
                        {
                            "attr": "status.value",
                            "value": "staged"
                        },
                        {
                            "attr": "vcpus",
                            "negate": True,
                            "value": None
                        },
                        {
                            "attr": "memory",
                            "negate": True,
                            "value": None
                        },
                        {
                            "attr": "custom_fields.proxmox_vm_template",
                            "negate": True,
                            "value": None
                        }
                    ]
                }
            },
            'proxmox-remove-vm': {
                'enabled': True,
                'action_type': 'webhook',
                'action_object_type': 'extras.webhook',
                'action_object_id': -1,
                'object_types': [
                    "virtualization.virtualmachine"
                ],
                'event_types': [
                    "object_deleted"
                ],
                'conditions': ''
            },
            'proxmox-set-ipconfig0-and-ssh-key': {
                'enabled': True,
                'action_type': 'webhook',
                'action_object_type': 'extras.webhook',
                'action_object_id': -1,
                'object_types': [
                    "virtualization.virtualmachine"
                ],
                'event_types': [
                    "object_created",
                    "object_deleted",
                    "object_updated"
                ],
                'conditions': {
                    "and": [
                        {
                            "attr": "primary_ip4",
                            "negate": True,
                            "value": None
                        },
                        {
                            "attr": "status.value",
                            "value": "staged"
                        }
                    ]
                }
            },
            'proxmox-resize-vm-disk': {
                'enabled': True,
                'action_type': 'webhook',
                'action_object_type': 'extras.webhook',
                'action_object_id': -1,
                'object_types': [
                    "virtualization.virtualdisk"
                ],
                'event_types': [
                    "object_updated"
                ],
                'conditions': ''
            },
            'proxmox-add-vm-disk': {
                'enabled': True,
                'action_type': 'webhook',
                'action_object_type': 'extras.webhook',
                'action_object_id': -1,
                'object_types': [
                    "virtualization.virtualdisk"
                ],
                'event_types': [
                    "object_created"
                ],
                'conditions': ''
            },
            'proxmox-remove-vm-disk': {
                'enabled': True,
                'action_type': 'webhook',
                'action_object_type': 'extras.webhook',
                'action_object_id': -1,
                'object_types': [
                    "virtualization.virtualdisk"
                ],
                'event_types': [
                    "object_deleted"
                ],
                'conditions': {
                    "attr": "name",
                    "negate": True,
                    "value": "scsi0"
                }              
            },
            'proxmox-stop-vm': {
                'enabled': True,
                'action_type': 'webhook',
                'action_object_type': 'extras.webhook',
                'action_object_id': -1,
                'object_types': [
                    "virtualization.virtualmachine"
                ],
                'event_types': [
                    "object_updated"
                ],
                'conditions': {
                    "attr": "status.value",
                    "value": "offline"
                }
            },
            'proxmox-start-vm': {
                'enabled': True,
                'action_type': 'webhook',
                'action_object_type': 'extras.webhook',
                'action_object_id': -1,
                'object_types': [
                    "virtualization.virtualmachine"
                ],
                'event_types': [
                    "object_updated"
                ],
                'conditions': {
                    "attr": "status.value",
                    "value": "active"
                }
            },
#            'update-dns': {
#                'enabled': True,
#                'action_type': 'webhook',
#                'action_object_type': 'extras.webhook',
#                'action_object_id': -1,
#            }
    }

    if app_config['automation_type'] == 'flask_application':
        netbox_webhook_url = f"{app_config['flask_application']['http_proto']}://{app_config['flask_application']['host']}:{app_config['flask_application']['http_port']}/{app_config['flask_application']['netbox_webhook_name']}/"
        netbox_webhook_name = f"netbox-proxmox-{re.sub('_', '-', app_config['automation_type'])}"

        netbox_webhook_payload['ssl_verification'] = app_config['flask_application']['ssl_verify']
        netbox_webhook_payload['http_method'] = 'POST'
        netbox_webhook_payload['http_content_type'] = 'application/json'
        netbox_webhook_payload['name'] = netbox_webhook_name
        netbox_webhook_payload['payload_url'] = netbox_webhook_url
        netbox_webhook_payload['additional_headers'] = ''
        netbox_webhook_payload['body_template'] = ''

        netbox_webhook_id, netbox_webhook_name_returned = netbox_create_webhook(netbox_url, netbox_api_token, netbox_webhook_payload)

        if not netbox_webhook_id:
            raise ValueError(f"Unable to create webhook for {netbox_webhook_payload['name']}")
        
        for event_rule in netbox_proxmox_event_rules:
            netbox_event_rule_payload['name'] = f"NEW-{event_rule}-{re.sub(r'_', '-', app_config['automation_type'])}"
            netbox_event_rule_payload['enabled'] = netbox_proxmox_event_rules[event_rule]['enabled']
            netbox_event_rule_payload['object_types'] = netbox_proxmox_event_rules[event_rule]['object_types']
            netbox_event_rule_payload['event_types'] = netbox_proxmox_event_rules[event_rule]['event_types']
            netbox_event_rule_payload['action_type'] = netbox_proxmox_event_rules[event_rule]['action_type']
            netbox_event_rule_payload['action_object_type'] = netbox_proxmox_event_rules[event_rule]['action_object_type']
            netbox_event_rule_payload['action_object_id'] = netbox_webhook_id
            netbox_event_rule_payload['conditions'] = netbox_proxmox_event_rules[event_rule]['conditions']

            if not netbox_create_event_rule(netbox_url, netbox_api_token, netbox_event_rule_payload):
                raise ValueError(f"Unable to create event rule {netbox_event_rule_payload['name']}")
    elif app_config['automation_type'] == 'ansible_automation':
        awx_playbook_to_event_rule_mappings = {
            'awx-proxmox-add-vm-disk.yml': 'proxmox-add-vm-disk',
            'awx-proxmox-clone-vm-and-set-resources.yml': 'proxmox-clone-vm-and-set-resources',
            'awx-proxmox-remove-vm.yml': 'proxmox-remove-vm',
            'awx-proxmox-remove-vm-disk.yml': 'proxmox-remove-vm-disk',
            'awx-proxmox-resize-vm-disk.yml': 'proxmox-resize-vm-disk',
            'awx-proxmox-set-ipconfig0.yml': 'proxmox-set-ipconfig0-and-ssh-key',
            'awx-proxmox-start-vm.yml': 'proxmox-start-vm',
            'awx-proxmox-stop-vm.yml': 'proxmox-stop-vm',
            #'awx-update-dns.yml': 'update-dns'        
        }

        ansible_automation_webhook_body_templates = {
            'proxmox-clone-vm-and-set-resources': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['name'] }}\",\r\n      \"vcpus\": \"{{ data['vcpus'] }}\",\r\n      \"memory\": \"{{ data['memory'] }}\",\r\n      \"template\": \"{{ data['custom_fields']['proxmox_vm_template'] }}\",\r\n      \"storage\": \"{{ data['custom_fields']['proxmox_vm_storage'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-remove-vm': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['name'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-set-ipconfig0-and-ssh-key': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['name'] }}\",\r\n      \"ip\": \"{{ data['primary_ip4']['address'] }}\",\r\n      \"ssh_key\": \"{{ data['custom_fields']['proxmox_public_ssh_key'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-resize-vm-disk': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['virtual_machine']['name'] }}\",\r\n      \"resize_disk\": \"{{ data['name'] }}\",\r\n      \"resize_disk_size\": \"{{ data['size'] }}\",\r\n      \"storage_volume\": \"{{ data['custom_fields']['proxmox_storage_volume'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-add-vm-disk': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['virtual_machine']['name'] }}\",\r\n      \"add_disk\": \"{{ data['name'] }}\",\r\n      \"add_disk_size\": \"{{ data['size'] }}\",\r\n      \"storage_volume\": \"{{ data['custom_fields']['proxmox_storage_volume'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-remove-vm-disk': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['virtual_machine']['name'] }}\",\r\n      \"remove_disk\": \"{{ data['name'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-stop-vm': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['name'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-start-vm': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['name'] }}\"\r\n    }\r\n  }\r\n}",
            #'update-dns': "{\r\n  \"extra_vars\": {\r\n    \"dns_stuff\": {\r\n      \"dns_zone_id\": \"{{ data['zone']['id'] }}\",\r\n      \"dns_zone_name\": \"{{ data['zone']['name'] }}\",\r\n      \"dns_integrations\": \"{{ data['custom_fields']['dns_integrations'] }}\"\r\n    }\r\n  }\r\n}"
        }
        
        if not 'settings' in app_config['ansible_automation']:
            raise ValueError("Missing 'settings' section in 'ansible_automation'")

        if not 'project' in app_config['ansible_automation']['settings']:
            raise ValueError("Missing 'project' in ansible_automation 'settings'")
                
        awx_project_name = app_config['ansible_automation']['settings']['project']

        awx_url_v2_api = f"{app_config['ansible_automation']['http_proto']}://{app_config['ansible_automation']['host']}:{app_config['ansible_automation']['http_port']}/api/v2/"

        if not awx_url_v2_api.endswith('/'):
            awx_url_v2_api += '/'

        auth_in = setup_http_basic_auth(app_config['ansible_automation']['username'], app_config['ansible_automation']['password'])

        awx_project_id = awx_get_project_info(awx_url_v2_api, auth_in, app_config['ansible_automation']['ssl_verify'], awx_project_name)

        awx_job_templates = awx_get_job_templates_info(awx_url_v2_api, auth_in, app_config['ansible_automation']['ssl_verify'], awx_project_id)

        if not awx_job_templates:
            raise ValueError("Unable to find any matching AWX job templates")

        awx_job_templates = dict(sorted(awx_job_templates.items()))

        netbox_webhook_additional_headers = create_authorization_header(app_config['ansible_automation']['username'], app_config['ansible_automation']['password'])

        for awx_playbook_to_event_rule_mapping in awx_playbook_to_event_rule_mappings:
            if awx_playbook_to_event_rule_mapping in awx_job_templates:
                netbox_webhook_name = f"{awx_job_templates[awx_playbook_to_event_rule_mapping]['name']}-{re.sub(r'_', '-', app_config['automation_type'])}"
                netbox_webhook_url = f"{awx_url_v2_api}job_templates/{awx_job_templates[awx_playbook_to_event_rule_mapping]['id']}/launch/"

                netbox_webhook_payload['ssl_verification'] = app_config['ansible_automation']['ssl_verify']
                netbox_webhook_payload['http_method'] = 'POST'
                netbox_webhook_payload['http_content_type'] = 'application/json'
                netbox_webhook_payload['name'] = netbox_webhook_name
                netbox_webhook_payload['payload_url'] = netbox_webhook_url
                netbox_webhook_payload['additional_headers'] = netbox_webhook_additional_headers

                key_name = awx_playbook_to_event_rule_mappings[awx_playbook_to_event_rule_mapping]

                if key_name in ansible_automation_webhook_body_templates:
                    netbox_webhook_payload['body_template'] = ansible_automation_webhook_body_templates[key_name]
                else:
                    netbox_webhook_payload['body_template'] = ''
                    continue

                netbox_webhook_id, netbox_webhook_name_returned = netbox_create_webhook(netbox_url, netbox_api_token, netbox_webhook_payload)

                if not netbox_webhook_id:
                    raise ValueError(f"Unable to create webhook for {netbox_webhook_payload['name']}")

                collected_netbox_webhook_payload[key_name] = netbox_webhook_id

        for collected_netbox_webhook in collected_netbox_webhook_payload:
            if collected_netbox_webhook in netbox_proxmox_event_rules:
                netbox_event_rule_payload['name'] = f"{collected_netbox_webhook}-{re.sub(r'_', '-', app_config['automation_type'])}"
                netbox_event_rule_payload['enabled'] = netbox_proxmox_event_rules[collected_netbox_webhook]['enabled']
                netbox_event_rule_payload['object_types'] = netbox_proxmox_event_rules[collected_netbox_webhook]['object_types']
                netbox_event_rule_payload['event_types'] = netbox_proxmox_event_rules[collected_netbox_webhook]['event_types']
                netbox_event_rule_payload['action_type'] = netbox_proxmox_event_rules[collected_netbox_webhook]['action_type'].lower()
                netbox_event_rule_payload['action_object_type'] = netbox_proxmox_event_rules[collected_netbox_webhook]['action_object_type']
                netbox_event_rule_payload['action_object_id'] = collected_netbox_webhook_payload[collected_netbox_webhook]
                netbox_event_rule_payload['conditions'] = netbox_proxmox_event_rules[collected_netbox_webhook]['conditions']

                if not netbox_create_event_rule(netbox_url, netbox_api_token, netbox_event_rule_payload):
                    raise ValueError(f"Unable to create event rule {netbox_event_rule_payload['name']}")
    else:
        raise ValueError(f"Unknown automation type {app_config['automation_type']}")


if __name__ == "__main__":
    main()

    