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
from helpers.netbox_objects import __netbox_make_slug, NetBox, NetBoxSites, NetBoxManufacturers, NetBoxPlatforms, NetBoxTags, NetBoxDeviceRoles, NetBoxDeviceTypes, NetBoxDeviceTypesInterfaceTemplates, NetBoxDevices, NetBoxDevicesInterfaces, NetBoxDeviceInterfaceMacAddressMapping, NetBoxDeviceCreateBridgeInterface, NetBoxClusterTypes, NetBoxClusters, NetBoxVirtualMachines, NetBoxVirtualMachineInterface, NetBoxIPAddresses
from helpers.netbox_branches import NetBoxBranches

from proxmoxer import ProxmoxAPI, ResourceException

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

nb_obj = None


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


def netbox_create_cluster_type(netbox_url: str, netbox_api_token: str, cluster_type: str):
    try:
        return dict(NetBoxClusterTypes(netbox_url, netbox_api_token, {'name': cluster_type, 'slug': __netbox_make_slug(cluster_type)}).obj)['id']
    except Exception as e:
        raise ValueError(e)


def netbox_create_cluster(netbox_url: str, netbox_api_token: str, cluster_name: str, cluster_type: int):
    try:
        return dict(NetBoxClusters(netbox_url, netbox_api_token, {'name': cluster_name, 'type': cluster_type, 'status': 'active'}).obj)['id']
    except Exception as e:
        raise ValueError(e)


def netbox_associate_device_with_cluster(nb_obj, device_id: int, cluster_id: int):
    try:
        check_device = nb_obj.nb.dcim.devices.get(id=device_id)

        if not check_device:
            raise ValueError(f"Unable to find device id {device_id} in NetBox")

        check_cluster = nb_obj.nb.virtualization.clusters.get(id=cluster_id)

        if not check_cluster:
            raise ValueError(f"Unable to find cluster id {cluster_id} in NetBox")

        check_device.cluster = cluster_id
        check_device.save()
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)


def main():
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
    nb_obj = NetBox(nb_url, app_config['netbox_api_config']['api_token'], None)
    #print(nb_obj, dir(nb_obj))

    if 'branch' in app_config['netbox']:
        branch_name = app_config['netbox']['branch']

        branch_timeout = 0
        if 'branch_timeout' in app_config['netbox']:
            branch_timeout = app_config['netbox']['branch_timeout']

        branch_site = NetBoxBranches(nb_obj)
        branch_site.create_branch(branch_name, branch_timeout)
        print("BBB", branch_site.branches, dir(nb_obj))

        if not 'X_NETBOX_BRANCH' in os.environ:
            os.environ['X_NETBOX_BRANCH'] = branch_site.branches[branch_name]

        #nb_obj.nb.http_session.headers["X-NetBox-Branch"] = branch_site.branches[branch_name]

    nb_pxmx_cluster = NetBoxProxmoxCluster(app_config, nb_obj)

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
            netbox_device_id = dict(NetBoxDevices(nb_url, app_config['netbox_api_config']['api_token'], {'name': proxmox_node, 'role': netbox_device_role_id, 'device_type': netbox_device_type_id, 'site': netbox_site_id, 'platform': netbox_platform_id, 'serial': device_serial, 'status': 'active'}).obj)['id']
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

            print(f"device: {proxmox_node}, interface: {device_interface} {device_interface.type} {device_interface.mac_address}")

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

                        nb_assign_ip_address = NetBoxIPAddresses(nb_url, app_config['netbox_api_config']['api_token'], nb_assign_ip_address_payload, 'address')

                    #vmbrX_interface_details = dict(vmbrX_interface)

                    #if not 'id' in vmbrX_interface_details:
                    #    raise ValueError(f"'id' missing for interface {vmbr_info[device_interface.name]} on {proxmox_node}")
            else:
                if 'ipv4address' in nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][device_interface.name]:
                    #print(f"Assigning {nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][device_interface.name]['ipv4address']} to {device_interface.name} on {proxmox_node}")                        
                    nb_assign_ip_address_payload = {
                        'address': nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][device_interface.name]['ipv4address'],
                        'status': 'active',
                        'assigned_object_type': 'dcim.interface',
                        'assigned_object_id': str(device_interface.id)
                    }

                    nb_assign_ip_address = NetBoxIPAddresses(nb_url, app_config['netbox_api_config']['api_token'], nb_assign_ip_address_payload, 'address')

        # create cluster type and cluster in NetBox
        netbox_cluster_type_id = netbox_create_cluster_type(nb_url, app_config['netbox_api_config']['api_token'], 'Proxmox')

        if not netbox_cluster_type_id:
            raise ValueError(f"Unable to create Proxmox cluster type in NetBox for {proxmox_node}")
        
        netbox_cluster_id = netbox_create_cluster(nb_url, app_config['netbox_api_config']['api_token'], nb_pxmx_cluster.proxmox_cluster_name, netbox_cluster_type_id)

        if not netbox_cluster_id:
            raise ValueError(f"Unable to create Proxmox cluster {nb_pxmx_cluster.proxmox_cluster_name} in NetBox")
        
        # associate nodes in NetBox with cluster
        #print(f"Want to associate {proxmox_node}, device id: {netbox_device_id} with {nb_pxmx_cluster.proxmox_cluster_name}")
        netbox_associate_device_with_cluster(nb_obj, netbox_device_id, netbox_cluster_id)


if __name__ == "__main__":
    main()
