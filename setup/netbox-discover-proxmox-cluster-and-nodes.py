#!/usr/bin/env python3

import os, sys, re
import time
import argparse
import yaml
import json
import getpass
import paramiko
import pynetbox
import proxmoxer
import urllib3

from helpers.netbox_proxmox_cluster import NetBoxProxmoxCluster
#from helpers.netbox_proxmox_api import NetBoxProxmoxAPIHelper
from helpers.netbox_objects import __netbox_make_slug, NetBox, NetBoxSites, NetBoxManufacturers, NetBoxPlatforms, NetBoxTags, NetBoxDeviceRoles, NetBoxDeviceTypes, NetBoxDeviceTypesInterfaceTemplates, NetBoxDevices, NetBoxDevicesInterfaces, NetBoxDeviceInterfaceMacAddressMapping, NetBoxDeviceCreateBridgeInterface, NetBoxClusterTypes, NetBoxClusters, NetBoxClusterGroups, NetBoxVirtualMachines, NetBoxVirtualMachineInterface, NetBoxIPAddresses

from proxmoxer import ProxmoxAPI, ResourceException

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_arguments():
    # Initialize the parser
    parser = argparse.ArgumentParser(description="Import Proxmox Cluster (optional) and Nodes Configurations")

    parser.add_argument("--config", required=True, help="YAML file containing the configuration")

    # Parse the arguments
    args = parser.parse_args()

    # Return the parsed arguments
    return args


def get_proxmox_node_vmbr_network_interface_mapping(proxmox_api_config: dict, proxmox_node: str, network_interface: str):
    proxmox_vmbrX_network_interface_mapping = {}

    try:
        proxmox = ProxmoxAPI(
            proxmox_api_config['api_host'],
            port=proxmox_api_config['api_port'],
            user=proxmox_api_config['api_user'],
            token_name=proxmox_api_config['api_token_id'],
            token_value=proxmox_api_config['api_token_secret'],
            verify_ssl=False
        )

        proxmox_node_network_settings = proxmox.nodes(proxmox_node).network.get()

        proxmox_vmbrX_interface_mapping = list(filter(lambda d: 'bridge_ports' in d and d['bridge_ports'] == network_interface, proxmox_node_network_settings))

        if proxmox_vmbrX_interface_mapping:
            if not network_interface in proxmox_vmbrX_network_interface_mapping:
                proxmox_vmbrX_network_interface_mapping[network_interface] = []

            proxmox_vmbrX_network_interface_mapping[network_interface] = proxmox_vmbrX_interface_mapping[0]['iface']
        
        return proxmox_vmbrX_network_interface_mapping
    except ResourceException as e:
        print("E", e, dir(e), e.status_code, e.status_message, e.errors)
        if e.errors:
            if 'vmid' in e.errors:
                print("F", e.errors['vmid'])

    return {}


