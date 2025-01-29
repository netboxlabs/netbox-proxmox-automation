#!/usr/bin/env python3

import os, sys, re
import argparse
import time
import yaml

from helpers.ansible_automation import AnsibleAutomation


def get_arguments():
    # Initialize the parser
    parser = argparse.ArgumentParser(description="Import Netbox and Proxmox Configurations")

    # Add arguments for URL and Token
    parser.add_argument("--config", required=True, help="YAML file containing the configuration")

    # Parse the arguments
    args = parser.parse_args()

    # Return the parsed arguments
    return args


def create_aa_organization(aa_obj = None, org_name = None):
    org_payload = {
        'name': org_name
    }

    return aa_obj.create_object('organizations', org_name, org_payload)


def create_aa_inventory(aa_obj = None, inventory_name = None, org_id = 0):
    inventory_payload = {
        'name': inventory_name,
        'organization': org_id
    }

    return aa_obj.create_object('inventory', inventory_name, inventory_payload)


def create_aa_execution_environment(aa_obj = None, ee_name = None, ee_image_name = None, ee_reg_cred_id = 0, org_id = 0):
    ee_payload = {
        'name': ee_name,
        'image': ee_image_name,
        'organization': org_id
    }

    if ee_reg_cred_id:
        ee_payload['credential'] = ee_reg_cred_id

    return aa_obj.create_object('execution_environments', ee_name, ee_payload)


def create_aa_project(aa_obj = None, project_name = None, scm_type = None, scm_url = None, scm_branch = None, org_id = 0, ee_id = 0):
    project_payload = {
        'name': project_name,
        'organization': org_id,
        'scm_type': scm_type,
        'scm_url': scm_url,
        'scm_branch': scm_branch,
        'default_environment': ee_id
    }

    created_project = aa_obj.create_object('projects', project_name, project_payload)

    # Wait for project completion to complete, pausing 0.25s per iteration
    while True:
        proj_status = aa_obj.get_object_by_name('projects', project_name)

        if proj_status['status'] == 'successful':
            break

        if proj_status['status'] == 'failed':
            print("failed to sync project playbooks")
            sys.exit(0)

        time.sleep(0.25)

    return created_project


def create_aa_credential_type(aa_obj = None, credential_type_name = None):
    ct_payload = {
        'name': credential_type_name,
        'kind': "cloud",
        'inputs': {
            'fields': [
                {'id': "proxmox_api_host", 'type': "string", 'label': "Proxmox API Host"},
                {'id': "proxmox_api_user", 'type': "string", 'label': "Proxmox API User"},
                {'id': "proxmox_api_user_token", 'type': "string", 'label': "Proxmox API Token ID"},
                {'id': "proxmox_node", 'type': "string", 'label': "Proxmox Node"},
                {'id': "proxmox_api_token_secret", 'type': "string", 'label': "Proxmox API Token", 'secret': True},
                {'id': "netbox_api_proto", 'type': "string", 'label': "NetBox HTTP Protocol"},
                {'id': "netbox_api_host", 'type': "string", 'label': "NetBox API host"},
                {'id': "netbox_api_port", 'type': "string", 'label': "NetBox API port"},
                {'id': "netbox_api_token", 'type': "string", 'label': "NetBox API token", 'secret': True}
            ],
            'required': ['proxmox_api_host',
                         'proxmox_api_user',
                         'proxmox_api_user_token',
                         'proxmox_node',
                         'proxmox_api_token_secret',
                         'netbox_api_host',
                         'netbox_api_port',
                         'netbox_api_proto',
                         'netbox_api_token'
            ]
        },
        'injectors': {
            'extra_vars': {
                "netbox_env_info": {
                    "api_host": '{{ netbox_api_host }}',
                    "api_port": '{{ netbox_api_port }}',
                    "api_proto": '{{ netbox_api_proto }}',
                    "api_token": '{{ netbox_api_token }}'
                },
                "proxmox_env_info": {
                    "node": '{{ proxmox_node }}',
                    "api_host": '{{ proxmox_api_host }}',
                    "api_user": '{{ proxmox_api_user }}',
                    "api_token_id": '{{ proxmox_api_user_token }}',
                    "api_token_secret": '{{ proxmox_api_token_secret }}'
                }
            }
        }
    }

    return aa_obj.create_object('credential_types', credential_type_name, ct_payload)


