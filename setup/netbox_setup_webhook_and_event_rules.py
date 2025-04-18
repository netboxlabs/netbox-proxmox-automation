#!/usr/bin/env python3

import os, sys, re
import argparse
import yaml
import base64

# adapted from sol1 implementation
from helpers.netbox_objects import NetboxWebhooks, NetboxEventRules

# awxkit wrapper
from helpers.ansible_automation_awx_manager import AnsibleAutomationAWXManager


def get_arguments():
    # Initialize the parser
    parser = argparse.ArgumentParser(description="Import Netbox and Proxmox Configurations")

    # Add arguments for URL and Token
    parser.add_argument("--config", required=True, help="YAML file containing the configuration")

    # Parse the arguments
    args = parser.parse_args()

    # Return the parsed arguments
    return args


def create_authorization_header(username = None, password = None):
    awx_api_login_str = f"{username}:{password}"
    awx_api_login_str_auth = base64.b64encode(awx_api_login_str.encode('utf-8')).decode('utf-8')
    
    return f"Authorization: Basic {awx_api_login_str_auth}"


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
                        "attr": "custom_fields.proxmox_vm_type",
                        "value": "vm"
                    },
                    {
                        "attr": "custom_fields.proxmox_vm_templates",
                        "negate": True,
                        "value": None
                    }
                ]
            }
        },
        'proxmox-vm-set-resources': {
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
                        "attr": "custom_fields.proxmox_vm_type",
                        "value": "vm"
                    },
                    {
                        "attr": "custom_fields.proxmox_vm_templates",
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
            'conditions': {
                "attr": "custom_fields.proxmox_vm_type",
                "value": "vm"
            }
        },
        'proxmox-set-ipconfig0': {
            'enabled': True,
            'action_type': 'webhook',
            'action_object_type': 'extras.webhook',
            'action_object_id': -1,
            'object_types': [
                "virtualization.virtualmachine"
            ],
            'event_types': [
                "object_created",
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
                    },
                    {
                        "attr": "custom_fields.proxmox_vm_type",
                        "value": "vm"
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
            'conditions': {
                "attr": "name",
                "negate": True,
                "value": "rootfs"                
            }
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
            'conditions': {
                "and": [
                    {
                        "attr": "name",
                        "value": "scsi0",
                        "negate": True
                    },
                    {
                        "attr": "name",
                        "value": "rootfs",
                        "negate": True
                    }
                    ]                          
            }
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
                "and": [
                    {
                        "attr": "status.value",
                        "value": "offline"
                    },
                    {
                        "attr": "custom_fields.proxmox_vm_type",
                        "value": "vm"
                    }
                ]
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
                "and": [
                    {
                        "attr": "status.value",
                        "value": "active"
                    },
                    {
                        "attr": "custom_fields.proxmox_vm_type",
                        "value": "vm"
                    }
                ]
            }
        },
        'proxmox-clone-lxc-and-set-resources': {
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
                        "attr": "custom_fields.proxmox_vm_type",
                        "value": "lxc"
                    },
                    {
                        "attr": "custom_fields.proxmox_lxc_templates",
                        "negate": True,
                        "value": None
                    },
                    {
                        "attr": "custom_fields.proxmox_public_ssh_key",
                        "negate": True,
                        "value": None
                    }
                ]
            }
        },
        'proxmox-lxc-set-resources': {
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
                        "attr": "custom_fields.proxmox_vm_type",
                        "value": "lxc"
                    },
                    {
                        "attr": "custom_fields.proxmox_lxc_templates",
                        "negate": True,
                        "value": None
                    },
                    {
                        "attr": "custom_fields.proxmox_public_ssh_key",
                        "negate": True,
                        "value": None
                    }
                ]
            }
        },
        'proxmox-set-netif': {
            'enabled': True,
            'action_type': 'webhook',
            'action_object_type': 'extras.webhook',
            'action_object_id': -1,
            'object_types': [
                "virtualization.virtualmachine"
            ],
            'event_types': [
                "object_created",
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
                    },
                    {
                        "attr": "custom_fields.proxmox_vm_type",
                        "value": "lxc"
                    }
                ]
            }
        },
        'proxmox-resize-lxc-disk': {
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
            'conditions': {
                "attr": "name",
                "value": "rootfs"                
            }
        },
        'proxmox-remove-lxc': {
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
            'conditions': {
                "attr": "custom_fields.proxmox_vm_type",
                "value": "lxc"
            }
        },
        'proxmox-stop-lxc': {
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
                "and": [
                    {
                        "attr": "status.value",
                        "value": "offline"
                    },
                    {
                        "attr": "custom_fields.proxmox_vm_type",
                        "value": "lxc"
                    }
                ]
            }
        },
        'proxmox-start-lxc': {
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
                "and": [
                    {
                        "attr": "status.value",
                        "value": "active"
                    },
                    {
                        "attr": "custom_fields.proxmox_vm_type",
                        "value": "lxc"
                    }
                ]
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
            netbox_event_rule_payload['name'] = f"{event_rule}-{re.sub(r'_', '-', app_config['automation_type'])}"
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
        ansible_automation_webhook_body_templates = {
            # add this: "vmid": "{{ data['custom_fields']['proxmox_vmid'] }}",
            'proxmox-clone-vm-and-set-resources': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['name'] }}\",\r\n      \"vcpus\": \"{{ data['vcpus'] }}\",\r\n      \"memory\": \"{{ data['memory'] }}\",\r\n      \"vmid\": \"{{ data['custom_fields']['proxmox_vmid'] }}\",\r\n      \"template\": \"{{ data['custom_fields']['proxmox_vm_templates'] }}\",\r\n      \"storage\": \"{{ data['custom_fields']['proxmox_vm_storage'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-remove-vm': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['name'] }}\",\r\n      \"vmid\": \"{{ data['custom_fields']['proxmox_vmid'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-set-ipconfig0': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['name'] }}\",\r\n      \"ip\": \"{{ data['primary_ip4']['address'] }}\",\r\n      \"ssh_key\": \"{{ data['custom_fields']['proxmox_public_ssh_key'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-resize-vm-disk': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['virtual_machine']['name'] }}\",\r\n      \"resize_disk\": \"{{ data['name'] }}\",\r\n      \"resize_disk_size\": \"{{ data['size'] }}\",\r\n      \"storage_volume\": \"{{ data['custom_fields']['proxmox_storage_volume'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-add-vm-disk': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['virtual_machine']['name'] }}\",\r\n      \"add_disk\": \"{{ data['name'] }}\",\r\n      \"add_disk_size\": \"{{ data['size'] }}\",\r\n      \"storage_volume\": \"{{ data['custom_fields']['proxmox_storage_volume'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-remove-vm-disk': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['virtual_machine']['name'] }}\",\r\n      \"remove_disk\": \"{{ data['name'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-stop-vm': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['name'] }}\",\r\n      \"vmid\": \"{{ data['custom_fields']['proxmox_vmid'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-start-vm': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['name'] }}\",\r\n      \"vmid\": \"{{ data['custom_fields']['proxmox_vmid'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-clone-lxc-and-set-resources': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"hostname\": \"{{ data['name'] }}\",\r\n      \"cpus\": \"{{ data['vcpus'] }}\",\r\n      \"memory\": \"{{ data['memory'] }}\",\r\n      \"vmid\": \"{{ data['custom_fields']['proxmox_vmid'] }}\",\r\n      \"template\": \"{{ data['custom_fields']['proxmox_lxc_templates'] }}\",\r\n      \"storage\": \"{{ data['custom_fields']['proxmox_vm_storage'] }}\",\r\n      \"pubkey\": \"{{ data['custom_fields']['proxmox_public_ssh_key'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-remove-lxc': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"hostname\": \"{{ data['name'] }}\",\r\n      \"vmid\": \"{{ data['custom_fields']['proxmox_vmid'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-start-lxc': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"hostname\": \"{{ data['name'] }}\",\r\n      \"vmid\": \"{{ data['custom_fields']['proxmox_vmid'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-stop-lxc': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"hostname\": \"{{ data['name'] }}\",\r\n      \"vmid\": \"{{ data['custom_fields']['proxmox_vmid'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-set-netif': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"hostname\": \"{{ data['name'] }}\",\r\n      \"ip\": \"{{ data['primary_ip4']['address'] }}\"\r\n    }\r\n  }\r\n}",
            'proxmox-resize-lxc-disk': "{\r\n  \"extra_vars\": {\r\n    \"vm_config\": {\r\n      \"name\": \"{{ data['virtual_machine']['name'] }}\",\r\n      \"resize_disk\": \"{{ data['name'] }}\",\r\n      \"resize_disk_size\": \"{{ data['size'] }}\",\r\n      \"storage_volume\": \"{{ data['custom_fields']['proxmox_storage_volume'] }}\"\r\n    }\r\n  }\r\n}"
            #'update-dns': "{\r\n  \"extra_vars\": {\r\n    \"dns_stuff\": {\r\n      \"dns_zone_id\": \"{{ data['zone']['id'] }}\",\r\n      \"dns_zone_name\": \"{{ data['zone']['name'] }}\",\r\n      \"dns_integrations\": \"{{ data['custom_fields']['dns_integrations'] }}\"\r\n    }\r\n  }\r\n}"
        }
        
        if not 'settings' in app_config['ansible_automation']:
            raise ValueError("Missing 'settings' section in 'ansible_automation'")

        if not 'project' in app_config['ansible_automation']['settings']:
            raise ValueError("Missing 'project' in ansible_automation 'settings'")
        
        if not 'name' in app_config['ansible_automation']['settings']['project']:
            raise ValueError("Missing 'name' of project in ansible_automation 'settings'")
                
        awx_project_name = app_config['ansible_automation']['settings']['project']['name']

        aam = AnsibleAutomationAWXManager(app_config)

        aam.get_project(awx_project_name)
        project_playbooks = aam.get_playbooks()

        if not project_playbooks:
            print(f"No playbooks found for project {awx_project_name}")
            sys.exit(1)

        aam.get_job_templates_for_project()

        if not hasattr(aam, 'job_templates'):
            print(f"No job templates found for {awx_project_name}")
            sys.exit(1)

        awx_url = f"{app_config['ansible_automation']['http_proto']}://{app_config['ansible_automation']['host']}:{app_config['ansible_automation']['http_port']}"

        netbox_webhook_additional_headers = create_authorization_header(app_config['ansible_automation']['username'], app_config['ansible_automation']['password'])

        for job_template in aam.job_templates:
            netbox_webhook_name = f"{job_template['name']}-{re.sub(r'_', '-', app_config['automation_type'])}"
            netbox_webhook_url = f"{awx_url}{job_template['related']['launch']}"

            netbox_webhook_payload['ssl_verification'] = app_config['ansible_automation']['ssl_verify']
            netbox_webhook_payload['http_method'] = 'POST'
            netbox_webhook_payload['http_content_type'] = 'application/json'
            netbox_webhook_payload['name'] = netbox_webhook_name
            netbox_webhook_payload['payload_url'] = netbox_webhook_url
            netbox_webhook_payload['additional_headers'] = netbox_webhook_additional_headers

            if job_template['name'] in ansible_automation_webhook_body_templates:
                netbox_webhook_payload['body_template'] = ansible_automation_webhook_body_templates[job_template['name']]
            else:
                netbox_webhook_payload['body_template'] = ''
                continue

            netbox_webhook_id, netbox_webhook_name_returned = netbox_create_webhook(netbox_url, netbox_api_token, netbox_webhook_payload)

            if not netbox_webhook_id:
                raise ValueError(f"Unable to create webhook for {netbox_webhook_payload['name']}")

            collected_netbox_webhook_payload[job_template['name']] = netbox_webhook_id

        for collected_netbox_webhook in collected_netbox_webhook_payload:
            if not collected_netbox_webhook in netbox_proxmox_event_rules:
                print(f"Unable to find {collected_netbox_webhook} mapping in netbox_proxmox_event_rules")
                sys.exit(1)

            netbox_event_rule_payload['name'] = f"{collected_netbox_webhook}-{re.sub(r'_', '-', app_config['automation_type'])}"
            netbox_event_rule_payload['enabled'] = netbox_proxmox_event_rules[collected_netbox_webhook]['enabled']
            netbox_event_rule_payload['object_types'] = netbox_proxmox_event_rules[collected_netbox_webhook]['object_types']
            netbox_event_rule_payload['event_types'] = netbox_proxmox_event_rules[collected_netbox_webhook]['event_types']
            netbox_event_rule_payload['action_type'] = netbox_proxmox_event_rules[collected_netbox_webhook]['action_type'].lower()
            netbox_event_rule_payload['action_object_type'] = netbox_proxmox_event_rules[collected_netbox_webhook]['action_object_type']
            netbox_event_rule_payload['action_object_id'] = collected_netbox_webhook_payload[collected_netbox_webhook]
            netbox_event_rule_payload['conditions'] = netbox_proxmox_event_rules[collected_netbox_webhook]['conditions']

            if not netbox_create_event_rule(netbox_url, netbox_api_token, netbox_event_rule_payload):
                print(f"Unable to create event rule {netbox_event_rule_payload['name']}")
                sys.exit(1)
    else:
        print(f"Unknown automation type {app_config['automation_type']}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()

    