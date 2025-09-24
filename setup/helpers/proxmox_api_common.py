import re
import pynetbox
import proxmoxer
import requests
import urllib
import urllib.parse

from proxmoxer import ProxmoxAPI

class ProxmoxAPICommon:
    def __init__(self, cfg_data):
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