def create_aa_credential(aa_obj = None, credential_name = None, credential_type_id = 0, org_id = 0, netbox_api_config = {}, proxmox_api_config = {}):
    credential_payload = {
        'name': credential_name,
        'credential_type': credential_type_id,
        'organization': org_id,
        'inputs': {
            'netbox_api_host': netbox_api_config['api_host'],
            'netbox_api_port': str(netbox_api_config['api_port']),
            'netbox_api_proto': netbox_api_config['api_proto'],
            'netbox_api_token': netbox_api_config['api_token'],
            'proxmox_node': proxmox_api_config['node'],
            'proxmox_api_host': proxmox_api_config['api_host'],
            'proxmox_api_user': proxmox_api_config['api_user'],
            'proxmox_api_user_token': proxmox_api_config['api_token_id'],
            'proxmox_api_token_secret': proxmox_api_config['api_token_secret']
        }
    }

    return aa_obj.create_object('credentials', credential_name, credential_payload)


def get_aa_playbooks(aa_obj = None, project_id = 0):
    aa_playbooks = []

    for playbook_item in aa_obj.get_object_by_id('projects', project_id).get_related('playbooks'):
        if playbook_item.endswith('.yml') or playbook_item.endswith('.yaml'):
            if not re.search(r'/', playbook_item):
                aa_playbooks.append(playbook_item)

    return aa_playbooks


def create_aa_job_template(aa_obj = None, playbook_name = None, inventory_id = 0, org_id = 0, ee_id = 0, project_id = 0):
    job_template_name = re.sub(r'^awx\-', 'XX', playbook_name.split('.')[0])

    job_template_payload = {
        'name': job_template_name,
        'job_type': 'run',
        'inventory': inventory_id,
        'organization': org_id,
        'project': project_id,
        'execution_environment': ee_id,
        'playbook': playbook_name,
        'ask_variables_on_launch': True,
        'ask_credential_on_launch': True
    }

    return aa_obj.create_object('job_templates', job_template_name, job_template_payload)
    

def create_aa_job_template_credential(aa_obj = None, template_id = 0, cred_name = None):
    the_cred = aa_obj.get_object_by_name('credentials', cred_name)

    if not the_cred:
        raise ValueError(f"Unable to get credentials object for {cred_name}")
        
    jt_entry = aa_obj.get_object_by_id('job_templates', template_id)

    if not jt_entry:
        raise ValueError(f"Unable to find job_templates {template_id}")

    if not jt_entry['summary_fields']['credentials']:
        try:
            jt_entry.add_credential(the_cred)
        except:
            return False
        
    return True