def main():
    default_proxmox_cluster_type = 'Proxmox'
    discovered_proxmox_nodes_information = {}

    args = get_arguments()
    #print("ARGS", args, args.config)

    try:
        with open(args.config, 'r') as cfg_f:
            app_config = yaml.safe_load(cfg_f)
    except yaml.YAMLError as exc:
        print(exc)

    #print("CFG DATA", app_config, app_config['proxmox_api_config'])

    nb_url = f"{app_config['netbox_api_config']['api_proto']}://{app_config['netbox_api_config']['api_host']}:{str(app_config['netbox_api_config']['api_port'])}/"

    if 'branch' in app_config['netbox']:
        branch_name = app_config['netbox']['branch']
        os.environ['NETBOX_BRANCH'] = branch_name

        branch_timeout = 0
        if 'branch_timeout' in app_config['netbox']:
            branch_timeout = app_config['netbox']['branch_timeout']
        os.environ['NETBOX_BRANCH_TIMEOUT'] = str(branch_timeout)

    nb_pxmx_cluster = NetBoxProxmoxCluster(app_config)

    if not 'site' in app_config['netbox']:
        netbox_site = "netbox-proxmox-automation Default Site"
    else:
        netbox_site = app_config['netbox']['site']

    #nb_pxmx_cluster.get_proxmox_cluster_info()

    # Collect Proxmox node login information
    nb_pxmx_cluster.generate_proxmox_node_creds_configuration()
    proxmox_nodes_connection_info = nb_pxmx_cluster.proxmox_nodes_connection_info

    # discover nodes base system information
    nb_pxmx_cluster.get_proxmox_nodes_system_information()
    nb_pxmx_cluster.get_proxmox_nodes_network_interfaces()
    discovered_proxmox_nodes_information = nb_pxmx_cluster.discovered_proxmox_nodes_information

    #print("DISCOVERED PROXMOX NODES INFORMATION", discovered_proxmox_nodes_information)
    #print(nb_pxmx_cluster.proxmox_nodes['pxmx-n1'])

    try:
        netbox_site_id = dict(NetBoxSites(nb_url, app_config['netbox_api_config']['api_token'], {'name': netbox_site, 'slug': __netbox_make_slug(netbox_site), 'status': 'active'}).obj)['id']
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)

    # create cluster type and cluster in NetBox
    try:
        if 'cluster_role' in app_config['netbox']:
            proxmox_cluster_type = app_config['netbox']['cluster_role']
        else:
            proxmox_cluster_type = default_proxmox_cluster_type

        netbox_cluster_type_id = dict(NetBoxClusterTypes(nb_url, app_config['netbox_api_config']['api_token'], {'name': proxmox_cluster_type, 'slug': __netbox_make_slug(proxmox_cluster_type)}).obj)['id']
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)        

    try:
        if 'cluster_group' in app_config['netbox']:
            cluster_group = app_config['netbox']['cluster_group']
        else:
            cluster_group = netbox_site

        netbox_cluster_group_id = dict(NetBoxClusterGroups(nb_url, app_config['netbox_api_config']['api_token'], {'name': cluster_group, 'slug': __netbox_make_slug(cluster_group)}).obj)['id']
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)        

    try:
        netbox_cluster_id = dict(NetBoxClusters(nb_url, app_config['netbox_api_config']['api_token'], {'name': nb_pxmx_cluster.proxmox_cluster_name, 'type': netbox_cluster_type_id, 'group': netbox_cluster_group_id, 'status': 'active'}).obj)['id']
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)        

    for proxmox_node in discovered_proxmox_nodes_information:
        # Create Manufacturer in NetBox
        try:
            manufacturer_name = discovered_proxmox_nodes_information[proxmox_node]['system']['manufacturer']
            netbox_manufacturer_id = dict(NetBoxManufacturers(nb_url, app_config['netbox_api_config']['api_token'], {'name': manufacturer_name, 'slug': __netbox_make_slug(manufacturer_name)}).obj)['id']
        except pynetbox.RequestError as e:
            raise ValueError(e, e.error)

        # Create Platform in NetBox
        if not 'version' in nb_pxmx_cluster.proxmox_nodes[proxmox_node]:
            raise ValueError(f"Missing Proxmox version information for {proxmox_node}")
        
        try:
            proxmox_version = nb_pxmx_cluster.proxmox_nodes[proxmox_node]['version']
            netbox_platform_id = dict(NetBoxPlatforms(nb_url, app_config['netbox_api_config']['api_token'], {'name': proxmox_version, 'slug': __netbox_make_slug(proxmox_version)}).obj)['id']
        except pynetbox.RequestError as e:
            raise ValueError(e, e.error)        

        # Create NetBox Device Role
        try:
            device_role_name = app_config['netbox']['device_role']
            netbox_device_role_id = dict(NetBoxDeviceRoles(nb_url, app_config['netbox_api_config']['api_token'], {'name': device_role_name, 'slug': __netbox_make_slug(device_role_name), 'vm_role': False}).obj)['id']
        except pynetbox.RequestError as e:
            raise ValueError(e, e.error)

        # Create Device Type in NetBox
        try:
            device_model = nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['model']
            netbox_device_type_id = dict(NetBoxDeviceTypes(nb_url, app_config['netbox_api_config']['api_token'], {'manufacturer': netbox_manufacturer_id, 'model': device_model, 'slug': __netbox_make_slug(device_model), 'u_height': 1}).obj)['id']
        except pynetbox.RequestError as e:
            raise ValueError(e, e.error)

        # Create Interfaces for Device Type in NetBox
        for network_interface in discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces']:
            if network_interface.startswith('vmbr'):
                continue

            #print(f"network interface: {network_interface}")

            try:
                network_interface_type = nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][network_interface]['type']
                NetBoxDeviceTypesInterfaceTemplates(nb_url, app_config['netbox_api_config']['api_token'], {'device_type': netbox_device_type_id, 'name': network_interface, 'type': network_interface_type, 'enabled': False})
            except pynetbox.RequestError as e:
                raise ValueError(e, e.error)

        # Create Device in NetBox
        try:
            device_serial = nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['serial']
            netbox_device_id = dict(NetBoxDevices(nb_url, app_config['netbox_api_config']['api_token'], {'name': proxmox_node, 'role': netbox_device_role_id, 'device_type': netbox_device_type_id, 'site': netbox_site_id, 'platform': netbox_platform_id, 'serial': device_serial, 'cluster': netbox_cluster_id, 'status': 'active'}).obj)['id']
        except pynetbox.RequestError as e:
            raise ValueError(e, e.error)

        if not netbox_device_id:
            raise ValueError(f"NetBox missing device id for {proxmox_node}, device type id {netbox_device_type_id}")

        try:
            device_interfaces = list(NetBoxDevicesInterfaces(nb_url, app_config['netbox_api_config']['api_token'], {'device_id': netbox_device_id}).multi_obj)
        except pynetbox.RequestError as e:
            raise ValueError(e, e.error)
    
        for device_interface in device_interfaces:
            if device_interface.name.startswith('vmbr'):
                continue

            print(f"device: {proxmox_node}, interface: {device_interface.name} ({device_interface.type}) [MAC address redacted]")

            try:
                NetBoxDeviceInterfaceMacAddressMapping(nb_url, app_config['netbox_api_config']['api_token'], netbox_device_id, device_interface, nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][device_interface.name])            
            except pynetbox.RequestError as e:
                raise ValueError(e, e.error)

            # Create bridge interface name: vmbrX, bridge: device_interface.id
            vmbr_info = get_proxmox_node_vmbr_network_interface_mapping(app_config['proxmox_api_config'], proxmox_node, device_interface.name)

            if vmbr_info:
                if device_interface.name in vmbr_info:
                    try:
                        vmbrX_interface_data = {
                            'device': netbox_device_id,
                            'type': nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][device_interface.name]['type'],
                            'bridge': device_interface.id,
                            'name': vmbr_info[device_interface.name],
                            'enabled': True
                        }

                        nb_bridge_interface = NetBoxDeviceCreateBridgeInterface(nb_url, app_config['netbox_api_config']['api_token'], vmbrX_interface_data)
                    except pynetbox.RequestError as e:
                        raise ValueError(e, e.error)

                    if 'ipv4address' in nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][nb_bridge_interface.obj.display]:
                        #print(f"Assigning {nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][vmbrX_interface_details['display']]['ipv4address']} to {vmbrX_interface_details['display']} on {proxmox_node}")                        
                        nb_assign_ip_address_payload = {
                            'address': nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][nb_bridge_interface.obj.display]['ipv4address'],
                            'status': 'active',
                            'assigned_object_type': 'dcim.interface',
                            'assigned_object_id': str(nb_bridge_interface.obj.id)
                        }

                        try:
                            ipv4_address = NetBoxIPAddresses(nb_url, app_config['netbox_api_config']['api_token'], nb_assign_ip_address_payload, 'address')
                        except pynetbox.RequestError as e:
                            raise ValueError(e, e.error)

            else:
                if 'ipv4address' in nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][device_interface.name]:
                    #print(f"Assigning {nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][device_interface.name]['ipv4address']} to {device_interface.name} on {proxmox_node}")                        
                    nb_assign_ip_address_payload = {
                        'address': nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][device_interface.name]['ipv4address'],
                        'status': 'active',
                        'assigned_object_type': 'dcim.interface',
                        'assigned_object_id': str(device_interface.id)
                    }

                    try:
                        ipv4_address = NetBoxIPAddresses(nb_url, app_config['netbox_api_config']['api_token'], nb_assign_ip_address_payload, 'address')
                    except pynetbox.RequestError as e:
                        raise ValueError(e, e.error)

    # If there are no changes, then delete the branch
    if getattr(ipv4_address, 'nbb'):
        if not ipv4_address.nbb.branch_changes():
            print(f"No changes.  Deleting branch {ipv4_address.nbb.branch_name}")
            del ipv4_address.nb.http_session.headers['X-NetBox-Branch']
            ipv4_address.nbb.delete_branch()


if __name__ == "__main__":
    main()
