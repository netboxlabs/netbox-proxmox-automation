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


def create_aa_project(aa_obj = None, project_name = None):
    project_payload = {
        'name': project_name
    }

    return aa_obj.create_object('projects', project_name, project_payload)


def main():
    args = get_arguments()
    app_config_file = args.config

    default_organization = 'Default'
    default_inventory = 'Default Inventory'

    default_project = 'netbox-proxmox-ee-test1'
    default_scm_type = 'git'
    default_git_url = 'https://github.com/netboxlabs/netbox-proxmox-automation.git'
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
    print(aa.cfg_data)

    print("FOUND ORG?", aa.get_object_id('organizations', 'Default'))
    print("FOUND INVENTORY?", aa.get_object_id('inventory', 'Demo Inventory'))

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

    project_name = default_project
    if 'project_name' in app_config['ansible_automation']['settings']:
        project_name = app_config['ansible_automation']['settings']['project']

    created_project = create_aa_project(aa, project_name)

    if not created_project:
        print(f"Unable to create project {project_name}")
        sys.exit(1)

    project_id = created_project['id']

    print(org_id, inventory_id, project_id, created_project, aa.get_object_by_id('projects', project_id))

    sys.exit(0)


if __name__ == '__main__':
    main()