def main():
    args = get_arguments()
    app_config_file = args.config

    default_organization = 'Default'
    default_inventory = 'Default Inventory'

    default_execution_environment = 'netbox-proxmox-exec-env'
    default_execution_environment_image = 'localhost:5000/awx/ee/exec-env-test1:1.0.0'
    default_execution_environment_pull = 'Missing'

    default_project = 'netbox-proxmox-ee-test1'
    default_scm_type = 'git'
    default_scm_url = 'https://github.com/netboxlabs/netbox-proxmox-automation.git'
    default_scm_branch = 'main'

    credential_type = 'NetBox Proxmox Credential Type'
    credential_name = 'NetBox Proxmox Credentials Configuration'

    with open(app_config_file) as yaml_cfg:
        try:
            app_config = yaml.safe_load(yaml_cfg)
        except yaml.YAMLError as exc:
            raise ValueError(exc)
        except IOError as ioe:
            raise ValueError(ioe)

    if not 'ansible_automation' in app_config:
        raise ValueError(f"Missing 'ansible_automation' section in {app_config_file}")
    
    if not 'settings' in app_config['ansible_automation']:
        raise ValueError(f"Missing 'settings' in 'ansible_automation' section of {app_config_file}")

    aa = AnsibleAutomation(app_config['ansible_automation'])

    org_name = default_organization    
    if 'organization' in app_config['ansible_automation']['settings']:
        org_name = app_config['ansible_automation']['settings']['organization']

    created_organization = create_aa_organization(aa, org_name)

    if not created_organization:
        print(f"Unable to create organization {org_name}")
        sys.exit(1)

    org_id = created_organization['id']

    inventory_name = default_inventory
    if 'inventory' in app_config['ansible_automation']['settings']:
        inventory_name = app_config['ansible_automation']['settings']['inventory']

    created_inventory = create_aa_inventory(aa, inventory_name, org_id)

    if not created_inventory:
        print(f"Unable to create inventory {inventory_name}")
        sys.exit(1)

    inventory_id = created_inventory['id']

    ee_name = default_execution_environment
    ee_image_name = default_execution_environment_image

    if 'execution_environment' in app_config['ansible_automation']['settings']:
        if 'name' in app_config['ansible_automation']['settings']['execution_environment']:
            ee_name = app_config['ansible_automation']['settings']['execution_environment']['name']

        if 'image' in app_config['ansible_automation']['settings']['execution_environment']:
            ee_image_name = app_config['ansible_automation']['settings']['execution_environment']['image']

    created_ee = create_aa_execution_environment(aa, ee_name, ee_image_name, 0, org_id)
    created_ee_id = created_ee['id']

    if not created_ee:
        print(f"Unable to create execution environment {ee_name}")
        sys.exit(1)

    project_name = default_project
    if 'project' in app_config['ansible_automation']['settings']:
        project_name = app_config['ansible_automation']['settings']['project']

    scm_type = default_scm_type
    if 'scm_type' in app_config['ansible_automation']['settings']:
        scm_type = app_config['ansible_automation']['settings']['scm_type']

    scm_url = default_scm_url
    if 'scm_url' in app_config['ansible_automation']['settings']:
        scm_url = app_config['ansible_automation']['settings']['scm_url']

    scm_branch = default_scm_branch
    if 'scm_branch' in app_config['ansible_automation']['settings']:
        scm_branch = app_config['ansible_automation']['settings']['scm_branch']

    created_project = create_aa_project(aa, project_name, scm_type, scm_url, scm_branch, org_id, created_ee_id)

    if not created_project:
        print(f"Unable to create project {project_name}")
        sys.exit(1)

    project_id = created_project['id']

    project_playbooks = get_aa_playbooks(aa, project_id)

    if not project_playbooks:
        print(f"Unable to collect project playbooks for {project_name}")
        sys.exit(1)

    project_playbooks = [x for x in project_playbooks if x.startswith('awx-')]
    #print("PP", project_playbooks)

    create_credential_type = create_aa_credential_type(aa, credential_type)

    if not create_credential_type:
        print(f"Unable to create credential type {credential_type}")
        sys.exit(1)

    create_credential_type_id = create_credential_type['id']

    create_credential = create_aa_credential(aa, credential_name, create_credential_type_id, org_id, app_config['netbox_api_config'], app_config['proxmox_api_config'])

    if not create_credential:
        print(f"Unable to create credential {credential_name}")
        sys.exit(1)

    created_job_templates = []
    for project_playbook in project_playbooks:
        created_job_template = create_aa_job_template(aa, project_playbook, inventory_id, org_id, created_ee_id, project_id)
        created_job_templates.append(created_job_template)

    for created_job_template_item in created_job_templates:
        create_aa_job_template_credential(aa, created_job_template_item['id'], credential_name)

    #print(org_id, inventory_id, project_id, created_project['related']['playbooks'], create_credential_id, create_credential_type_id)

    sys.exit(0)


if __name__ == '__main__':
    main()
