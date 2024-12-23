#!/usr/bin/env python3

# adapted from sol1 implementation

import os, sys, re
import argparse
import yaml
import json
import pynetbox

from helpers.netbox_proxmox_api import NetBoxProxmoxAPIHelper

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


class Netbox:
    def __init__(self, url, token, payload) -> None:
        # NetBox API details
        self.netbox_url = url
        self.netbox_token = token
        self.payload = payload
        self.object_type = None
        self.obj = None
        self.required_fields = []
        self.init_api()


    def init_api(self):
        # Initialize pynetbox API connection
        self.nb = pynetbox.api(self.netbox_url, token=self.netbox_token)


    def findBy(self, key):
        self.obj = self.object_type.get(**{key: self.payload[key]})

    @property
    def hasRequired(self):
        missing = []
        for key in self.required_fields:
            if key not in self.payload:
                missing.append(key)
        if missing:
            print(f"missing required fields {', '.join(missing)}")
            return False
        else: 
            return True

    def createOrUpdate(self):
        # If object exists see if we need to update it
        if self.obj:
            # Do we need to save?
            updated = False

            for key, value in self.payload.items():
                if isinstance(value, dict):
                    if hasattr(self.obj, key):
                        child_key = next(iter(value))
                        child_value = value[child_key]
                        if not hasattr(self.obj, key) or not hasattr(getattr(self.obj, key), child_key) or getattr(getattr(self.obj, key), child_key) != child_value:
                            print(f"Updating '{key}' from '{getattr(self.obj, key)}' to '{value}'")
                            setattr(self.obj, key, value)
                            updated = True 
                else:
                    if getattr(self.obj, key) != value:
                        print(f"Updating '{key}' from '{getattr(self.obj, key)}' to '{value}'")
                        setattr(self.obj, key, value)
                        updated = True                
            if updated:
                self.obj.save()
                # TODO: error handling here
                print(f"Object '{self.payload}' updated successfully.")
            else:
                print(f"No changes detected for '{self.payload}'.")
        # If the object doesn't exist then create it
        else:
            if self.hasRequired:
                self.object_type.create(self.payload)
                if 'name' in self.payload:
                    print(f"Object '{self.payload['name']}' created successfully.")
                elif 'username' in self.payload:              
                    print(f"Object '{self.payload['username']}' created successfully.")


