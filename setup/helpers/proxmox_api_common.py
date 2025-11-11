import re
import pynetbox
import proxmoxer
import requests
import urllib
import urllib.parse

from proxmoxer import ProxmoxAPI, ResourceException

class ProxmoxAPICommon:
    def __init__(self, cfg_data):
        self.cfg_data = cfg_data
        self.proxmox_cluster_name = None
        self.proxmox_nodes = {}

        self.proxmox_api_config = {
            'api_host': cfg_data['proxmox_api_config']['api_host'],
            'api_port': cfg_data['proxmox_api_config']['api_port'],
            'api_user': cfg_data['proxmox_api_config']['api_user'],
            'api_token_id': cfg_data['proxmox_api_config']['api_token_id'],
            'api_token_secret': cfg_data['proxmox_api_config']['api_token_secret'],
            'verify_ssl': cfg_data['proxmox_api_config']['verify_ssl']
        }

        self.proxmox_api = ProxmoxAPI(
            self.proxmox_api_config['api_host'],
            port=self.proxmox_api_config['api_port'],
            user=self.proxmox_api_config['api_user'],
            token_name=self.proxmox_api_config['api_token_id'],
            token_value=self.proxmox_api_config['api_token_secret'],
            verify_ssl=self.proxmox_api_config['verify_ssl']
        )

        self.__proxmox_collect_cluster_name_and_nodes()

    
    def __proxmox_collect_cluster_name_and_nodes(self):
        try:
            proxmox_cluster_status = self.proxmox_api.cluster.status.get()

            # Extract all 'type' values for 'cluster' (should only be 1)
            proxmox_cluster_info = list(filter(lambda d: d["type"] == 'cluster', proxmox_cluster_status))

            if len(proxmox_cluster_info) > 1:
                raise ValueError(f"Multiple Proxmox cluster names found for {self.proxmox_api_config['api_host']}.  Not allowed!")

            if proxmox_cluster_info:
                self.proxmox_cluster_name = proxmox_cluster_info[0]['name']

            # Extract all values for type 'nodes'
            proxmox_node_info = list(filter(lambda d: d["type"] == 'node', proxmox_cluster_status))

            if not proxmox_node_info:
                raise ValueError(f"Unable to collect nodes for {self.proxmox_api_config['api_host']}")

            if not self.proxmox_cluster_name and len(self.proxmox_nodes) > 1:
                raise ValueError(f"No cluster name is defined, and node count is {len(self.proxmox_nodes)}")

            for pm_node in proxmox_node_info:
                if pm_node['type'] != 'node':
                    continue

                #print("PM NODE", pm_node)

                if not pm_node['name'] in self.proxmox_nodes:
                    self.proxmox_nodes[pm_node['name']] = {}
                
                self.proxmox_nodes[pm_node['name']]['ip'] = pm_node['ip']
                self.proxmox_nodes[pm_node['name']]['online'] = pm_node['online']

                self.proxmox_nodes[pm_node['name']]['version'] = f"Proxmox-{self.__get_proxmox_version_from_node(pm_node['name'])}"

            if not self.proxmox_cluster_name:
                if 'cluster_name' in self.cfg_data['proxmox']:
                    self.proxmox_cluster_name = self.cfg_data['proxmox']['cluster_name']
                else:
                    self.proxmox_cluster_name = list(self.proxmox_nodes.keys())[0]
        except ResourceException as e:
            print("E", e, dir(e), e.status_code, e.status_message, e.errors)
            if e.errors:
                if 'vmid' in e.errors:
                    print("F", e.errors['vmid'])
            raise ValueError("E", e, dir(e), e.status_code, e.status_message, e.errors)
        

    def __get_proxmox_version_from_node(self, proxmox_node: str):
        try:
            pm_version_info = self.proxmox_api.nodes(proxmox_node).version.get()
            return f"{pm_version_info['version']}-{pm_version_info['repoid']}"
        except ResourceException as e:
            #raise(e)
            print("E", e, dir(e), e.status_code, e.status_message, e.errors)
            if e.errors:
                if 'vmid' in e.errors:
                    print("F", e.errors['vmid'])
    
