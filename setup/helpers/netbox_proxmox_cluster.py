import os, sys, re
import getpass
import json
import paramiko
import pynetbox
import proxmoxer
import requests
import urllib
import urllib.parse

from proxmoxer import ProxmoxAPI, ResourceException
from . proxmox_api_common import ProxmoxAPICommon

class NetBoxProxmoxCluster(ProxmoxAPICommon):
    def __init__(self, cfg_data: dict, options: dict):
        super(NetBoxProxmoxCluster, self).__init__(cfg_data, options)

        self.cfg_data = cfg_data
        self.discovered_proxmox_nodes_information = {}

        self.ssh_known_hosts_file = '~/.ssh/known_hosts'

        if 'ssh_known_hosts_file' in self.cfg_data['proxmox'] and 'proxmox' in self.cfg_data:
            self.ssh_known_hosts_file = self.cfg_data['proxmox']['ssh_known_hosts_file']


    def generate_proxmox_node_creds_configuration(self):
        temp_nodes_cn_info = {}

        # test nodes data
        # PMCI 1 {'pxmx-n2': {'ip': '192.168.71.4', 'login': 'root', 'use_pass': False}, 'pxmx-n1': {'ip': '192.168.71.3', 'login': 'root', 'use_pass': False}}
        for proxmox_node in sorted(self.proxmox_nodes):
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

        if self.debug:
            print("Proxmox nodes connection info")
            print(json.dumps(temp_nodes_cn_info, indent=4))
            print()

        self.proxmox_nodes_connection_info = temp_nodes_cn_info


    def __get_proxmox_node_info_cmd(self, proxmox_node_info: dict, run_command: str):
        do_get_pty = False
        output = None
        error = None

        # Create an SSH client instance
        client = paramiko.SSHClient()

        # Load ssh keys
        client.load_system_host_keys()

        if self.ssh_known_hosts_file.startswith('~'):
            self.ssh_known_hosts_file = os.path.expanduser(self.ssh_known_hosts_file)

        client.load_host_keys(self.ssh_known_hosts_file)

        # Set policy for handling unknown host keys (RejectPolicy for security)
        #client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #client.set_missing_host_key_policy(paramiko.RejectPolicy())

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

            if self.debug:
                print(f"SSH node run command '{run_command}' output")
                print(output)
                print()

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


    def simulate_get_proxmox_nodes_system_information(self):
        pm_nodes_sim_dir = './.simulate/proxmox_nodes'

        if not os.path.isdir(pm_nodes_sim_dir):
            raise ValueError(f"Unable to locate simulation directory for Proxmox nodes: {pm_nodes_sim_dir}")
        
        for item in os.listdir(pm_nodes_sim_dir):
            pm_nodes_subdir = f"{pm_nodes_sim_dir}/{item}"

            if os.path.isdir(pm_nodes_subdir):
                if not item in self.proxmox_nodes:
                    self.proxmox_nodes[item] = {}

            if not 'system' in self.proxmox_nodes[item]:
                self.proxmox_nodes[item]['system'] = {}

            json_system_file = f"{pm_nodes_subdir}/system.json"

            with open(json_system_file, 'r') as json_f:
                json_data = json.load(json_f)

            self.proxmox_nodes[item]['system'] = json_data


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

                if 'product_name' in temp_system_info:
                    temp_system_info['model'] = temp_system_info.pop('product_name')
                    
                self.discovered_proxmox_nodes_information[proxmox_node]['system'] = json.loads(json.dumps(temp_system_info))

                if self.debug:
                    print("Proxmox node system information")
                    print(json.dumps(temp_system_info, indent=4))
                    print()
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON conversion error: {e}")        


    def proxmox_node_lshw_test(self, proxmox_node_name: str, proxmox_node_login_info: dict):
        lshw_command = self.cfg_data['proxmox']['node_commands']['lshw_command']
        output, error = self.__get_proxmox_node_info_cmd(proxmox_node_name, proxmox_node_login_info, lshw_command)
        return output, error


    def get_proxmox_nodes_network_interfaces(self):
        ethtool_to_netbox_speed_mappings = {
            'supported_ports': {
                '[ TP ]': 'twisted pair'
            },
            'twisted pair': {
                '1000baseT': '1gbase-t',
                '2500baseT': '2.5gbase-t'
            }
        }

        try:            
            for proxmox_node in self.proxmox_nodes_connection_info:
                if not 'network_interfaces' in self.discovered_proxmox_nodes_information[proxmox_node]['system']:
                    self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'] = {}

                if self.debug:
                    print(f"PM NODE NI: {proxmox_node} ||| {self.proxmox_nodes_connection_info[proxmox_node]}")
                    
                node_network_info = self.proxmox_api.nodes(proxmox_node).network.get()

                if not node_network_info:
                    raise ValueError(f"Unable to finding network information for {proxmox_node}")

                interface_number = 0

                for ni in sorted(node_network_info, key=lambda item: item['iface']):
                    if not ni['iface'] in self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces']:
                        self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][ni['iface']] = {}

                    if not 'active' in ni:
                        ni['active'] = 0

                    self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][ni['iface']]['enabled'] = bool(ni['active'])

                    interface_mac_addr_cmd = f"/usr/bin/cat /sys/class/net/{ni['iface']}/address"
                    output, error = self.__get_proxmox_node_info_cmd(self.proxmox_nodes_connection_info[proxmox_node], interface_mac_addr_cmd)

                    if error:
                        print(f"\t\tSKIPPING: Unable to retrieve mac address for {ni['iface']} on {proxmox_node}: {error}", file=sys.stderr)
                        continue
                    
                    if self.debug:
                        print(f"Retrieved mac address for {ni['iface']} on {proxmox_node}: {output}")
                        print()
                    
                    self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][ni['iface']]['mac'] = output.rstrip()

                    if self.discovered_proxmox_nodes_information[proxmox_node]['system']['manufacturer'].lower() == 'protectli':
                        if interface_number == 0:
                            self.discovered_proxmox_nodes_information[proxmox_node]['system']['serial_number'] = output.rstrip().lower().replace(':', '-')

                    if 'bridge_ports' in ni:
                        self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][ni['iface']]['bridge_ports'] = ni['bridge_ports'].split(' ')[0]

                    if 'cidr' in ni:
                        self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][ni['iface']]['ipv4address'] = ni['cidr']

                    if 'cidr6' in ni:
                        self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][ni['iface']]['ipv6address'] = ni['cidr6']

                    if self.debug:
                        print("  NODE NETWORK INTERFACE", json.dumps(ni, indent=4), "\n", ni['iface'], ni['type'], ni['active'])

                    if bool(ni['active']) and not ni['iface'].startswith('vmbr'):
                        ethtool_info = self.__get_proxmox_node_ethtool_info(self.proxmox_nodes_connection_info[proxmox_node], ni['iface'])

                        if self.debug:
                            print(f"ethtool output")
                            print(ethtool_info)
                            print()

                        # need last supported_link_modes for type mapping
                        if ethtool_info['port'] in ethtool_to_netbox_speed_mappings['supported_ports']:
                            if_type = ethtool_to_netbox_speed_mappings['supported_ports'][ethtool_info['port']]
                            max_interface_link_mode = ethtool_info['supported_link_modes'][-1].split('/')[0]

                            if max_interface_link_mode in ethtool_to_netbox_speed_mappings[if_type]:
                                if self.debug:
                                    print(f"Found max interface link mode {max_interface_link_mode}")
                                    print()

                                if_type_speed = ethtool_to_netbox_speed_mappings[if_type][max_interface_link_mode]
                                self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][ni['iface']]['type'] = if_type_speed
                            else:
                                if self.debug:
                                    print(f"*** No interface link mode found for {ni['iface']}.  Using default (other)")
                                    print()

                                self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][ni['iface']]['type'] = 'other'
                    else:
                        self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][ni['iface']]['type'] = 'other'

                        if ni['iface'].startswith('vmbr'):
                            self.discovered_proxmox_nodes_information[proxmox_node]['system']['network_interfaces'][ni['iface']]['type'] = 'bridge'

                    interface_number += 1
                
                if self.debug:
                    print("ALL IF", self.discovered_proxmox_nodes_information)
        except proxmoxer.core.ResourceException as e:
            raise ValueError(f"Proxmox resource exception encountered: {e}")
    

    def simulate_get_proxmox_nodes_network_interfaces(self):
        base_mac_addr = ':d3:ad:b3:3f:' # e.g. 64:62:66:23:BF:13
        mac_addr_first_val = 0

        pm_nodes_sim_dir = './.simulate/proxmox_nodes'

        for proxmox_node in self.proxmox_nodes:
            interface_number = 0
            mac_addr_last_val = 0

            if not 'network_interfaces' in self.proxmox_nodes[proxmox_node]['system']:
                self.proxmox_nodes[proxmox_node]['system']['network_interfaces'] = {}

            pm_nodes_subdir = f"{pm_nodes_sim_dir}/{proxmox_node}"

            if not os.path.isdir(pm_nodes_subdir):
                raise ValueError(f"Unable to locate simulation directory for Proxmox nodes: {pm_nodes_subdir}")
        
            json_network_file = f"{pm_nodes_subdir}/networking.json"

            with open(json_network_file, 'r') as json_f:
                json_network_data = json.load(json_f)

            for ni in sorted(json_network_data, key=lambda item: item['iface']):
                if not 'iface' in ni:
                    continue

                if ni['type'] == 'unknown':
                    continue

                if not ni['iface'] in self.proxmox_nodes[proxmox_node]['system']['network_interfaces']:
                    self.proxmox_nodes[proxmox_node]['system']['network_interfaces'][ni['iface']] = {}

                if not 'active' in ni:
                    ni['active'] = 0

                mac_first_two = f"{mac_addr_first_val:02d}"
                mac_last_two = f"{mac_addr_last_val:02d}"
                mac_addr = f"{str(mac_first_two)}{base_mac_addr}{str(mac_last_two)}"
                print(f"proxmox node {proxmox_node} -> {ni['iface']} -> mac {mac_addr} active {ni['active']}")

                self.proxmox_nodes[proxmox_node]['system']['network_interfaces'][ni['iface']]['mac'] = mac_addr
                self.proxmox_nodes[proxmox_node]['system']['network_interfaces'][ni['iface']]['enabled'] = bool(ni['active'])

                if 'bridge_ports' in ni:
                    self.proxmox_nodes[proxmox_node]['system']['network_interfaces'][ni['iface']]['bridge_ports'] = ni['bridge_ports'].split(' ')[0]

                if 'cidr' in ni:
                    self.proxmox_nodes[proxmox_node]['system']['network_interfaces'][ni['iface']]['ipv4address'] = ni['cidr']

                if 'cidr6' in ni:
                    self.proxmox_nodes[proxmox_node]['system']['network_interfaces'][ni['iface']]['ipv6address'] = ni['cidr6']

                if self.debug:
                    print("  NODE NETWORK INTERFACE", json.dumps(ni, indent=4), "\n", ni['iface'], ni['type'], ni['active'])

                if ni['type'] == 'eth':
                    self.proxmox_nodes[proxmox_node]['system']['network_interfaces'][ni['iface']]['type'] = 'other'
                elif ni['type'] == 'bridge':
                    self.proxmox_nodes[proxmox_node]['system']['network_interfaces'][ni['iface']]['type'] = 'bridge'

                interface_number += 1
                
                if self.debug:
                    print("ALL IF", self.proxmox_nodes)

                mac_addr_last_val += 1

            mac_addr_first_val += 1


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

        if self.debug:
            print("ETHTOOL SETTINGS")
            print(json.dumps(ethtool_settings, indent=4))
            print()

        return ethtool_settings


