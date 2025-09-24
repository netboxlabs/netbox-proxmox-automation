import re
import pynetbox
import proxmoxer
import requests
import urllib
import urllib.parse

from proxmoxer import ProxmoxAPI, ResourceException
from . proxmox_api_common import ProxmoxAPICommon

class NetBoxProxmoxAPIHelper(ProxmoxAPICommon):
    def __init__(self, cfg_data):
        super(NetBoxProxmoxAPIHelper, self).__init__(cfg_data)

        self.cfg_data = cfg_data

        self.proxmox_nodes = []
        self.proxmox_vm_templates = {}
        self.proxmox_lxc_templates = {}
        self.proxmox_vms = {}
        self.proxmox_lxc = {}
        self.proxmox_storage_volumes = []
        self.proxmox_lxc_storage_volumes = []

        self.__proxmox_collect_nodes()
        self.__proxmox_collect_vms()


    def __proxmox_collect_nodes(self):
        try:
            # change from nodes.get to cluster.resources.get or somesuch.  this will add cluster support where we are single node now
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
    

    def proxmox_get_vm_templates(self):
        return self.proxmox_vm_templates
    

    def proxmox_get_vm_storage_volumes(self):
        try:
            for proxmox_storage in self.proxmox_api.storage.get():
                if proxmox_storage['type'] != 'dir':
                    self.proxmox_storage_volumes.append(proxmox_storage['storage'])
                else:
                    if re.search(r'vztmpl', proxmox_storage['content']):
                        self.proxmox_lxc_storage_volumes.append(proxmox_storage['storage'])
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

            if self.proxmox_vms[proxmox_vm]['running']: # FIX: MOVE BEFORE TRY AND DECREASE INDENT BUT ONLY IF CLOUD-INIT ENABLED (ide2 in our config)
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


    def proxmox_get_lxc_storage_volumes(self):
        if not self.proxmox_lxc_storage_volumes:
            self.proxmox_get_vm_storage_volumes()

    
    def proxmox_get_lxc_templates(self, proxmox_node = None):
        for lxc_storage in self.proxmox_lxc_storage_volumes:
            method = getattr(self.proxmox_api.nodes(proxmox_node).storage, lxc_storage)
            local_storage = method.content.get()

            #local_storage = self.proxmox_api.nodes('proxmox-ve').storage.local.content.get()
            if local_storage:
                for ls in local_storage:
                    if ls['format'] == 'tzst' and ls['content'] == 'vztmpl':
                        lxc_image_path = ls['volid']
                        lxc_image_name = lxc_image_path.split('/')[1]
                        self.proxmox_lxc_templates[lxc_image_path] = lxc_image_name


    def proxmox_get_lxc(self):
        return self.proxmox_lxc


    def proxmox_get_lxc_configurations(self):
        proxmox_lxc_configurations = {}

        for proxmox_lxc in self.proxmox_get_lxc():
            if not proxmox_lxc in proxmox_lxc_configurations:
                proxmox_lxc_configurations[proxmox_lxc] = {}

            proxmox_lxc_config = self.proxmox_api.nodes(self.proxmox_lxc[proxmox_lxc]['node']).lxc(self.proxmox_lxc[proxmox_lxc]['vmid']).config.get()

            proxmox_lxc_configurations[proxmox_lxc]['vcpus'] = proxmox_lxc_config['cores']
            proxmox_lxc_configurations[proxmox_lxc]['memory'] = proxmox_lxc_config['memory']
            proxmox_lxc_configurations[proxmox_lxc]['running'] = self.proxmox_lxc[proxmox_lxc]['running']
            proxmox_lxc_configurations[proxmox_lxc]['node'] = self.proxmox_lxc[proxmox_lxc]['node']
            proxmox_lxc_configurations[proxmox_lxc]['vmid'] = str(self.proxmox_lxc[proxmox_lxc]['vmid'])

            proxmox_lxc_configurations[proxmox_lxc]['is_lxc'] = True

            if not 'disks' in proxmox_lxc_configurations[proxmox_lxc]:
                proxmox_lxc_configurations[proxmox_lxc]['disks'] = []

            if 'rootfs' in proxmox_lxc_config:
                storage_volume, disk_name, disk_size = sum([part.split(':') for part in proxmox_lxc_config['rootfs'].split(',')], [])
                del disk_name

                get_disk_size = re.search(r'size=(\d+)([MG])$', disk_size)

                if not get_disk_size:
                    raise ValueError(f"Unable to find matching disk size for {proxmox_lxc}")

                if get_disk_size.group(2) == "M":
                    disk_size = get_disk_size.group(1)
                elif get_disk_size.group(2) == "G":
                    disk_size = int(get_disk_size.group(1)) * 1024
                else:
                    raise ValueError(f"Unknown disk size metric: {get_disk_size.group(2)}")

                proxmox_lxc_configurations[proxmox_lxc]['disks'].append({'disk_name': 'rootfs', 'disk_size': str(disk_size), 'proxmox_disk_storage_volume': storage_volume})
                
            if not 'network_interfaces' in proxmox_lxc_configurations[proxmox_lxc]:
                proxmox_lxc_configurations[proxmox_lxc]['network_interfaces'] = {}

            network_interface_id = 0

            while True:
                net_interface_name = f"net{network_interface_id}"

                if not net_interface_name in proxmox_lxc_config and network_interface_id == 0:
                    raise ValueError(f"Unable to find '{net_interface_name}' for {proxmox_lxc}")
                elif not net_interface_name in proxmox_lxc_config and network_interface_id > 0:
                    break
                
                ni_info = re.search(r'^name=([^,]+),bridge=[^,]+,firewall=\d{1},gw=([^,]+),hwaddr=([^,]+),ip=([^,]+),', proxmox_lxc_config[net_interface_name])
                ni_info6 = re.search(r'^name=([^,]+),bridge=[^,]+,firewall=\d{1},gw6=([^,]+),hwaddr=([^,]+),ip6=([^,]+),', proxmox_lxc_config[net_interface_name])

                if not ni_info and not ni_info6:
                    raise ValueError(f"Unable to parse network interface information for {proxmox_lxc}")
                
                if ni_info:
                    if len(ni_info.groups()) != 4:
                        raise ValueError(f"Incorrect number of fields in '{net_interface_name}' for {proxmox_lxc}")                    
                    ip_address_type = 'ipv4'

                if ni_info6:
                    if len(ni_info6.groups()) != 4:
                        raise ValueError(f"Incorrect number of fields in '{net_interface_name}' for {proxmox_lxc}")
                    ip_address_type = 'ipv6'

                interface_name = ni_info.group(1)
                #gateway = ni_info.group(2)
                mac_address = ni_info.group(3)
                ip_address = ni_info.group(4)

                if not interface_name in proxmox_lxc_configurations[proxmox_lxc]['network_interfaces']:
                    proxmox_lxc_configurations[proxmox_lxc]['network_interfaces'][interface_name] = {}

                proxmox_lxc_configurations[proxmox_lxc]['network_interfaces'][interface_name] = {}
                proxmox_lxc_configurations[proxmox_lxc]['network_interfaces'][interface_name]['mac-address'] = mac_address
                proxmox_lxc_configurations[proxmox_lxc]['network_interfaces'][interface_name]['ip-addresses'] = []

                proxmox_lxc_configurations[proxmox_lxc]['network_interfaces'][interface_name]['ip-addresses'].append(
                    {
                        'type': ip_address_type,
                        'ip-address': ip_address
                    }
                )

                network_interface_id += 1

        return proxmox_lxc_configurations    
 
