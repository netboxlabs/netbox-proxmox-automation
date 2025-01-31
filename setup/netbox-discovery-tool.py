#!/usr/bin/env python3

import os, sys, re
import argparse
import yaml
import json
import pynetbox
import proxmoxer

from helpers.netbox_proxmox_api import NetBoxProxmoxAPIHelper
from helpers.netbox_objects import Netbox, NetBoxTags, NetBoxDeviceRoles, NetboxClusterTypes, NetboxClusters, NetboxVirtualMachines, NetboxVirtualMachineInterface, NetboxIPAddresses

nb_obj = None

proxmox_to_netbox_vm_status_mappings = {
    False: 'offline',
    True: 'active'
}


# I think that what we want is ./netbox-proxmox-discovery.py (vms|lxc) --config <whatever>
def get_arguments():
    # Initialize the parser
    parser = argparse.ArgumentParser(description="Import Netbox and Proxmox Configurations")

    # Add arguments for URL and Token
    sub_parser = parser.add_subparsers(dest='virt_type',
                                       required=True,
                                       description='Proxmox virtualization types',
                                       help='additional help')

    vms_action = sub_parser.add_parser('vm', help='vm help action')
    vms_action.add_argument("--config", required=True, help="YAML file containing the configuration")

    lxc_action = sub_parser.add_parser('lxc', help='lxc help action')
    lxc_action.add_argument("--config", required=True, help="YAML file containing the configuration")

    # Parse the arguments
    args = parser.parse_args()

    # Return the parsed arguments
    return args


def __netbox_make_slug(in_str):
    return re.sub(r'\W+', '-', in_str).lower()


def netbox_get_vms(nb_obj = None):
    nb_vm_info = {}

    try:
        for each_nb_vm in list(nb_obj.nb.virtualization.virtual_machines.all()):
            each_nb_vm_info = dict(each_nb_vm)

            if not each_nb_vm_info['name'] in nb_vm_info:
                nb_vm_info[each_nb_vm_info['name']] = {}

            nb_vm_info[each_nb_vm_info['name']]['is_proxmox_vm'] = False

            if each_nb_vm_info['custom_fields']['proxmox_vmid']:
                nb_vm_info[each_nb_vm_info['name']]['is_proxmox_vm'] = True
                nb_vm_info[each_nb_vm_info['name']]['id'] = int(each_nb_vm_info['custom_fields']['proxmox_vmid'])
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)

    return nb_vm_info


def netbox_create_proxmox_discovered_object_tags(nb_obj = None, tag_name = None):
    try:
        nb_obj.nb.extras.tags.create([{'name': tag_name, 'slug': __netbox_make_slug(tag_name)}])
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)


