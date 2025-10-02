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
from helpers.netbox_proxmox_api import NetBoxProxmoxAPIHelper
from helpers.netbox_objects import Netbox, NetBoxSites, NetBoxManufacturers, NetBoxTags, NetBoxDeviceRoles, NetBoxDeviceTypes, NetBoxDevices, NetBoxDeviceInterfaceTemplates, NetboxClusterTypes, NetboxClusters, NetboxVirtualMachines, NetboxVirtualMachineInterface, NetboxIPAddresses
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


def __netbox_make_slug(in_str):
    return re.sub(r'\W+', '-', in_str).lower()


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


def netbox_create_site(netbox_url: str, netbox_api_token: str, site_name: str):
    try:
        return dict(NetBoxSites(netbox_url, netbox_api_token, {'name': site_name, 'slug': __netbox_make_slug(site_name), 'status': 'active'}).obj)['id']
    except Exception as e:
        raise ValueError(e)


def netbox_create_device_manufacturer(netbox_url: str, netbox_api_token: str, manufacturer_name: str):
    try:
        return dict(NetBoxManufacturers(netbox_url, netbox_api_token, {'name': manufacturer_name, 'slug': __netbox_make_slug(manufacturer_name)}).obj)['id']
    except Exception as e:
        raise ValueError(e)


def netbox_create_device_role(netbox_url: str, netbox_api_token: str, device_role_name: str):
    try:
        return dict(NetBoxDeviceRoles(netbox_url, netbox_api_token, {'name': device_role_name, 'slug': __netbox_make_slug(device_role_name), 'vm_role': False}).obj)['id']
    except Exception as e:
        raise ValueError(e)


def netbox_create_device_type(netbox_url: str, netbox_api_token: str, manufacturer_id: int, model: str):
    try:
        return dict(NetBoxDeviceTypes(netbox_url, netbox_api_token, {'manufacturer': manufacturer_id, 'model': model, 'slug': __netbox_make_slug(model), 'u_height': 1}).obj)['id']
    except Exception as e:
        raise ValueError(e)


def netbox_create_interface_for_device_type(nb_obj, device_type_id: int, interface_name: str, interface_type: str):
    try:
        device_type_interface_payload = {
            'device_type': {
                    'id': device_type_id
                },
            'name': interface_name,
            'enabled': False,
            'mgmt_only': False,
            'type': interface_type
        }

        created_device_type_interface = nb_obj.nb.dcim.interface_templates.get(device_type = device_type_id, name = interface_name)

        if not created_device_type_interface:
            created_device_type_interface = nb_obj.nb.dcim.interface_templates.create(device_type_interface_payload)

        created_device_type_interface_id = dict(created_device_type_interface)['id']

        return created_device_type_interface_id
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)


def netbox_create_device_for_proxmox_node(netbox_url: str, netbox_api_token: str, device_name: str, device_role: int, device_type: int, site: int, serial: str):
    try:
        return dict(NetBoxDevices(netbox_url, netbox_api_token, {'name': device_name, 'role': device_role, 'device_type': device_type, 'site': site, 'serial': serial, 'status': 'active'}).obj)['id']
    except Exception as e:
        raise ValueError(e)


def netbox_get_interfaces_for_proxmox_node_by_device_id(nb_obj, device_id: int):
    try:
        interfaces = list(nb_obj.nb.dcim.interfaces.filter(device_id=device_id))
        return interfaces
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)


def __netbox_assign_mac_address_for_proxmox_node_by_object_id(nb_obj, assigned_object_id: int, mac_address: str):
    try:
        mac_address_data = {
            'mac_address': mac_address,
            'assigned_object_type': 'dcim.interface',
            'assigned_object_id': assigned_object_id
        }

        check_mac_address = nb_obj.nb.dcim.mac_addresses.get(assigned_object_id=assigned_object_id, mac_address=mac_address)

        if not check_mac_address:
            new_mac_address = nb_obj.nb.dcim.mac_addresses.create(**mac_address_data)

            if not new_mac_address:
                raise ValueError(f"Unable to create mac address {mac_address} for interface id: {assigned_object_id}")

            return new_mac_address

        return check_mac_address        
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)


