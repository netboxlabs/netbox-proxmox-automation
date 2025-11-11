import os
import pynetbox
import re
import requests
import time
import urllib

from proxmoxer import ProxmoxAPI, ResourceException

class NetBoxProxmoxHelper:
    def __init__(self, cfg_data, proxmox_node, debug=False):
        self.debug = debug

        self.netbox_api_config = {
            'api_proto': cfg_data['netbox_api_config']['api_proto'],
            'api_host': cfg_data['netbox_api_config']['api_host'],
            'api_port': cfg_data['netbox_api_config']['api_port'],
            'api_token': cfg_data['netbox_api_config']['api_token'],
            'verify_ssl': cfg_data['netbox_api_config']['verify_ssl']
        }

        self.proxmox_api_config = {
            'node': proxmox_node,
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
            verify_ssl=False
        )

        nb_url = f"{self.netbox_api_config['api_proto']}://{self.netbox_api_config['api_host']}:{self.netbox_api_config['api_port']}"

        self.netbox_api = pynetbox.api(
            nb_url,
            token=self.netbox_api_config['api_token']
        )

        self.netbox_api.http_session.verify = self.netbox_api_config['verify_ssl']


    def json_data_check_proxmox_vmid_exists(self, json_in):
        if not json_in['data']['custom_fields']['proxmox_vmid']:
            raise ValueError("Missing value for 'proxmox_vmid'")


    def netbox_get_proxmox_vmid(self, nb_vm_obj_proxmox_vmid):
        try:
            nb_obj = self.netbox_api.virtualization.virtual_machines.get(id=nb_vm_obj_proxmox_vmid)

            if not nb_obj:
                raise ValueError("Unable to get Proxmox vmid from NetBox")

            nb_obj_data = dict(nb_obj)

            return nb_obj_data['custom_fields']['proxmox_vmid']
        except pynetbox.core.query.RequestError as e:
            raise pynetbox.core.query.RequestError(e)


    def netbox_get_proxmox_node_from_vm_id(self, nb_vm_id=0):
        try:
            nb_obj = self.netbox_api.virtualization.virtual_machines.get(id=nb_vm_id)

            if not nb_obj:
                raise ValueError("Unable to get Proxmox vmid from NetBox")

            nb_obj_data = dict(nb_obj)

            return nb_obj_data['custom_fields']['proxmox_node']
        except pynetbox.core.query.RequestError as e:
            raise pynetbox.core.query.RequestError(e)
    

    def proxmox_job_get_status(self, job_in):
        try:
            while True:
                task_status = self.proxmox_api.nodes(self.proxmox_api_config['node']).tasks(job_in).status.get()

                if self.debug:
                    print("RAW TASK STATUS", task_status)

                if 'status' in task_status and task_status['status'] == 'stopped':
                    break
        except ResourceException as e:
            raise ResourceException(e)
        

    def generate_gateway_from_ip_address(self, ip_address, last_quad=1):
        return '.'.join(''.join(ip_address.split('/')[0]).split('.')[0:3]) + f'.{last_quad}'
    

    def proxmox_get_vms(self):
        try:
            proxmox_vms = {}

            proxmox_get_vms = self.proxmox_api.cluster.resources.get(type='vm')

            for proxmox_vm in proxmox_get_vms:
                if not proxmox_vm['template']:
                    if 'name' in proxmox_vm and 'vmid' in proxmox_vm:
                        proxmox_vms[proxmox_vm['name']] = proxmox_vm['vmid']

            return proxmox_vms
        except ResourceException as e:
            return ResourceException(e)
        

    def create_vm_root_disk_in_netbox(self, netbox_vm_obj_id = 0, disk_name = 'dummy', full_root_disk_info = None):
        try:
            disk_info, disk_size = full_root_disk_info.split(',')
            storage_volume = disk_info.split(':')[0]

            m = re.search(r'^size=(\d+)([MG])$', disk_size)

            if m:
                disk_raw_size = m.group(1)

                if m.group(2) == 'G':
                    disk_size = int(disk_raw_size) * 1000
                elif m.group(2) == 'M':
                    disk_size = int(disk_raw_size)

                netbox_vm_disk_info = {
                    'virtual_machine': netbox_vm_obj_id,
                    'name': disk_name,
                    'custom_fields': {
                        'proxmox_disk_storage_volume': storage_volume
                    },
                    'size': disk_size
                }

                self.netbox_api.virtualization.virtual_disks.create(**netbox_vm_disk_info)
        except pynetbox.lib.query.RequestError as e:
            return pynetbox.lib.query.RequestError(e)


