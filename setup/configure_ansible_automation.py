#!/usr/bin/env python3

import os, sys, re
import argparse
import yaml

from helpers.ansible_automation_awx_manager import AnsibleAutomationAWXManager


def get_arguments():
    # Initialize the parser
    parser = argparse.ArgumentParser(description="Command-line Parsing for AWX (Tower/AAP) Object Creations")

    sub_parser = parser.add_subparsers(dest='action_type',
                                       required=True,
                                       description='Ansible Automation actions',
                                       help='additional help')

    aa_create = sub_parser.add_parser('create', help='create objects help action')
    aa_create.add_argument("--config", required=True, help="YAML file containing the configuration")

    aa_destroy = sub_parser.add_parser('destroy', help='destroy objects help action')
    aa_destroy.add_argument("--config", required=True, help="YAML file containing the configuration")

    # Parse the arguments
    args = parser.parse_args()

    # Return the parsed arguments
    return args


def main():
    args = get_arguments()
    app_config_file = args.config

    default_organization = 'Default'
    default_inventory = 'Default Inventory'

    default_host_name = 'localhost'
    default_host_var_data = "---\nansible_connection: local\nansible_python_interpreter: '{{ ansible_playbook_python }}'"

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


    # Set common variables
    org_name = default_organization
    if 'organization' in app_config['ansible_automation']['settings']:
        org_name = app_config['ansible_automation']['settings']['organization']

    inventory_name = default_inventory
    if 'inventory' in app_config['ansible_automation']['settings']:
        if 'name' in app_config['ansible_automation']['settings']['inventory']:
            inventory_name = app_config['ansible_automation']['settings']['inventory']['name']

    host_name = default_host_name
    host_var_data = default_host_var_data
    if 'hosts' in app_config['ansible_automation']['settings']:
        if 'name' in app_config['ansible_automation']['settings']['hosts']:
            host_name = app_config['ansible_automation']['settings']['hosts']['name']

        if 'var_data' in app_config['ansible_automation']['settings']['hosts']:
            host_var_data = app_config['ansible_automation']['settings']['hosts']['var_data']

    ee_name = default_execution_environment
    ee_image_name = default_execution_environment_image
    if 'execution_environment' in app_config['ansible_automation']['settings']:
        if 'name' in app_config['ansible_automation']['settings']['execution_environment']:
            ee_name = app_config['ansible_automation']['settings']['execution_environment']['name']

        if 'image' in app_config['ansible_automation']['settings']['execution_environment']:
            ee_image_name = app_config['ansible_automation']['settings']['execution_environment']['image']

    project_name = default_project
    if 'project' in app_config['ansible_automation']['settings']:
        if 'name' in app_config['ansible_automation']['settings']['project']:
            project_name = app_config['ansible_automation']['settings']['project']['name']

    scm_type = default_scm_type
    if 'project' in app_config['ansible_automation']['settings']:
        if 'scm_type' in app_config['ansible_automation']['settings']['project']:
            scm_type = app_config['ansible_automation']['settings']['project']['scm_type']

    scm_url = default_scm_url
    if 'project' in app_config['ansible_automation']['settings']:
        if 'scm_url' in app_config['ansible_automation']['settings']['project']:
            scm_url = app_config['ansible_automation']['settings']['project']['scm_url']

    scm_branch = default_scm_branch
    if 'project' in app_config['ansible_automation']['settings']:
        if 'scm_branch' in app_config['ansible_automation']['settings']['project']:
            scm_branch = app_config['ansible_automation']['settings']['project']['scm_branch']
    # End set common variables

    
    aam = AnsibleAutomationAWXManager(app_config)

    if args.action_type == 'create':
        aam.create_organization(org_name)

        aam.create_inventory(inventory_name)

        aam.create_host(host_name, host_var_data)

        aam.create_execution_environment(ee_name, ee_image_name)

        aam.create_project(project_name, scm_type, scm_url, scm_branch)

        project_playbooks = aam.get_playbooks()
        project_playbooks = [x for x in project_playbooks if x.startswith('awx-')]
        #print("project playbooks", project_playbooks)

        if not project_playbooks:
            print("I can't find any project playbooks.  Therefore I cannot create any templates.  Exiting.")
            sys.exit(1)

        aam.create_credential_type(credential_type)

        aam.create_credential(credential_name)

        for project_playbook in project_playbooks:
            aam.create_job_template(project_playbook)

        for created_job_template_item in aam.created_job_templates:
            aam.create_job_template_credential(created_job_template_item['id'])
    elif args.action_type == 'destroy':
        aam.get_project(project_name)

        aam.get_job_templates_for_project()

        if not aam.job_templates:
            print(f"Unable to find any job templates for project {project_name}!")
            sys.exit(1)

        collected_credentials = {}
        for project_template in aam.job_templates:
            related_credentials = aam.get_object_by_id('credentials', project_template.get_related('credentials').results[0]['id'])

            if related_credentials:
                related_credentials_type = aam.get_object_by_id('credential_types', related_credentials.get_related('credential_type')['id'])
                collected_credentials[related_credentials['name']] = related_credentials_type['name']

            aam.delete_job_template(project_template)

        aam.delete_project()

        if credential_name in collected_credentials:
            aam.delete_credential(credential_name)

        if collected_credentials[credential_name] == credential_type:
            aam.delete_credential_type(credential_type)

        if host_name != default_host_name:
            aam.delete_host(host_name)

        if inventory_name != default_inventory:
            aam.delete_inventory(inventory_name)

    sys.exit(0)


if __name__ == '__main__':
    main()
