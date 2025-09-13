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

from helpers.netbox_proxmox_api import NetBoxProxmoxAPIHelper
from helpers.netbox_objects import Netbox, NetBoxTags, NetBoxDeviceRoles, NetboxClusterTypes, NetboxClusters, NetboxVirtualMachines, NetboxVirtualMachineInterface, NetboxIPAddresses

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


def get_proxmox_cluster_info(proxmox_api_config: dict):
    proxmox_cluster_name = None
    proxmox_nodes = {}

    try:
        proxmox = ProxmoxAPI(
            proxmox_api_config['api_host'],
            port=proxmox_api_config['api_port'],
            user=proxmox_api_config['api_user'],
            token_name=proxmox_api_config['api_token_id'],
            token_value=proxmox_api_config['api_token_secret'],
            verify_ssl=False
        )

        proxmox_cluster_status = proxmox.cluster.status.get()

        # Extract all 'type' values for 'cluster' (should only be 1)
        proxmox_cluster_info = list(filter(lambda d: d["type"] == 'cluster', proxmox_cluster_status))

        if proxmox_cluster_info:
            proxmox_cluster_name = proxmox_cluster_info[0]['name']

        # Extract all values for type 'nodes'
        proxmox_node_info = list(filter(lambda d: d["type"] == 'node', proxmox_cluster_status))

        if proxmox_node_info:
            for pm_node in proxmox_node_info:
                if pm_node['type'] == 'node':
                    if not pm_node['name'] in proxmox_nodes:
                        proxmox_nodes[pm_node['name']] = {}
                    
                    proxmox_nodes[pm_node['name']]['ip'] = pm_node['ip']
                    proxmox_nodes[pm_node['name']]['online'] = pm_node['online']

        return (proxmox_cluster_name, proxmox_nodes)
    except ResourceException as e:
        #raise(e)
        print("E", e, dir(e), e.status_code, e.status_message, e.errors)
        if e.errors:
            if 'vmid' in e.errors:
                print("F", e.errors['vmid'])

    return None
    

def generate_proxmox_node_creds_configuration(proxmox_nodes: dict):
    temp_nodes_cn_info = {}

    # test nodes data
    # PMCI 1 {'pxmx-n2': {'ip': '192.168.71.4', 'login': 'root', 'use_pass': False}, 'pxmx-n1': {'ip': '192.168.71.3', 'login': 'root', 'use_pass': False}}
    for proxmox_node in proxmox_nodes:
        if not proxmox_node in temp_nodes_cn_info:
            temp_nodes_cn_info[proxmox_node] = {}

        temp_nodes_cn_info[proxmox_node]['ip'] = proxmox_nodes[proxmox_node]['ip']

        if not proxmox_nodes[proxmox_node]['online']:
            print(f"Proxmox node {proxmox_node} is not online.  Skipping...")
            continue

        while True:
            login_name = input(f"Enter login name for {proxmox_node}: ")
            if login_name:
                break

        temp_nodes_cn_info[proxmox_node]['login'] = login_name

        while True:
            use_ssh_pass = input(f"Is password for {login_name} required for {proxmox_node}? ")
            if use_ssh_pass and use_ssh_pass.lower() in ('y', 'yes', 'n', 'no'):
                break

        if use_ssh_pass.lower().startswith('y'):
            while True:
                ssh_pass = getpass.getpass(f"Enter password for {login_name} on {proxmox_node}: ")
                if ssh_pass:
                    break
            temp_nodes_cn_info[proxmox_node]['use_pass'] = True
            temp_nodes_cn_info[proxmox_node]['pass'] = ssh_pass
        elif use_ssh_pass.lower().startswith('n'):
            temp_nodes_cn_info[proxmox_node]['use_pass'] = False

        if login_name != "root":
            temp_nodes_cn_info[proxmox_node]['use_sudo'] = True

            while True:
                sudo_pass_required = input(f"Does sudo require a password? ")
                if sudo_pass_required and sudo_pass_required.lower() in ('y', 'yes', 'n', 'no'):
                    break

            if sudo_pass_required.lower().startswith('y'):
                while True:
                    sudo_pass = getpass.getpass(f"Enter sudo password for {login_name} on {proxmox_node['name']}: ")
                    if sudo_pass:
                        break
                temp_nodes_cn_info[proxmox_node]['sudo_pass'] = sudo_pass

    return temp_nodes_cn_info