def netbox_update_interface_for_proxmox_node_by_device_id(nb_obj, device_id: int, interface_name: str, interface_data: dict):
    try:
        interface = nb_obj.nb.dcim.interfaces.get(device_id=device_id, name=interface_name)

        if not interface:
            raise ValueError(f"Interface {interface_name} not found on device id: {device_id}")

        assigned_mac_address = __netbox_assign_mac_address_for_proxmox_node_by_object_id(nb_obj, interface.id, interface_data['mac'])

        interface.enabled = interface_data['enabled']

        if 'id' in assigned_mac_address:
            interface.primary_mac_address = assigned_mac_address['id']
        else:
            interface.primary_mac_address = assigned_mac_address.id

        interface.save()
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)


def netbox_create_vmbrX_interface_mapping(nb_obj, device_id: int, device_type: str, physical_interface_id: int, vmbr_name: str):
    try:
        interface = nb_obj.nb.dcim.interfaces.get(device_id=device_id, bridge=physical_interface_id, name=vmbr_name)

        if interface:
            return interface

        vmbrX_interface_data = {
            'device': device_id,
            'type': device_type,
            'bridge': physical_interface_id,
            'name': vmbr_name,
            'enabled': True
        }

        new_bridge_interface = nb_obj.nb.dcim.interfaces.create(**vmbrX_interface_data)

        if not new_bridge_interface:
            raise ValueError(f"Unable to create bridge interface {vmbrX_interface_data} for interface id: {physical_interface_id}")
        
        return new_bridge_interface    
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)


def netbox_create_and_assign_ip_address(nb_obj, ip_addr: str, interface_id: int):
    try:
        #check_ip_addr = dict(nb_obj.nb.ipam.ip_addresses.get(address=ip_addr))
        check_ip_addr = nb_obj.nb.ipam.ip_addresses.get(address=ip_addr)

        if not check_ip_addr:
            check_ip_addr = nb_obj.nb.ipam.ip_addresses.create(address=ip_addr)

        #check_ip_addr.assigned_object = device_interface
        check_ip_addr.assigned_object_id = interface_id
        check_ip_addr.assigned_object_type = 'dcim.interface'
        check_ip_addr.save()
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)

    return True


def netbox_create_cluster_type(netbox_url: str, netbox_api_token: str, cluster_type: str):
    try:
        return dict(NetboxClusterTypes(netbox_url, netbox_api_token, {'name': cluster_type, 'slug': __netbox_make_slug(cluster_type)}).obj)['id']
    except Exception as e:
        raise ValueError(e)