def netbox_create_vm(nb_url = None, nb_api_token = None, proxmox_cluster_name = None, vm_configuration = {}, vm_name = None, vm_role_id = 0, tag_id = 0):
    try:
        create_vm_config = {
            'name': vm_name,
            'cluster': dict(NetboxClusters(nb_url, nb_api_token, {'name': proxmox_cluster_name}).obj)['id'],
            'vcpus': str(vm_configuration['vcpus']),
            'memory': vm_configuration['memory'],
            'role': vm_role_id,
            'status': proxmox_to_netbox_vm_status_mappings[vm_configuration['running']],
            #'tags': [str(tag_id)]
        }

        if tag_id > 0:
            create_vm_config['tags'] = [str(tag_id)]

        if not 'custom_fields' in create_vm_config:
            create_vm_config['custom_fields'] = {}

        if proxmox_to_netbox_vm_status_mappings[vm_configuration['running']]:
            if 'node' in vm_configuration:
                create_vm_config['custom_fields']['proxmox_node'] = vm_configuration['node']

            if 'public_ssh_key' in vm_configuration:
                create_vm_config['custom_fields']['proxmox_public_ssh_key'] = vm_configuration['public_ssh_key']

            if 'storage' in vm_configuration:
                create_vm_config['custom_fields']['proxmox_vm_storage'] = vm_configuration['storage']

            if 'vmid' in vm_configuration:
                create_vm_config['custom_fields']['proxmox_vmid'] = vm_configuration['vmid']

            if 'is_lxc' in vm_configuration:
                print("YES LXC", vm_name)
                create_vm_config['custom_fields']['proxmox_is_lxc_container'] = True
            else:
                print("NO LXC", vm_name)
                create_vm_config['custom_fields']['proxmox_is_lxc_container'] = False

        #print("NB VM CONFIG", create_vm_config)
        """
        NB VM CONFIG {'name': 'u2004-client1', 'cluster': 1, 'vcpus': '1', 'memory': '512', 'status': 'active',
        'tags': ['2'],
        'custom_fields': {'proxmox_node': 'proxmox-ve', 'proxmox_public_ssh_key': 'ssh-rsa AAAAB3N...0QiC6e51 identity-proxmox-vm', 'proxmox_vm_storage': 'local-lvm', 'proxmox_vmid': '6382'}}        
        """
        nb_created_vm = NetboxVirtualMachines(nb_url, nb_api_token, create_vm_config)
        nb_created_vm_id = dict(nb_created_vm.obj)['id']
        #print("CREATED NB VM", nbc_vm, nb_created_vm_id, vm_configuration)
        """
        CREATED NB VM <helpers.netbox_objects.NetboxVirtualMachines object at 0x105a3b5d0> 274
        {'vcpus': 1, 'memory': '512', 'running': True, 'node': 'proxmox-ve', 'vmid': '6382',
        'public_ssh_key': 'ssh-rsa AAAAB3N...PY0QiC6e51 identity-proxmox-vm',
        'bootdisk': 'scsi0', 'storage': 'local-lvm',
        'disks': [{'scsi0': '20480'}],
        'network_interfaces': {'eth0': {'mac-address': 'bc:24:11:3e:76:51',
                                       'ip-addresses': [{'type': 'ipv4', 'ip-address': '192.168.80.11/24'}, 
                                                        {'type': 'ipv6', 'ip-address': 'fe80::be24:11ff:fe3e:7651/64'}]}}}
        """

        if 'network_interfaces' in vm_configuration:
            for network_interface in vm_configuration['network_interfaces']:
                #print(f"******** CREATE NETWORK INTERFACE INFO {vm_name}: {nb_created_vm_id} {network_interface}")
                network_interface_id = __netbox_create_vm_network_interface(nb_url, nb_api_token, nb_created_vm_id, network_interface, vm_configuration['network_interfaces'][network_interface]['mac-address'])

                for ip_address_entry in vm_configuration['network_interfaces'][network_interface]['ip-addresses']:
                    #print(f"IP ADDRESS ENTRY: {ip_address_entry} ---> {ip_address_entry['ip-address']}")
                    ip_address_id = __netbox_vm_network_interface_assign_ip_address(nb_url, nb_api_token, network_interface_id, ip_address_entry['ip-address'])

                    if network_interface == 'eth0' or network_interface == 'net0':
                        if not ip_address_entry['ip-address'].endswith('/64'):
                            __netbox_vm_network_interface_assign_primary_ip4_address(vm_name, network_interface_id, ip_address_entry['ip-address'])

        if 'disks' in vm_configuration:
            for vm_disk in vm_configuration['disks']:
                __netbox_vm_create_disk(vm_name, vm_disk['disk_name'], vm_disk['disk_size'], vm_disk['proxmox_disk_storage_volume'])
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)