def _get_proxmox_node_info_cmd(proxmox_node_name:str, proxmox_node_login_info: dict, lshw_command: str):
    do_get_pty = False
    output = None
    error = None

    # Create an SSH client instance
    client = paramiko.SSHClient()

    # Set policy for handling unknown host keys (AutoAddPolicy for convenience, RejectPolicy for security in production)
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Connect to the server
    try:
        if not 'login' in proxmox_node_login_info:
            raise ValueError("'login' field missing in proxmox_node_login_info")
        
        if 'use_pass' in proxmox_node_login_info and proxmox_node_login_info['use_pass'] and not 'pass' in proxmox_node_login_info:
            raise ValueError("'pass' field missing in proxmox_node_login_info")

        if proxmox_node_login_info['login'] != 'root' and (not 'use_sudo' in proxmox_node_login_info and not proxmox_node_login_info['use_sudo']):
            raise ValueError("'use_sudo' field missing or set to False in proxmox_node_login_info")

        # Execute a command
        if proxmox_node_login_info['login'] != 'root' and proxmox_node_login_info['use_sudo']:
            lshw_command = f"sudo {lshw_command}"

        if 'sudo_pass' in proxmox_node_login_info and proxmox_node_login_info['sudo_pass']:
            do_get_pty = True

        if 'use_pass' in proxmox_node_login_info and proxmox_node_login_info['use_pass']:
            client.connect(proxmox_node_name, username=proxmox_node_login_info['login'], password=proxmox_node_login_info['pass'])
        else:
            client.connect(proxmox_node_name, username=proxmox_node_login_info['login'])

        stdin, stdout, stderr = client.exec_command(lshw_command, get_pty=do_get_pty)

        if 'sudo_pass' in proxmox_node_login_info and proxmox_node_login_info['sudo_pass']:
            stdin.write(proxmox_node_login_info['sudo_pass'] + '\n')
            stdin.flush()

        # Read the output
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
    except paramiko.AuthenticationException:
        print("Authentication failed. Check username and password or SSH keys.")
    except paramiko.SSHException as e:
        print(f"SSH connection error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        # Close the connection
        client.close()

    return output, error


def proxmox_node_lshw_test(proxmox_node_name:str, proxmox_node_login_info: dict, lshw_command: str):
    output, error = _get_proxmox_node_info_cmd(proxmox_node_name, proxmox_node_login_info, lshw_command)
    return output, error


def get_proxmox_node_system_information(proxmox_node_name:str, proxmox_node_login_info: dict, dmidecode_command: str):
    temp_system_info = {}
    
    dmidecode_command = f"{dmidecode_command} -t system"
    output, error = _get_proxmox_node_info_cmd(proxmox_node_name, proxmox_node_login_info, dmidecode_command)

    sys_info_lines = output.split('\n')

    for sys_info_line in sys_info_lines:
        if sys_info_line == "":
            continue

        if ':' in sys_info_line:
            key, val = sys_info_line.split(':')
            key = key.lower().lstrip().replace(' ', '_')
            val = val.lstrip()

            if key in ('manufacturer', 'product_name', 'serial_number'):
                temp_system_info[key] = val

    if error:
        raise ValueError(error)

    try:
        return json.loads(json.dumps(temp_system_info))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON conversion error: {e}")


def get_proxmox_node_network_interfaces(proxmox_node_name:str, proxmox_node_login_info: dict, lshw_command: str):
    lshw_command = f"{lshw_command} -class network -json"
    output, error = _get_proxmox_node_info_cmd(proxmox_node_name, proxmox_node_login_info, lshw_command)

    if error:
        raise ValueError(error)
    
    try:
        return json.loads(output)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON conversion error: {e}")    


def get_proxmox_node_ethtool_info(proxmox_node_name:str, proxmox_node_login_info: dict, ethtool_command: str):
    ethtool_settings = {}
    tmp_ethtool_settings = {}

    output, error = _get_proxmox_node_info_cmd(proxmox_node_name, proxmox_node_login_info, ethtool_command)
    
    if error:
        raise ValueError(error)

    lines = output.split('\n')

    for line in lines:
        if line == "":
            continue

        if ':' in line:
            key, val = line.split(':')
            key = key.strip().lower().replace(' ', '_')
            key = key.strip().lower().replace('-', '_')

            if val != "":
                ethtool_settings[key] = val.lstrip()
        else:
            ethtool_settings[key] += re.sub(r'\s+', ' ', line)

    for parsed_line in ethtool_settings:
        if parsed_line.endswith('link_modes'):
            ethtool_settings[parsed_line] = ethtool_settings[parsed_line].split(' ')

    if 'supported_ports' in ethtool_settings:
        ethtool_settings['port'] = ethtool_settings.pop('supported_ports')

    if 'auto_negotiation' in ethtool_settings:
        if ethtool_settings['auto_negotiation'] == 'on':
            ethtool_settings['duplex'] = 'Auto'

    return ethtool_settings


def main():
    proxmox_cluster_name = None
    proxmox_nodes = []
    proxmox_nodes_connection_info = {}
    discovered_proxmox_nodes_information = {}

    network_interface_enabled_state_mappings = {
        'yes': True,
        'no': False
    }

    ethtool_to_netbox_speed_mappings = {
        'supported_ports': {
            '[ TP ]': 'twisted pair'
        },
        'twisted pair': {
            '1000baseT': '1gbase-t',
            '2500baseT': '2.5gbase-t'
        }
    }

    args = get_arguments()
    print("ARGS", args, args.config)

    try:
        with open(args.config, 'r') as cfg_f:
            app_config = yaml.safe_load(cfg_f)
    except yaml.YAMLError as exc:
        print(exc)

    print("CFG DATA", app_config, app_config['proxmox_api_config'])

    nb_url = f"{app_config['netbox_api_config']['api_proto']}://{app_config['netbox_api_config']['api_host']}:{str(app_config['netbox_api_config']['api_port'])}/"
    nb_obj = Netbox(nb_url, app_config['netbox_api_config']['api_token'], None)
    print(nb_obj, dir(nb_obj))

    proxmox_cluster_name, proxmox_nodes = get_proxmox_cluster_info(app_config['proxmox_api_config'])
    print("PMCI", proxmox_cluster_name, proxmox_nodes)

    if not proxmox_cluster_name:
        proxmox_cluster_name = f"proxmox-cluster-name-placeholder-{str(int(time.time()))}"

    print(proxmox_cluster_name)

    # Collect Proxmox node login information
    proxmox_nodes_connection_info = generate_proxmox_node_creds_configuration(proxmox_nodes)

    # discover nodes base system information
    for pnci in proxmox_nodes_connection_info:
        system_info = get_proxmox_node_system_information(proxmox_nodes_connection_info[pnci]['ip'], proxmox_nodes_connection_info[pnci], app_config['proxmox']['node_commands']['dmidecode_command'])

        # raw output
        # {'manufacturer': 'Protectli', 'product_name': 'VP2430', 'serial_number': 'Default string'} 3
        print(system_info, len(system_info))
        print(system_info['manufacturer'], system_info['product_name'], system_info['serial_number'])
        
        if not pnci in discovered_proxmox_nodes_information:
            discovered_proxmox_nodes_information[pnci] = {}
            discovered_proxmox_nodes_information[pnci]['system'] = {}
            discovered_proxmox_nodes_information[pnci]['system']['network_interfaces'] = []
        
        discovered_proxmox_nodes_information[pnci]['system']['manufacturer'] = system_info['manufacturer']
        discovered_proxmox_nodes_information[pnci]['system']['model'] = system_info['product_name']
        discovered_proxmox_nodes_information[pnci]['system']['serial'] = system_info['serial_number']

    # discover nodes network interfaces information
    for pnci in proxmox_nodes_connection_info:
        ni_info = get_proxmox_node_network_interfaces(proxmox_nodes_connection_info[pnci]['ip'], proxmox_nodes_connection_info[pnci], app_config['proxmox']['node_commands']['lshw_command'])

        # raw output
        # [{'id': 'pxmx-n1', 'class': 'system', 'claimed': True, 'handle': 'DMI:0001', 'description': 'Desktop Computer', 'product': 'VP2430 (VP2430)', 'vendor': 'Protectli', 'version': '1.00', 'serial': 'Default string', 'width': 64, 'configuration': {'boot': 'normal', 'chassis': 'desktop', 'family': 'Vault Pro', 'sku': 'VP2430', 'uuid': '03000200-0400-0500-0006-000700080009'}, 'capabilities': {'smbios-3.6.0': 'SMBIOS version 3.6.0', 'dmi-3.6.0': 'DMI version 3.6.0', 'smp': 'Symmetric Multi-Processing', 'vsyscall32': '32-bit processes'}}, {'id': 'pnp00:00', 'class': 'system', 'claimed': True, 'product': 'PnP device PNP0c02', 'physid': '0', 'configuration': {'driver': 'system'}, 'capabilities': {'pnp': True}}, {'id': 'pnp00:03', 'class': 'system', 'claimed': True, 'product': 'PnP device PNP0c02', 'physid': '3', 'configuration': {'driver': 'system'}, 'capabilities': {'pnp': True}}, {'id': 'pnp00:04', 'class': 'system', 'claimed': True, 'product': 'PnP device PNP0c02', 'physid': '4', 'configuration': {'driver': 'system'}, 'capabilities': {'pnp': True}}, {'id': 'pnp00:05', 'class': 'system', 'claimed': True, 'product': 'PnP device PNP0c02', 'physid': '5', 'configuration': {'driver': 'system'}, 'capabilities': {'pnp': True}}, {'id': 'pnp00:06', 'class': 'system', 'claimed': True, 'product': 'PnP device PNP0c02', 'physid': '6', 'configuration': {'driver': 'system'}, 'capabilities': {'pnp': True}}, {'id': 'pnp00:07', 'class': 'system', 'claimed': True, 'product': 'PnP device PNP0c02', 'physid': '7', 'configuration': {'driver': 'system'}, 'capabilities': {'pnp': True}}]
        print(ni_info, len(ni_info))

        for ni in ni_info:
            if not 'logicalname' in ni:
                continue

            temp_h = {
                'name': ni['logicalname'],
                'mac': ni['serial'],
                'enabled': network_interface_enabled_state_mappings[ni['configuration']['link']]
            }

            if network_interface_enabled_state_mappings[ni['configuration']['link']]:
                full_et_cmd_out = f"{app_config['proxmox']['node_commands']['ethtool_command']} {ni['logicalname']}"
                ethtool_info = get_proxmox_node_ethtool_info(proxmox_nodes_connection_info[pnci]['ip'], proxmox_nodes_connection_info[pnci], full_et_cmd_out)

                # need last supported_link_modes for type mapping
                if ethtool_info['port'] in ethtool_to_netbox_speed_mappings['supported_ports']:
                    if_type = ethtool_to_netbox_speed_mappings['supported_ports'][ethtool_info['port']]
                    max_interface_link_mode = ethtool_info['supported_link_modes'][-1].split('/')[0]
                    if_type_speed = ethtool_to_netbox_speed_mappings[if_type][max_interface_link_mode]
                    temp_h['type'] = if_type_speed

            discovered_proxmox_nodes_information[pnci]['system']['network_interfaces'].append(temp_h)

    # sample output
    # {'pxmx-n2': {'system': {'network_interfaces': [{'name': 'enp1s0', 'mac': '64:62:66:23:bf:03', 'enabled': True, 'type': '1000BASE-T (1GE)'}, {'name': 'enp2s0', 'mac': '64:62:66:23:bf:04', 'enabled': True, 'type': '2.5GBASE-T (2.5GE)'}, {'name': 'enp3s0', 'mac': '64:62:66:23:bf:05', 'enabled': False, 'type': '2.5GBASE-T (2.5GE)'}, {'name': 'enp4s0', 'mac': '64:62:66:23:bf:06', 'enabled': False, 'type': '2.5GBASE-T (2.5GE)'}], 'manufacturer': 'Protectli', 'model': 'VP2430 (VP2430)', 'serial': 'Default string'}}, 'pxmx-n1': {'system': {'network_interfaces': [{'name': 'enp1s0', 'mac': '64:62:66:23:bf:13', 'enabled': True, 'type': '1000BASE-T (1GE)'}, {'name': 'enp2s0', 'mac': '64:62:66:23:bf:14', 'enabled': True, 'type': '2.5GBASE-T (2.5GE)'}, {'name': 'enp3s0', 'mac': '64:62:66:23:bf:15', 'enabled': False, 'type': '2.5GBASE-T (2.5GE)'}, {'name': 'enp4s0', 'mac': '64:62:66:23:bf:16', 'enabled': False, 'type': '2.5GBASE-T (2.5GE)'}], 'manufacturer': 'Protectli', 'model': 'VP2430 (VP2430)', 'serial': 'Default string'}}}
    print(discovered_proxmox_nodes_information)

    # create cluster and type in NetBox

    # create nodes in NetBox and associate with cluster


if __name__ == "__main__":
    main()