def netbox_create_cluster(netbox_url: str, netbox_api_token: str, cluster_name: str, cluster_type: int):
    try:
        return dict(NetboxClusters(netbox_url, netbox_api_token, {'name': cluster_name, 'type': cluster_type, 'status': 'active'}).obj)['id']
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
    nb_obj = Netbox(nb_url, app_config['netbox_api_config']['api_token'], None)
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
        netbox_site = "netbox-proxmox-automation Default NetBox Site"
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

    # Create Site in NetBox
    netbox_site_id = netbox_create_site(nb_url, app_config['netbox_api_config']['api_token'], netbox_site)
 
    if not netbox_site_id:
        raise ValueError(f"Unable to create site {netbox_site} in NetBox")

    for proxmox_node in discovered_proxmox_nodes_information:
        # Create Manufacturer in NetBox
        netbox_manufacturer_id = netbox_create_device_manufacturer(nb_url, app_config['netbox_api_config']['api_token'], discovered_proxmox_nodes_information[proxmox_node]['system']['manufacturer'])

        if not netbox_manufacturer_id:
            raise ValueError(f"NetBox missing manufacturer id for {discovered_proxmox_nodes_information[proxmox_node]['system']['manufacturer']}")

        # Create NetBox Device Role
        netbox_device_role_id = netbox_create_device_role(nb_url, app_config['netbox_api_config']['api_token'], app_config['netbox']['device_role'])

        if not netbox_device_role_id:
            raise ValueError(f"NetBox missing device role for {app_config['netbox']['device_role']}")

        # Create Device Type in NetBox
        netbox_device_type_id = netbox_create_device_type(nb_url, app_config['netbox_api_config']['api_token'], netbox_manufacturer_id, nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['model'])

        if not netbox_device_type_id:
            raise ValueError(f"Netbox missing device type for {nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['manufacturer']}, model {nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['model']}")

        # Create Interfaces for Device Type in NetBox
        for network_interface in discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces']:
            if network_interface.startswith('vmbr'):
                continue

            #print(f"network interface: {network_interface}")

            #netbox_interface_templates_id = netbox_create_interface_for_device_type(nb_url, app_config['netbox_api_config']['api_token'], netbox_device_type_id, network_interface['name'], network_interface['type'])
            netbox_interface_templates_id = netbox_create_interface_for_device_type(nb_obj, netbox_device_type_id, network_interface, nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][network_interface]['type'])

            if not netbox_interface_templates_id:
                raise ValueError(f"Unable to create interface-type {nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][network_interface]['type']} (interface: {network_interface}) for device type id {netbox_device_type_id}")            

        # Create Device in NetBox
        netbox_device_id = netbox_create_device_for_proxmox_node(nb_url, app_config['netbox_api_config']['api_token'], proxmox_node, netbox_device_role_id, netbox_device_type_id, netbox_site_id, nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['serial'])

        if not netbox_device_id:
            raise ValueError(f"Netbox missing device id for {proxmox_node}, device type id {netbox_device_type_id}")

        device_interfaces = netbox_get_interfaces_for_proxmox_node_by_device_id(nb_obj, netbox_device_id)
    
        for device_interface in device_interfaces:
            if device_interface.name.startswith('vmbr'):
                continue

            print(f"device: {proxmox_node}, interface: {device_interface} {device_interface.type} {device_interface.mac_address}")

            netbox_update_interface_for_proxmox_node_by_device_id(nb_obj, netbox_device_id, device_interface, nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][device_interface.name])            

            # Create bridge interface name: vmbrX, bridge: device_interface.id
            vmbr_info = get_proxmox_node_vmbr_network_interface_mapping(app_config['proxmox_api_config'], proxmox_node, device_interface.name)

            if vmbr_info:
                if device_interface.name in vmbr_info:
                    vmbrX_interface = netbox_create_vmbrX_interface_mapping(nb_obj, netbox_device_id, nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][device_interface.name]['type'], device_interface.id, vmbr_info[device_interface.name])
                    vmbrX_interface_details = dict(vmbrX_interface)

                    if not 'id' in vmbrX_interface_details:
                        raise ValueError(f"'id' missing for interface {vmbr_info[device_interface.name]} on {proxmox_node}")

                    if 'ipv4address' in nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][vmbrX_interface_details['display']]:
                        #print(f"Assigning {nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][vmbrX_interface_details['display']]['ipv4address']} to {vmbrX_interface_details['display']} on {proxmox_node}")                        
                        netbox_create_and_assign_ip_address(nb_obj, nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][vmbrX_interface_details['display']]['ipv4address'], vmbrX_interface_details['id'])
            else:
                if 'ipv4address' in nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][device_interface.name]:
                    #print(f"Assigning {nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][device_interface.name]['ipv4address']} to {device_interface.name} on {proxmox_node}")                        
                    netbox_create_and_assign_ip_address(nb_obj, nb_pxmx_cluster.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][device_interface.name]['ipv4address'], device_interface.id)

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
