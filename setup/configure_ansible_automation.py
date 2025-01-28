#!/usr/bin/env python3

import os, sys, re
import argparse
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

    return aa_obj.create_object('projects', project_name, project_payload)


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

    print(org_id, inventory_id, project_id, created_project, aa.get_object_by_id('projects', project_id))
    print(dir(aa.api_v2))

    sys.exit(0)


if __name__ == '__main__':
    main()