class NetboxCustomFields(Netbox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.extras.custom_fields
        self.required_fields = [ 
            "weight",
            "filter_logic",
            "search_weight",
            "object_types",
            "type",
            "name",
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetboxCustomFieldChoiceSets(Netbox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.extras.custom_field_choice_sets
        self.required_fields = [ 
            "name",
            "extra_choices",

        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetboxClusterTypes(Netbox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.virtualization.cluster_types
        self.required_fields = [ 
            "name",
            "slug",
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetboxClusters(Netbox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.virtualization.clusters
        self.required_fields = [ 
            "name",
            "type",
            "status",
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetboxVirtualMachines(Netbox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.virtualization.virtual_machines
        self.required_fields = [ 
            "name",
            "status"
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetboxIPAddresses(Netbox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.ipam.ip_addresses
        self.required_fields = [ 
            "address",
            "status"    
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


def create_custom_field_choice_sets_proxmox_vm_templates(proxmox_api_obj):
    proxmox_api_obj.proxmox_get_vm_templates()
    extra_choices = []

    for k, v in proxmox_api_obj.proxmox_vm_templates.items():
        extra_choices.append([str(k), v])

    ncfcs = NetboxCustomFieldChoiceSets(netbox_url, netbox_api_token, {'name': 'proxmox-vm-templates', 'extra_choices': extra_choices})
    return dict(ncfcs.obj)['id']


def create_custom_field_choice_sets_proxmox_vm_storage(proxmox_api_obj):
    proxmox_api_obj.proxmox_get_vm_storage_volumes()
    print(proxmox_api_obj.proxmox_storage_volumes)

    extra_choices = []

    for psv in proxmox_api_obj.proxmox_storage_volumes:
        extra_choices.append([psv, psv])

    ncfcs = NetboxCustomFieldChoiceSets(netbox_url, netbox_api_token, {'name': 'proxmox-vm-storage', 'extra_choices': extra_choices})
    return dict(ncfcs.obj)['id']


def create_custom_field_choice_sets_proxmox_vm_cluster_nodes(proxmox_api_obj):
    extra_choices = []

    # get proxmox nodes
    proxmox_api_obj.get_proxmox_nodes()
    proxmox_cluster_nodes = proxmox_api_obj.proxmox_nodes

    for pcn in proxmox_cluster_nodes:
        extra_choices.append([pcn, pcn])

    ncfcs = NetboxCustomFieldChoiceSets(netbox_url, netbox_api_token, {'name': 'proxmox-cluster-nodes', 'extra_choices': extra_choices})
    return dict(ncfcs.obj)['id']


def create_custom_field(netbox_url=None, netbox_api_token=None, name=None, label=None, choice_set_id=0, default=None):
    if name in ['proxmox_node', 'proxmox_vm_storage', 'proxmox_vm_template']:
        object_types = ['virtualization.virtualmachine']
        input_type = {'value': 'select', 'label': 'Selection'}
    elif name in ['proxmox_disk_storage_volume']:
        object_types = ['virtualization.virtualdisk']
        input_type = {'value': 'select', 'label': 'Selection'}
    elif name in ['proxmox_public_ssh_key']:
        object_types = ['virtualization.virtualmachine']
        input_type = {'value': 'longtext', 'label': 'Text (long)'}
    elif name in ['proxmox_vmid']:
        object_types = ['virtualization.virtualmachine']
        input_type = {'value': 'text', 'label': 'Text'}

    if input_type['value'] == 'select':
        nbcf = NetboxCustomFields(netbox_url, netbox_api_token,
                                {'weight': 100, 'filter_logic': {'value': 'loose', 'label': 'Loose'}, 'search_weight': 1000,
                                'object_types': object_types,
                                'type': input_type,
                                'group_name': 'Proxmox',
                                'name': name,
                                'label': label,
                                'choice_set': choice_set_id,
                                'default': default})
    elif input_type['value'] == 'text':
        nbcf = NetboxCustomFields(netbox_url, netbox_api_token,
                                {'weight': 100, 'filter_logic': {'value': 'loose', 'label': 'Loose'}, 'search_weight': 1000,
                                'object_types': object_types,
                                'type': input_type,
                                'group_name': 'Proxmox',
                                'name': name,
                                'label': label})
    elif input_type['value'] == 'longtext':
        nbcf = NetboxCustomFields(netbox_url, netbox_api_token,
                                {'weight': 100, 'filter_logic': {'value': 'loose', 'label': 'Loose'}, 'search_weight': 1000,
                                'object_types': object_types,
                                'type': input_type,
                                'group_name': 'Proxmox',
                                'name': name,
                                'label': label})

    return dict(nbcf.obj)['id']


if __name__ == "__main__":
    default_netbox_proxmox_name = 'Proxmox'
    default_netbox_cluster_role = default_netbox_proxmox_name
    default_netbox_cluster_name = 'proxmox-ve'
    default_netbox_vm_role = 'Proxmox VM'

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

    # init Proxmox API integration
    p = NetBoxProxmoxAPIHelper(app_config)

    # setup defaults and override from config values later
    proxmox_cluster_name = default_netbox_cluster_name
    vm_cluster_role = default_netbox_cluster_role
    vm_role = default_netbox_vm_role

    if 'proxmox' in app_config:
        if 'cluster_name' in app_config['proxmox']:
            proxmox_cluster_name = app_config['proxmox']['cluster_name']

    if 'netbox' in app_config:
        if 'cluster_role' in app_config['netbox']:
            vm_cluster_role = app_config['netbox']['cluster_role']

        if 'vm_role' in app_config['netbox']:
            vm_role = app_config['netbox']['vm_role']
    
    # vm clusters and types
    nbct = NetboxClusterTypes(netbox_url, netbox_api_token, {'name': vm_cluster_role, 'slug': __netbox_make_slug(vm_cluster_role)})
    netbox_cluster_type_id = dict(nbct.obj)['id']

    nbc = NetboxClusters(netbox_url, netbox_api_token, {'name': proxmox_cluster_name, 'type': netbox_cluster_type_id, 'status': 'active'})
    netbox_cluster_id = dict(nbc.obj)['id']

    # custom field choice sets
    netbox_field_choice_sets_templates_id = create_custom_field_choice_sets_proxmox_vm_templates(p)

    netbox_field_choice_sets_vm_storage_volumes_id = create_custom_field_choice_sets_proxmox_vm_storage(p)

    netbox_field_choice_sets_proxmox_nodes_id = create_custom_field_choice_sets_proxmox_vm_cluster_nodes(p)

    # custom fields

    # VM template id
    custom_field_template_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_vm_template', 'Proxmox VM Template', netbox_field_choice_sets_templates_id, str(min(p.proxmox_vm_templates.keys())))

    # VM proxmox node id
    custom_field_proxmox_node_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_node', 'Proxmox node', netbox_field_choice_sets_proxmox_nodes_id, p.proxmox_nodes[0])

    # proxmox_vmid
    custom_field_proxmox_vm_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_vmid', 'Proxmox Virtual machine ID (vmid)')

    # proxmox_public_ssh_key
    custom_field_proxmox_public_ssh_key_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_public_ssh_key', 'Proxmox public SSH key')

    # proxmox_disk_storage_volume
    custom_field_proxmox_disk_storage_volume_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_disk_storage_volume', 'Proxmox Disk Storage Volume', netbox_field_choice_sets_vm_storage_volumes_id, p.proxmox_storage_volumes[0])

    # proxmox_vm_storage
    custom_field_proxmox_disk_storage_volume_id = create_custom_field(netbox_url, netbox_api_token, 'proxmox_vm_storage', 'Proxmox VM Storage', netbox_field_choice_sets_vm_storage_volumes_id, p.proxmox_storage_volumes[0])