def __netbox_create_vm_network_interface(nb_url = None, nb_api_token = None, netbox_vm_id = 0, vm_network_interface_name = None, vm_network_interface_mac_address = None):
    try:
        print(f"Going to create network interface {vm_network_interface_name} on {netbox_vm_id}")

        nb_vm_create_interface_payload = {
            'virtual_machine': str(netbox_vm_id),
            'name': vm_network_interface_name,
            'mac_address': vm_network_interface_mac_address
        }

        #nb_create_vm_interface = NetboxVirtualMachineInterface(nb_url, nb_api_token, nb_vm_create_interface_payload)
        #nb_create_vm_interface_id = dict(nb_create_vm_interface.obj)['id']

        nb_create_vm_interface = nb_obj.nb.virtualization.interfaces.get(virtual_machine_id = netbox_vm_id, name = vm_network_interface_name, mac_address = vm_network_interface_mac_address)

        if not nb_create_vm_interface:
            nb_create_vm_interface = nb_obj.nb.virtualization.interfaces.create(nb_vm_create_interface_payload)
        
        nb_create_vm_interface_id = dict(nb_create_vm_interface)['id']

        return nb_create_vm_interface_id
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)


def __netbox_vm_network_interface_assign_ip_address(nb_url = None, nb_api_token = None, netbox_vm_network_interface_id = 0, ip_address = None):
    try:
        print(f"Going to assign IP address {ip_address} to {netbox_vm_network_interface_id}")

        nb_assign_ip_address_payload = {
            'address': ip_address,
            'status': 'active',
            'assigned_object_type': 'virtualization.vminterface',
            'assigned_object_id': str(netbox_vm_network_interface_id)
        }

        nb_assign_ip_address = NetboxIPAddresses(nb_url, nb_api_token, nb_assign_ip_address_payload, 'address')

        return nb_assign_ip_address
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)


def __netbox_vm_network_interface_assign_primary_ip4_address(vm_name = None, primary_network_interface_id = 0, ip_address = None):
    try:
        print(f"Setting primary network interface on VM {vm_name} to {primary_network_interface_id} {ip_address}")

        assigned_vm_obj = nb_obj.nb.virtualization.virtual_machines.get(name=vm_name)

        if assigned_vm_obj:
            found_ip_address = nb_obj.nb.ipam.ip_addresses.get(address = ip_address)
            assigned_vm_obj.primary_ip4 = dict(found_ip_address)['id']
            assigned_vm_obj.save()
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)


def __netbox_vm_create_disk(vm_name = None, disk_name = None, disk_size = 0, proxmox_disk_storage_volume = None):
    try:
        print(f"Adding virtual disk {disk_name} (vol: {proxmox_disk_storage_volume}) VM {vm_name}")

        assigned_vm_obj = nb_obj.nb.virtualization.virtual_machines.get(name=vm_name)
        assigned_disk_obj = nb_obj.nb.virtualization.virtual_disks.get(name=disk_name, virtual_machine=vm_name)

        if assigned_vm_obj and not assigned_disk_obj:
            nb_vm_id = dict(assigned_vm_obj)['id']

            virtual_disks_payload = {
                'virtual_machine': {
                    'name': vm_name,
                    'id': nb_vm_id
                },
                'name': disk_name,
                'size': int(disk_size),
                'custom_fields': {
                    'proxmox_disk_storage_volume': proxmox_disk_storage_volume
                }
            }

            created_vm_disk = nb_obj.nb.virtualization.virtual_disks.create(virtual_disks_payload)
            created_vm_disk_id = dict(created_vm_disk)['id']

            return created_vm_disk_id
    except pynetbox.RequestError as e:
        raise ValueError(e, e.error)


