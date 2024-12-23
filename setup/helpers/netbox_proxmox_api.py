import re
import pynetbox
import requests
import urllib

from proxmoxer import ProxmoxAPI

class NetBoxProxmoxAPIHelper:
    def __init__(self, cfg_data):
        self.proxmox_nodes = []
        self.proxmox_vms = {}
        self.proxmox_vm_templates = {}
        self.proxmox_storage_volumes = []

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


    def get_proxmox_nodes(self):
        try:
            for proxmox_node in self.proxmox_api.nodes.get():
                self.proxmox_nodes.append(proxmox_node['node'])
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)


    def __proxmox_get_vms(self):
        try:
            proxmox_vms = {}

            proxmox_get_vms = self.proxmox_api.cluster.resources.get(type='vm')

            for proxmox_vm in proxmox_get_vms:
                if not proxmox_vm['template']:
                    if 'name' in proxmox_vm and 'vmid' in proxmox_vm:
                        proxmox_vms[proxmox_vm['name']] = proxmox_vm['vmid']

            return proxmox_vms
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)


    def proxmox_get_vm_templates(self):
        try:
            proxmox_get_vms = self.proxmox_api.cluster.resources.get(type='vm')

            for proxmox_vm in proxmox_get_vms:
                if proxmox_vm['template']:
                    self.proxmox_vm_templates[proxmox_vm['vmid']] = proxmox_vm['name']
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)
    

    def proxmox_get_vm_storage_volumes(self):
        try:
            for proxmox_storage in self.proxmox_api.storage.get():
                if proxmox_storage['type'] != 'dir':
                    self.proxmox_storage_volumes.append(proxmox_storage['storage'])
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)


    def proxmox_check_if_vm_exists(self, vm_name = None):
        vm_exists = False

        proxmox_vms = self.__proxmox_get_vms()

        if vm_name in proxmox_vms:
            vm_exists = True

        return vm_exists
 
 
