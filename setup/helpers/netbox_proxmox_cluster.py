import re
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
