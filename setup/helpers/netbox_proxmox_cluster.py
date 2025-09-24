import re
import getpass
import json
import paramiko
import pynetbox
import proxmoxer
import requests
import time
import urllib
import urllib.parse

from proxmoxer import ProxmoxAPI, ResourceException
from . proxmox_api_common import ProxmoxAPICommon

class NetBoxProxmoxCluster(ProxmoxAPICommon):
    def __init__(self, cfg_data: dict, netbox_api_obj: object):
        super(NetBoxProxmoxCluster, self).__init__(cfg_data)

        self.cfg_data = cfg_data
        self.netbox_api = netbox_api_obj
        self.discovered_proxmox_nodes_information = {}


    def get_proxmox_cluster_info(self):
        self.proxmox_cluster_name = None
        self.proxmox_nodes = {}

        try:
            proxmox_cluster_status = self.proxmox_api.cluster.status.get()

            # Extract all 'type' values for 'cluster' (should only be 1)
            proxmox_cluster_info = list(filter(lambda d: d["type"] == 'cluster', proxmox_cluster_status))

            if proxmox_cluster_info:
                self.proxmox_cluster_name = proxmox_cluster_info[0]['name']
            else:
                self.proxmox_cluster_name = f"netbox-proxmox-automation-cluster-{str(int(time.time()))}"

            # Extract all values for type 'nodes'
            proxmox_node_info = list(filter(lambda d: d["type"] == 'node', proxmox_cluster_status))

            if proxmox_node_info:
                for pm_node in proxmox_node_info:
                    if pm_node['type'] == 'node':
                        if not pm_node['name'] in self.proxmox_nodes:
                            self.proxmox_nodes[pm_node['name']] = {}
                        
                        self.proxmox_nodes[pm_node['name']]['ip'] = pm_node['ip']
                        self.proxmox_nodes[pm_node['name']]['online'] = pm_node['online']
        except ResourceException as e:
            #raise(e)
            print("E", e, dir(e), e.status_code, e.status_message, e.errors)
            if e.errors:
                if 'vmid' in e.errors:
                    print("F", e.errors['vmid'])


    def generate_proxmox_node_creds_configuration(self):
        temp_nodes_cn_info = {}

        # test nodes data
        # PMCI 1 {'pxmx-n2': {'ip': '192.168.71.4', 'login': 'root', 'use_pass': False}, 'pxmx-n1': {'ip': '192.168.71.3', 'login': 'root', 'use_pass': False}}
        for proxmox_node in self.proxmox_nodes:
            if not proxmox_node in temp_nodes_cn_info:
                temp_nodes_cn_info[proxmox_node] = {}

            temp_nodes_cn_info[proxmox_node]['ip'] = self.proxmox_nodes[proxmox_node]['ip']

            if not self.proxmox_nodes[proxmox_node]['online']:
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

        self.proxmox_nodes_connection_info = temp_nodes_cn_info


    def __get_proxmox_node_info_cmd(self, proxmox_node_info: dict, run_command: str):
        do_get_pty = False
        output = None
        error = None

        # Create an SSH client instance
        client = paramiko.SSHClient()

        # Set policy for handling unknown host keys (AutoAddPolicy for convenience, RejectPolicy for security in production)
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the server
        try:
            if not 'login' in proxmox_node_info:
                raise ValueError("'login' field missing in proxmox_node_info")
            
            if 'use_pass' in proxmox_node_info and proxmox_node_info['use_pass'] and not 'pass' in proxmox_node_info:
                raise ValueError("'pass' field missing in proxmox_node_login_info")

            if proxmox_node_info['login'] != 'root' and (not 'use_sudo' in proxmox_node_info and not proxmox_node_info['use_sudo']):
                raise ValueError("'use_sudo' field missing or set to False in proxmox_node_login_info")

            # Execute a command
            if proxmox_node_info['login'] != 'root' and proxmox_node_info['use_sudo']:
                run_command = f"sudo {run_command}"

            if 'sudo_pass' in proxmox_node_info and proxmox_node_info['sudo_pass']:
                do_get_pty = True

            if 'use_pass' in proxmox_node_info and proxmox_node_info['use_pass']:
                client.connect(proxmox_node_info['ip'], username=proxmox_node_info['login'], password=proxmox_node_info['pass'])
            else:
                client.connect(proxmox_node_info['ip'], username=proxmox_node_info['login'])

            stdin, stdout, stderr = client.exec_command(run_command, get_pty=do_get_pty)

            if 'sudo_pass' in proxmox_node_info and proxmox_node_info['sudo_pass']:
                stdin.write(proxmox_node_info['sudo_pass'] + '\n')
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


    def get_proxmox_nodes_system_information(self):
        dmidecode_command = f"{self.cfg_data['proxmox']['node_commands']['dmidecode_command']} -t system"

        for proxmox_node in self.proxmox_nodes_connection_info:
            temp_system_info = {}

            if not proxmox_node in self.discovered_proxmox_nodes_information:
                self.discovered_proxmox_nodes_information[proxmox_node] = {}

            output, error = self.__get_proxmox_node_info_cmd(self.proxmox_nodes_connection_info[proxmox_node], dmidecode_command)

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
                if not 'system' in self.discovered_proxmox_nodes_information[proxmox_node]:
                    self.discovered_proxmox_nodes_information[proxmox_node]['system'] = {}

                self.discovered_proxmox_nodes_information[proxmox_node]['system'] = json.loads(json.dumps(temp_system_info))
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON conversion error: {e}")        


    def proxmox_node_lshw_test(self, proxmox_node_name: str, proxmox_node_login_info: dict):
        lshw_command = self.cfg_data['proxmox']['node_commands']['lshw_command']
        output, error = self.__get_proxmox_node_info_cmd(proxmox_node_name, proxmox_node_login_info, lshw_command)
        return output, error


    def get_proxmox_nodes_network_interfaces(self):
        lshw_command = f"{self.cfg_data['proxmox']['node_commands']['lshw_command']} -class network -json"

        network_interface_enabled_states = {
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

        for proxmox_node in self.proxmox_nodes_connection_info:
            if not 'network_interfaces' in self.discovered_proxmox_nodes_information[proxmox_node]['system']:
                self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'] = {}

            output, error = self.__get_proxmox_node_info_cmd(self.proxmox_nodes_connection_info[proxmox_node], lshw_command)

            if error:
                raise ValueError(error)
            
            try:
                interface_number = 0

                for interface in json.loads(output):
                    if 'id' in interface and interface['id'] == 'network':
                        if not 'logicalname' in interface:
                            continue

                        if not interface['logicalname'] in self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces']:
                            self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][interface['logicalname']] = {}

                        if interface_number == 0:
                            if self.discovered_proxmox_nodes_information[proxmox_node]['system']['manufacturer'].lower() == 'protectli':
                                if self.discovered_proxmox_nodes_information[proxmox_node]['system']['serial_number'].lower().startswith('defau'):
                                    self.discovered_proxmox_nodes_information[proxmox_node]['system']['serial_number'] = interface['serial'].lower().replace(':', '-')
                                    self.discovered_proxmox_nodes_information[proxmox_node]['system']['serial'] = self.discovered_proxmox_nodes_information[proxmox_node]['system'].pop('serial_number')
                            
                        self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][interface['logicalname']]['mac'] = interface['serial']
                        self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][interface['logicalname']]['enabled'] = network_interface_enabled_states[interface['configuration']['link']]

                        ethtool_info = self.__get_proxmox_node_ethtool_info(self.proxmox_nodes_connection_info[proxmox_node], interface['logicalname'])

                        self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][interface['logicalname']]['duplex'] = ethtool_info['duplex']
                        
                        # need last supported_link_modes for type mapping
                        if ethtool_info['port'] in ethtool_to_netbox_speed_mappings['supported_ports']:
                            if_type = ethtool_to_netbox_speed_mappings['supported_ports'][ethtool_info['port']]
                            max_interface_link_mode = ethtool_info['supported_link_modes'][-1].split('/')[0]
                            if_type_speed = ethtool_to_netbox_speed_mappings[if_type][max_interface_link_mode]
                            self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][interface['logicalname']]['type'] = if_type_speed

                    interface_number += 1
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON conversion error: {e}")            

            try:
                interfaces_ip_addresses = self.__get_proxmox_node_ip_addresses(self.proxmox_nodes_connection_info[proxmox_node])
                for interfaces_ip_address in interfaces_ip_addresses:
                    if interfaces_ip_address in self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'] or interfaces_ip_address.startswith('vmbr'):
                        if interfaces_ip_address.startswith('vmbr'):
                            if not interfaces_ip_address in self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces']:
                                self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][interfaces_ip_address] = {}

                        self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][interfaces_ip_address]['ipv4address'] = interfaces_ip_addresses[interfaces_ip_address]['ipv4address']
                        self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][interfaces_ip_address]['ipv6address'] = interfaces_ip_addresses[interfaces_ip_address]['ipv6address']
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON conversion error: {e}")            


    def __get_proxmox_node_ip_addresses(self, proxmox_node_info: dict):
        proxmox_node_ip_addresses = {}
        ip_command = f"{self.cfg_data['proxmox']['node_commands']['ipaddr_command']}"

        output, error = self.__get_proxmox_node_info_cmd(proxmox_node_info, ip_command)

        if error:
            raise ValueError(error)

        output_lines = output.split('\n')

        for output_line in output_lines:
            if output_line == "":
                continue

            if_parts = ' '.join(output_line.split()).split(' ')

            if len(if_parts) == 4 or len(if_parts) == 5:
                if if_parts[0] != 'lo':
                    proxmox_node_ip_addresses[if_parts[0]] = {
                        'ipv4address': if_parts[2],
                        'ipv6address': if_parts[-1],
                    }
        try:
            return json.loads(json.dumps(proxmox_node_ip_addresses))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON conversion error: {e}")    


    def __get_proxmox_node_ethtool_info(self, proxmox_node_info: dict, network_interface: str):
        ethtool_settings = {}
        ethtool_command = f"{self.cfg_data['proxmox']['node_commands']['ethtool_command']} {network_interface}"
        output, error = self.__get_proxmox_node_info_cmd(proxmox_node_info, ethtool_command)
        
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

        ethtool_settings['duplex'] = ethtool_settings['duplex'].lower()
        return ethtool_settings


