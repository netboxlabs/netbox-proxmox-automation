import re
import getpass
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
        self.netbox_api = netbox_api_obj


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