def main():
    global nb_obj

    args = get_arguments()

    # args.virt_type (vms, lxc)
    # args.config
    # print("ARGS", args)

    app_config_file = args.config

    with open(app_config_file) as yaml_cfg:
        try:
            app_config = yaml.safe_load(yaml_cfg)
        except yaml.YAMLError as exc:
            raise ValueError(exc)
        except IOError as ioe:
            raise ValueError(ioe)

    #print("APP CONFIG", app_config)
    #print("APP CONFIG NETBOX", app_config['netbox_api_config'])

    nb_url = f"{app_config['netbox_api_config']['api_proto']}://{app_config['netbox_api_config']['api_host']}:{str(app_config['netbox_api_config']['api_port'])}/"
    #print("NB URL", nb_url)
    nb_obj = Netbox(nb_url, app_config['netbox_api_config']['api_token'], None)
    #print("NB", nb_obj)

    # Collect all NetBox VMs, and for Proxmox VMs: VMIDs
    all_nb_vms = netbox_get_vms(nb_obj)
    #print(all_nb_vms)

    all_nb_vms_ids = {}

    for all_nb_vm in all_nb_vms:
        all_nb_vms_ids[all_nb_vms[all_nb_vm]['id']] = all_nb_vm

    pm = NetBoxProxmoxAPIHelper(app_config)

    if args.virt_type == 'vm':
        device_role_id = dict(NetBoxDeviceRoles(nb_url, app_config['netbox_api_config']['api_token'], {'name': app_config['netbox']['vm_role'], 'slug': __netbox_make_slug(app_config['netbox']['vm_role']), 'vm_role': True, 'color': 'ffbf00'}).obj)['id']

        proxmox_vm_configurations = pm.proxmox_get_vms_configurations()
        #print("HEY PM VMS", proxmox_vm_configurations)

        for proxmox_vm_configuration in proxmox_vm_configurations:
            #print("PXMXVMCFG", proxmox_vm_configuration, proxmox_vm_configurations[proxmox_vm_configuration])
            if not proxmox_vm_configuration in all_nb_vms and not pm.proxmox_vms[proxmox_vm_configuration]['vmid'] in all_nb_vms_ids:
                nbt_vm_discovered_id = dict(NetBoxTags(nb_url, app_config['netbox_api_config']['api_token'], {'name': 'proxmox-vm-discovered', 'slug': __netbox_make_slug('proxmox-vm-discovered'), 'color': 'aa1409'}).obj)['id']
            else:
                nbt_vm_discovered_id = 0

            netbox_create_vm(nb_url, app_config['netbox_api_config']['api_token'], app_config['proxmox']['cluster_name'], proxmox_vm_configurations[proxmox_vm_configuration], proxmox_vm_configuration, device_role_id, nbt_vm_discovered_id)
    elif args.virt_type == 'lxc':
        device_role_id = dict(NetBoxDeviceRoles(nb_url, app_config['netbox_api_config']['api_token'], {'name': app_config['netbox']['lxc_role'], 'slug': __netbox_make_slug(app_config['netbox']['lxc_role']), 'vm_role': True, 'color': 'ff9800'}).obj)['id']

        proxmox_lxc_configurations = pm.proxmox_get_lxc_configurations()

        for proxmox_lxc_configuration in proxmox_lxc_configurations:
            #print("PXMXVMCFG", proxmox_vm_configuration, proxmox_vm_configurations[proxmox_vm_configuration])
            if not proxmox_lxc_configuration in all_nb_vms and not pm.proxmox_lxc[proxmox_lxc_configuration]['vmid'] in all_nb_vms_ids:
                nbt_lxc_discovered_id = dict(NetBoxTags(nb_url, app_config['netbox_api_config']['api_token'], {'name': 'proxmox-lxc-discovered', 'slug': __netbox_make_slug('proxmox-lxc-discovered'), 'color': 'f44336'}).obj)['id']
            else:
                nbt_lxc_discovered_id = 0

            netbox_create_vm(nb_url, app_config['netbox_api_config']['api_token'], app_config['proxmox']['cluster_name'], proxmox_lxc_configurations[proxmox_lxc_configuration], proxmox_lxc_configuration, device_role_id, nbt_lxc_discovered_id)
    else:
        print(f"Unknown virtualizaton type {args.virt_type}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