class NetBoxProxmoxHelperVM(NetBoxProxmoxHelper):
    def __proxmox_update_vm_vcpus_and_memory(self, vmid=1, vcpus=1, memory=500):
        try:
            update_vm_vcpus = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(vmid).config.post(
                cores=int(float(vcpus)),
                memory=int(memory)
            )

            self.proxmox_job_get_status(update_vm_vcpus)

            return 200, {'result': f"Updated CPU information (cpus: {vcpus}, memory: {memory}) for {vmid}"}
        except ResourceException as e:
            return 500, {'result': e.content}
        

    def proxmox_check_if_vm_exists(self, vm_name = None):
        vm_exists = False

        proxmox_vms = self.proxmox_get_vms()

        if vm_name in proxmox_vms:
            vm_exists = True

        return vm_exists
 
 
    def proxmox_clone_vm(self, json_in):
        try:
            for required_netbox_object in ['proxmox_vm_templates', 'proxmox_vm_storage']:
                if not required_netbox_object in json_in['data']['custom_fields']:
                    return 500, {'result': f"Missing {required_netbox_object} in VM configuration"}

            netbox_collected_vms = {}

            nb_obj = self.netbox_api.virtualization.virtual_machines.filter(name=json_in['data']['name'])

            if not nb_obj:
                raise ValueError(f"Unable to find VM {json_in['data']['name']} in NetBox")
            
            nb_objs = list(nb_obj)

            if nb_objs:
                for nbo in nb_objs:
                    nbo_settings = dict(nbo)
                    netbox_collected_vms[nbo_settings['name']] = {}

                    if not 'tenant' in netbox_collected_vms[nbo_settings['name']]:
                        netbox_collected_vms[nbo_settings['name']]['tenant'] = []

                    netbox_collected_vms[nbo_settings['name']]['tenant'].append(nbo_settings['tenant'])

            if json_in['data']['tenant'] not in netbox_collected_vms[json_in['data']['name']]['tenant'] or not self.proxmox_check_if_vm_exists(json_in['data']['name']):
                try:
                    if 'data' in json_in and 'custom_fields' in json_in['data'] and 'proxmox_vmid' in json_in['data']['custom_fields'] and json_in['data']['custom_fields']['proxmox_vmid']:
                        self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(int(json_in['data']['custom_fields']['proxmox_vmid'])).config.get()
                    else:
                        new_vm_id = self.proxmox_api.cluster.get('nextid')
                except ResourceException as e:
                    if re.search(r'does\s+not\s+exist$', e.content):                
                        new_vm_id = int(json_in['data']['custom_fields']['proxmox_vmid'])
                    else:
                        return 500, {'result': e.content}
                
                if not new_vm_id:
                    raise ValueError(f"Unable to create VM id for {json_in['data']['name']}")

                clone_data = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(int(json_in['data']['custom_fields']['proxmox_vm_templates'])).clone.post(
                    newid=new_vm_id,
                    full=1,
                    name=json_in['data']['name'],
                    storage=json_in['data']['custom_fields']['proxmox_vm_storage'],
                    target=json_in['data']['custom_fields']['proxmox_node']
                )

                self.proxmox_job_get_status(clone_data)

                # set vmid in NetBox
                try:
                    tenant_name = json_in['data']['tenant']

                    if tenant_name:
                        nb_obj_update_vmid = self.netbox_api.virtualization.virtual_machines.get(name=json_in['data']['name'], tenant=tenant_name)
                    else:
                        nb_obj_update_vmid = self.netbox_api.virtualization.virtual_machines.get(name=json_in['data']['name'])

                    if nb_obj_update_vmid:
                        nb_obj_update_vmid['custom_fields']['proxmox_vmid'] = new_vm_id
                        nb_obj_update_vmid.save()
                except pynetbox.core.query.RequestError as e:
                    raise pynetbox.core.query.RequestError(e)
                
                # set scsi0 in NetBox
                try:
                    proxmox_vm_config = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(new_vm_id).config.get()

                    if 'bootdisk' in proxmox_vm_config:
                        os_disk = proxmox_vm_config['bootdisk']

                        self.create_vm_root_disk_in_netbox(nb_obj_update_vmid['id'], os_disk, proxmox_vm_config[os_disk])
                except pynetbox.core.query.RequestError as e:
                    raise pynetbox.core.query.RequestError(e)

            # update VM vcpus and memory if defined
            if json_in['data']['vcpus'] and json_in['data']['memory']:
                if not 'custom_fields' in json_in['data']:
                    json_in['data']['custom_fields'] = {}

                if not 'proxmox_vmid' in json_in['data']['custom_fields']:
                    json_in['data']['custom_fields']['proxmox_vmid'] = new_vm_id

                return self.proxmox_update_vm_vcpus_and_memory(json_in)
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_update_vm_vcpus_and_memory(self, json_in):
        #self.json_data_check_proxmox_vmid_exists(json_in)
        
        # update VM vcpus and/or memory if defined
        if json_in['data']['custom_fields']['proxmox_vmid'] and json_in['snapshots']['postchange']['vcpus'] and json_in['snapshots']['postchange']['memory']:
            return self.__proxmox_update_vm_vcpus_and_memory(json_in['data']['custom_fields']['proxmox_vmid'], json_in['snapshots']['postchange']['vcpus'], json_in['snapshots']['postchange']['memory'])
        
        return 500, {'result': f"Unable to update vcpus (json_in['snapshots']['postchange']['vcpus']) and/or memory (json_in['snapshots']['postchange']['memory']) for {json_in['data']['custom_fields']['proxmox_vmid']}"}


    def proxmox_start_vm(self, json_in):
        try:
            self.json_data_check_proxmox_vmid_exists(json_in)

            start_data = self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).status.start.post()

            self.proxmox_job_get_status(start_data)

            return 200, {'result': f"VM {json_in['data']['custom_fields']['proxmox_vmid']} started successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_stop_vm(self, json_in):
        try: 
            self.json_data_check_proxmox_vmid_exists(json_in)

            stop_data = self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).status.stop.post()

            self.proxmox_job_get_status(stop_data)

            return 200, {'result': f"VM {json_in['data']['custom_fields']['proxmox_vmid']} stopped successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_delete_vm(self, json_in):
        try:
            self.json_data_check_proxmox_vmid_exists(json_in)

            self.proxmox_stop_vm(json_in)

            delete_data = self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).delete()

            self.proxmox_job_get_status(delete_data)

            return 200, {'result': f"VM {json_in['data']['custom_fields']['proxmox_vmid']} deleted successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}

    
    def proxmox_set_ipconfig0(self, json_in):
        try:
            self.json_data_check_proxmox_vmid_exists(json_in)

            primary_ip = json_in['data']['primary_ip']['address']
            gateway = self.generate_gateway_from_ip_address(primary_ip)

            create_ipconfig0 = self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).config.post(
                ipconfig0=f"ip={primary_ip},gw={gateway}"
            )

            self.proxmox_job_get_status(create_ipconfig0)

            return 200, {'result': f"ipconfig0 set for VM {json_in['data']['custom_fields']['proxmox_vmid']} successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_set_ssh_public_key(self, json_in):
        try:
            self.json_data_check_proxmox_vmid_exists(json_in)

            proxmox_public_ssh_key = urllib.parse.quote(json_in['data']['custom_fields']['proxmox_public_ssh_key'].rstrip(), safe='')

            create_ssh_public_key = self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).config.post(
                sshkeys=f"{proxmox_public_ssh_key}"
            )

            self.proxmox_job_get_status(create_ssh_public_key)

            return 200, {'result': f"SSH public key for VM {json_in['data']['custom_fields']['proxmox_vmid']} set successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_add_disk(self, json_in):
        the_proxmox_vmid = ''

        try:
            if json_in['data']['name'] == 'scsi0':
                self.proxmox_resize_disk(json_in)
                the_proxmox_vmid = json_in['data']['custom_fields']['proxmox_vmid']
            else:
                proxmox_vmid = self.netbox_get_proxmox_vmid(json_in['data']['virtual_machine']['id'])

                config_data = {
                    f"{json_in['data']['name']}": f"{json_in['data']['custom_fields']['proxmox_disk_storage_volume']}:{int(json_in['data']['size'])/1000},backup=0,ssd=0"
                }

                add_disk_data = self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).qemu(proxmox_vmid).config.post(
                    **config_data
                )

                self.proxmox_job_get_status(add_disk_data)

                the_proxmox_vmid = proxmox_vmid

            return 200, {'result': f"Disk {json_in['data']['name']} resized for VM {the_proxmox_vmid} successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_resize_disk(self, json_in):
        try:
            proxmox_vmid = self.netbox_get_proxmox_vmid(json_in['data']['virtual_machine']['id'])

            disk_resize_info = self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).qemu(proxmox_vmid).resize.put(
                disk=json_in['data']['name'],
                size=f"{int(json_in['data']['size'])/1000}G"
            )

            self.proxmox_job_get_status(disk_resize_info)

            return 200, {'result': f"Disk {json_in['data']['name']} for VM {proxmox_vmid} resized successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_delete_disk(self, json_in):
        try:
            if json_in['data']['name'] == 'scsi0':
                raise ValueError("Cannot delete VM OS disk")

            proxmox_vmid = self.netbox_get_proxmox_vmid(json_in['data']['virtual_machine']['id'])

            self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).qemu(proxmox_vmid).unlink.put(idlist=json_in['data']['name'], force=1)

            return 200, {'result': f"Disk {json_in['data']['name']} for VM {json_in['data']['virtual_machine']['id']} deleted successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


class NetBoxProxmoxHelperLXC(NetBoxProxmoxHelper):
    def __proxmox_update_lxc_vcpus_and_memory(self, proxmox_node=None, vmid=1, vcpus=1, memory=512):
        try:
            update_lxc_vcpus = self.proxmox_api.nodes(proxmox_node).lxc(vmid).config.put(
                cores=int(float(vcpus)),
                memory=int(memory)
            )

            #self.proxmox_job_get_status(update_lxc_vcpus)

            return 200, {'result': f"Updated CPU and/or memory information (cpus: {vcpus}, memory {memory}) for {vmid}"}
        except ResourceException as e:
            return 500, {'result': e.content}
        

    def proxmox_create_lxc(self, json_in):
        try:
            # json_in['data']['name']
            # json_in['data']['custom_fields']['proxmox_lxc_template']
            try:
                if self.debug:
                    print("JSON IN", json_in['data'])

                if 'data' in json_in and 'custom_fields' in json_in['data'] and 'proxmox_vmid' in json_in['data']['custom_fields'] and json_in['data']['custom_fields']['proxmox_vmid']:
                    self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).config.get()
                else:
                    new_vm_id = self.proxmox_api.cluster.get('nextid')
            except ResourceException as e:
                if re.search(r'does\s+not\s+exist$', e.content):
                    if self.debug:
                        print("VMID IN PROXMOX DOES NOT EXIST (setting new vmid)", json_in['data']['custom_fields']['proxmox_vmid'])

                    new_vm_id = json_in['data']['custom_fields']['proxmox_vmid']
                else:
                    return 500, {'result': e.content}
            
            if not new_vm_id:
                return 500, {'result': f"Unable to create LXC id for {json_in['data']['name']}"}

            lxc_create_data = {
                'vmid': new_vm_id,
                'hostname': json_in['data']['name'],
                'ostemplate': json_in['data']['custom_fields']['proxmox_lxc_templates'],
                'cores': int(json_in['data']['vcpus']),
                'memory': int(json_in['data']['memory']),
                'storage': json_in['data']['custom_fields']['proxmox_vm_storage'],
                'password': 'netbox-proxmox-automation',
                'onboot': 1,
                'unprivileged': 1,
                'swap': 0
            }

            if json_in['data']['custom_fields']['proxmox_public_ssh_key']:
                if self.debug:
                    print("  LXC got public SSH key")
                lxc_create_data['ssh-public-keys'] = json_in['data']['custom_fields']['proxmox_public_ssh_key']

            if self.debug:
                print("LXC CREATE DATA", lxc_create_data, new_vm_id)

            create_lxc_data = self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).lxc.create(**lxc_create_data)

            self.proxmox_job_get_status(create_lxc_data)

            try:
                nb_obj_update_vmid = self.netbox_api.virtualization.virtual_machines.get(name=json_in['data']['name'])
            except pynetbox.lib.query.RequestError as e:
                return 500, {'result': e.content}

            if nb_obj_update_vmid:
                netbox_vm_obj_id = nb_obj_update_vmid['id']

                if self.debug:
                    print("  ID", netbox_vm_obj_id)

                nb_obj_update_vmid['custom_fields']['proxmox_vmid'] = new_vm_id
                nb_obj_update_vmid.save()

                """
                'rootfs': 'local-lvm:vm-104-disk-0,size=4G'}
                """
                
                lxc_config_info = self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).lxc(new_vm_id).config.get()

                if self.debug:
                    print("LXC CONFIG INFO", lxc_config_info)

                if 'rootfs' in lxc_config_info:
                    if self.debug:
                        print("ROOTFS INFO", lxc_config_info['rootfs'])

                    self.create_vm_root_disk_in_netbox(netbox_vm_obj_id, 'rootfs', lxc_config_info['rootfs'])

            if self.debug:
                print("AFTER LXC CREATE")

            return 200, {'result': f"LXC {json_in['data']['name']} (vmid: {new_vm_id}) created successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_update_lxc_vpus_and_memory(self, json_in):
        self.json_data_check_proxmox_vmid_exists(json_in)
        
        # update VM vcpus and/or memory if defined
        if json_in['data']['custom_fields']['proxmox_vmid'] and json_in['snapshots']['postchange']['vcpus'] and json_in['snapshots']['postchange']['memory']:
            return self.__proxmox_update_lxc_vcpus_and_memory(json_in['data']['custom_fields']['proxmox_node'], json_in['data']['custom_fields']['proxmox_vmid'], json_in['snapshots']['postchange']['vcpus'], json_in['snapshots']['postchange']['memory'])
        
        return 500, {'result': f"Unable to set vcpus ({json_in['data']['vcpus']}) and/or memory ({json_in['data']['memory']}) for LXC (vmid: {json_in['data']['custom_fields']['proxmox_vmid']})"}


    def proxmox_lxc_set_net0(self, json_in):
        try:
            self.json_data_check_proxmox_vmid_exists(json_in)

            primary_ip = json_in['data']['primary_ip']['address']
            gateway = self.generate_gateway_from_ip_address(primary_ip)

            self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).lxc(json_in['data']['custom_fields']['proxmox_vmid']).config.put(
                    net0=f"name=net0,bridge=vmbr0,ip={primary_ip},gw={gateway},firewall=1"
            )

            return 200, {'result': f"net0 for (LXC) vmid {json_in['data']['custom_fields']['proxmox_vmid']} configured with IP {primary_ip} and gateway {gateway}"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_lxc_resize_disk(self, json_in):
        if self.debug:
            print("PROXMOX LXC RESIZE DISK")

        try:
            proxmox_vmid = self.netbox_get_proxmox_vmid(json_in['data']['virtual_machine']['id'])

            disk_size = f"{int(json_in['data']['size'])/1000}G"
            print(f"LXC RESIZE DISK SIZE {json_in['data']['virtual_machine']} {disk_size}")

            lxc_disk_size_info = {
                'disk': 'rootfs',
                'size': disk_size
            }

            disk_resize_info = self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).lxc(proxmox_vmid).resize.put(**lxc_disk_size_info)

            self.proxmox_job_get_status(disk_resize_info)

            return 200, {'result': f"Disk rootfs resized to {disk_size}"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_start_lxc(self, json_in):
        try:
            self.json_data_check_proxmox_vmid_exists(json_in)

            start_data = self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).lxc(json_in['data']['custom_fields']['proxmox_vmid']).status.start.post()

            self.proxmox_job_get_status(start_data)

            return 200, {'result': f"LXC (vmid: {json_in['data']['custom_fields']['proxmox_vmid']}) has been started"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_stop_lxc(self, json_in):
        try: 
            self.json_data_check_proxmox_vmid_exists(json_in)

            stop_data = self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).lxc(json_in['data']['custom_fields']['proxmox_vmid']).status.stop.post()

            self.proxmox_job_get_status(stop_data)

            return 200, {'result': f"LXC (vmid: {json_in['data']['custom_fields']['proxmox_vmid']}) has been stopped"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_delete_lxc(self, json_in):
        try:
            self.json_data_check_proxmox_vmid_exists(json_in)

            self.proxmox_stop_lxc(json_in)

            delete_data = self.proxmox_api.nodes(json_in['data']['custom_fields']['proxmox_node']).lxc.delete(json_in['data']['custom_fields']['proxmox_vmid'])

            self.proxmox_job_get_status(delete_data)

            return 200, {'result': f"LXC (vmid: {json_in['data']['custom_fields']['proxmox_vmid']}) has been deleted"}
        except ResourceException as e:
            return 500, {'result': e.content}


class NetBoxProxmoxHelperMigrate(NetBoxProxmoxHelper):
    def __init__(self, cfg_data, proxmox_node, debug=False):
        super().__init__(cfg_data, proxmox_node, debug)

        self.proxmox_cluster_name = 'default-proxmox-cluster-name'
        self.proxmox_nodes = {}
        self.proxmox_vms = {}
        self.proxmox_lxc = {}

        self.__get_cluster_name_and_nodes()
        self.__get_proxmox_vms()
        self.__get_proxmox_lxcs()


    def __get_cluster_name_and_nodes(self):
        try:
            cluster_status = self.proxmox_api.cluster.status.get()

            for resource in cluster_status:
                if not 'type' in resource:
                    raise ValueError(f"Missing 'type' in Proxmox cluster resource {resource}")
                
                if resource['type'] == 'cluster':
                    self.proxmox_cluster_name = resource['name']
                elif resource['type'] == 'node':
                    if not resource['name'] in self.proxmox_nodes:
                        self.proxmox_nodes[resource['name']] = {}

                    self.proxmox_nodes[resource['name']]['ip'] = resource['ip']
                    self.proxmox_nodes[resource['name']]['online'] = resource['online']
        except ResourceException as e:
            raise RuntimeError(f"Proxmox API error: {e}") from e
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Failed to connect to Proxmox API")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            raise RuntimeError(f"HTTP {status}: {e.response.text}") from e
        

    def __get_proxmox_vms(self):
        try:
            for proxmox_node in self.proxmox_nodes:
                all_vm_settings = self.proxmox_api.nodes(proxmox_node).get('qemu')
                for vm_setting in all_vm_settings:
                    if 'template' in vm_setting and vm_setting['template'] == 1:
                        continue

                    if not vm_setting['name'] in self.proxmox_vms:
                        self.proxmox_vms[vm_setting['name']] = {}

                    self.proxmox_vms[vm_setting['name']]['vmid'] = vm_setting['vmid']
                    self.proxmox_vms[vm_setting['name']]['node'] = proxmox_node
        except ResourceException as e:
            raise RuntimeError(f"Proxmox API error: {e}") from e
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Failed to connect to Proxmox API")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            raise RuntimeError(f"HTTP {status}: {e.response.text}") from e


    def __get_proxmox_lxcs(self):
        try:
            for proxmox_node in self.proxmox_nodes:
                all_lxc_settings = self.proxmox_api.nodes(proxmox_node).get('lxc')
                for lxc_setting in all_lxc_settings:
                    if 'template' in lxc_setting and lxc_setting['template'] == 1:
                        continue

                    if not lxc_setting['name'] in self.proxmox_lxc:
                        self.proxmox_lxc[lxc_setting['name']] = {}

                    self.proxmox_lxc[lxc_setting['name']]['vmid'] = lxc_setting['vmid']
                    self.proxmox_lxc[lxc_setting['name']]['node'] = proxmox_node
        except ResourceException as e:
            raise RuntimeError(f"Proxmox API error: {e}") from e
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Failed to connect to Proxmox API")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            raise RuntimeError(f"HTTP {status}: {e.response.text}") from e


    def __wait_for_migration_task(self, proxmox_node: str, proxmox_task_id: int):
        try:
            start_time = int(time.time())

            while True:
                current_time = int(time.time())
                elapsed_seconds = current_time - start_time

                if elapsed_seconds >= 600: # 10 minutes
                    return 500, {'content': f"Unable to complete task {proxmox_task_id} in defined time"}
                
                task_status = self.proxmox_api.nodes(proxmox_node).tasks(proxmox_task_id).status.get()

                if task_status['status'] == 'stopped':
                    if 'exitstatus' in task_status and task_status['exitstatus'] == 'OK':
                        return 200, {'result': "Proxmox node migration successful"}
                    else:
                        return 500, {'result': f"Task {proxmox_task_id} is stopped but exit status does not appear to be successful: {task_status['exit_status']}"}
        except ResourceException as e:
            return 500, {'content': f"Proxmox API error: {e}"}
        except requests.exceptions.ConnectionError as e:
            return 500, {'content': f"Failed to connect to Proxmox API: {e}"}
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            return 500, {'content': f"HTTP {status}: {e.response.text}"}


    def migrate_vm(self, proxmox_vmid: int, proxmox_node: str, proxmox_target_node: str):
        migrate_vm_data = {
            'target': proxmox_target_node,
            'online': 1
        }

        try:
            migrate_vm_task_id = self.proxmox_api.nodes(proxmox_node).qemu(proxmox_vmid).migrate.post(**migrate_vm_data)
            return self.__wait_for_migration_task(proxmox_node, migrate_vm_task_id)
        except ResourceException as e:
            return 500, {'result': f"Proxmox API error: {e}"}
        except requests.exceptions.ConnectionError:
            return 500, {'result': f"Failed to connect to Proxmox API: {e}"}
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            return 500, {'result': f"HTTP {status}: {e.response.text}"}


    def migrate_lxc(self, proxmox_vmid: int, proxmox_node: str, proxmox_target_node: str):
        migrate_lxc_data = {
            'target': proxmox_target_node,
            'online': 1
        }

        try:
            migrate_lxc_task_id = self.proxmox_api.nodes(proxmox_node).lxc(proxmox_vmid).migrate.post(**migrate_lxc_data)
            self.__wait_for_migration_task(proxmox_node, migrate_lxc_task_id)
            return 200, {'result': f"LXC (vmid: {proxmox_vmid}) has been migrated to node {proxmox_target_node}"}
        except ResourceException as e:
            return 500, {'result': f"Proxmox API error: {e}"}
        except requests.exceptions.ConnectionError:
            return 500, {'result': f"Failed to connect to Proxmox API: {e}"}
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            return 500, {'result': f"HTTP {status}: {e.response.text}"}


