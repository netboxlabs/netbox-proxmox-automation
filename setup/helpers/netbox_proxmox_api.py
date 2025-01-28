import re
import pynetbox
import proxmoxer
import requests
import urllib
import urllib.parse

from proxmoxer import ProxmoxAPI

class NetBoxProxmoxAPIHelper:
    def __init__(self, cfg_data):
        self.proxmox_nodes = []
        self.proxmox_vm_templates = {}
        self.proxmox_vms = {}
        self.proxmox_lxc = {}
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

        self.__proxmox_collect_nodes()
        self.__proxmox_collect_vms()


    def __proxmox_collect_nodes(self):
        try:
            for proxmox_node in self.proxmox_api.nodes.get():
                if proxmox_node['type'] == 'node':
                    self.proxmox_nodes.append(proxmox_node['node'])
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)


    def __proxmox_collect_vms(self):
        try:
            proxmox_get_vms = self.proxmox_api.cluster.resources.get(type='vm')

            for proxmox_vm in proxmox_get_vms:
                if proxmox_vm['template']:
                    self.proxmox_vm_templates[proxmox_vm['vmid']] = proxmox_vm['name']
                else:
                    proxmox_vm_name = proxmox_vm['name']

                    # Sometimes Proxmox VMs have duplicate names, so take into account as proxmox-vm-name--proxmox-vmid
                    if proxmox_vm_name in self.proxmox_vms:
                        proxmox_vm_name = f"{proxmox_vm_name}-{proxmox_vm['vmid']}"

                    if proxmox_vm['type'] == 'qemu':
                        if not proxmox_vm_name in self.proxmox_vms:
                            self.proxmox_vms[proxmox_vm_name] = {}

                        self.proxmox_vms[proxmox_vm_name]['node'] = proxmox_vm['node']
                        self.proxmox_vms[proxmox_vm_name]['vmid'] = proxmox_vm['vmid']

                        self.proxmox_vms[proxmox_vm_name]['running'] = False

                        if proxmox_vm['status'] == 'running':
                            self.proxmox_vms[proxmox_vm_name]['running'] = True
                    elif proxmox_vm['type'] == 'lxc':
                        if not proxmox_vm['name'] in self.proxmox_lxc:
                            self.proxmox_lxc[proxmox_vm_name] = {}

                        self.proxmox_lxc[proxmox_vm_name]['node'] = proxmox_vm['node']
                        self.proxmox_lxc[proxmox_vm_name]['vmid'] = proxmox_vm['vmid']

                        self.proxmox_lxc[proxmox_vm_name]['running'] = False

                        if proxmox_vm['status'] == 'running':
                            self.proxmox_lxc[proxmox_vm_name]['running'] = True
                    else:
                        raise ValueError(f"Unknown Proxmox VM type {proxmox_vm['type']}")
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)


    def proxmox_get_vms(self):
        return self.proxmox_vms
    

    def proxmox_get_lxc(self):
        return self.proxmox_lxc


    def proxmox_get_vm_templates(self):
        return self.proxmox_vm_templates
    

    def proxmox_get_vm_storage_volumes(self):
        try:
            for proxmox_storage in self.proxmox_api.storage.get():
                if proxmox_storage['type'] != 'dir':
                    self.proxmox_storage_volumes.append(proxmox_storage['storage'])
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)


    def proxmox_check_if_vm_exists(self, vm_name = None):
        vm_exists = False

        if vm_name in self.proxmox_vms:
            vm_exists = True

        return vm_exists
    

    def proxmox_get_vms_configurations(self):
        proxmox_vm_configurations = {}

        #print("ALL PROXMOX VMS", "NODES", self.proxmox_nodes, "VMS", self.proxmox_vms, "LXC", self.proxmox_lxc)
        for proxmox_vm in self.proxmox_vms:
            proxmox_vm_config = self.proxmox_api.nodes(self.proxmox_vms[proxmox_vm]['node']).qemu(self.proxmox_vms[proxmox_vm]['vmid']).config.get()
            #print(" -- CONFIG", proxmox_vm_config)

            if not proxmox_vm in proxmox_vm_configurations:
                proxmox_vm_configurations[proxmox_vm] = {}

            proxmox_vm_configurations[proxmox_vm]['vcpus'] = proxmox_vm_config['cores']
            proxmox_vm_configurations[proxmox_vm]['memory'] = proxmox_vm_config['memory']
            proxmox_vm_configurations[proxmox_vm]['running'] = self.proxmox_vms[proxmox_vm]['running']
            proxmox_vm_configurations[proxmox_vm]['node'] = self.proxmox_vms[proxmox_vm]['node']
            proxmox_vm_configurations[proxmox_vm]['vmid'] = str(self.proxmox_vms[proxmox_vm]['vmid'])

            if self.proxmox_vms[proxmox_vm]['running']:
                if 'sshkeys' in proxmox_vm_config:
                    proxmox_vm_configurations[proxmox_vm]['public_ssh_key'] = urllib.parse.unquote(proxmox_vm_config['sshkeys'])

                proxmox_vm_configurations[proxmox_vm]['bootdisk'] = proxmox_vm_config['bootdisk']

                base_disk_name = re.sub(r'\d+$', '', proxmox_vm_config['bootdisk'])
                proxmox_vm_disks = [key for key in proxmox_vm_config if re.search(r'^%s\d+' % base_disk_name, key)]

                proxmox_vm_configurations[proxmox_vm]['storage'] = proxmox_vm_config[proxmox_vm_config['bootdisk']].split(':')[0]

                if not 'disks' in proxmox_vm_configurations[proxmox_vm]:
                    proxmox_vm_configurations[proxmox_vm]['disks'] = []

                for proxmox_vm_disk in proxmox_vm_disks:
                    tmp_disk_name = {}

                    disk_info = proxmox_vm_config[proxmox_vm_disk].split(',')[0]
                    storage_volume = disk_info.split(':')[0]
                    disk_size = proxmox_vm_config[proxmox_vm_disk].split(',')[-1]
                    get_disk_size = re.search(r'^size=(\d+)([MG])$', disk_size)

                    if get_disk_size.group(2) == "M":
                        disk_size = get_disk_size.group(1)
                    elif get_disk_size.group(2) == "G":
                        disk_size = int(get_disk_size.group(1)) * 1024
                    else:
                        raise ValueError(f"Unknown disk size metric: {get_disk_size.group(2)}")

                    tmp_disk_name[proxmox_vm_disk] = str(disk_size)
                    proxmox_vm_configurations[proxmox_vm]['disks'].append({'disk_name': proxmox_vm_disk, 'disk_size': tmp_disk_name[proxmox_vm_disk], 'proxmox_disk_storage_volume': storage_volume})

                try:
                    self.proxmox_api.nodes(self.proxmox_vms[proxmox_vm]['node']).qemu(self.proxmox_vms[proxmox_vm]['vmid']).agent.ping.post()

                    if not 'network_interfaces' in proxmox_vm_configurations[proxmox_vm]:
                        proxmox_vm_configurations[proxmox_vm]['network_interfaces'] = {}

                    #print("    -- NETWORK INTERFACES", self.proxmox_api.nodes(self.proxmox_vms[proxmox_vm]['node']).qemu(self.proxmox_vms[proxmox_vm]['vmid']).agent('network-get-interfaces').get())

                    for ni_info in self.proxmox_api.nodes(self.proxmox_vms[proxmox_vm]['node']).qemu(self.proxmox_vms[proxmox_vm]['vmid']).agent('network-get-interfaces').get()['result']:
                        network_interface_name = ni_info['name']
                        if not re.search(r'^(lo|docker)', network_interface_name):
                            if not network_interface_name in proxmox_vm_configurations[proxmox_vm]['network_interfaces']:
                                proxmox_vm_configurations[proxmox_vm]['network_interfaces'][network_interface_name] = {}

                            proxmox_vm_configurations[proxmox_vm]['network_interfaces'][network_interface_name] = {}
                            proxmox_vm_configurations[proxmox_vm]['network_interfaces'][network_interface_name]['mac-address'] = ni_info['hardware-address']
                            proxmox_vm_configurations[proxmox_vm]['network_interfaces'][network_interface_name]['ip-addresses'] = []

                            for ip_address in ni_info['ip-addresses']:
                                proxmox_vm_configurations[proxmox_vm]['network_interfaces'][network_interface_name]['ip-addresses'].append(
                                    {
                                        'type': ip_address['ip-address-type'],
                                        'ip-address': f"{ip_address['ip-address']}/{ip_address['prefix']}"
                                    }
                                )
                except proxmoxer.core.ResourceException as e:
                    if e.status_code == 500 and e.content == 'No QEMU guest agent configured':
                        print(f"- (SKIPPING) {e.content} for Proxmox VM {self.proxmox_vms[proxmox_vm]['vmid']}")

        #print("PXMXRVM", proxmox_vm_configurations)
        return proxmox_vm_configurations


    def proxmox_get_lxc_configurations(self):
        for proxmox_lxc in self.proxmox_lxc:
            print("AF", proxmox_lxc, self.proxmox_lxc[proxmox_lxc])
    
 
