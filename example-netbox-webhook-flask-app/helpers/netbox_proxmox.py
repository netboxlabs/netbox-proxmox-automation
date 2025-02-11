import re
import pynetbox
import requests
import urllib

from proxmoxer import ProxmoxAPI, ResourceException

class NetBoxProxmoxHelper:
    def __init__(self, cfg_data, proxmox_node):
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


    def __json_data_check_proxmox_vmid_exists(self, json_in):
        if not json_in['data']['custom_fields']['proxmox_vmid']:
            raise ValueError("Missing value for 'proxmox_vmid'")


    def __netbox_get_proxmox_vmid(self, nb_vm_obj_proxmox_vmid):
        try:
            nb_obj = self.netbox_api.virtualization.virtual_machines.get(id=nb_vm_obj_proxmox_vmid)

            if not nb_obj:
                raise ValueError("Unable to get Proxmox vmid from NetBox")

            nb_obj_data = dict(nb_obj)

            return nb_obj_data['custom_fields']['proxmox_vmid']
        except pynetbox.core.query.RequestError as e:
            raise pynetbox.core.query.RequestError(e)


    def __proxmox_job_get_status(self, job_in):
        try:
            while True:
                task_status = self.proxmox_api.nodes(self.proxmox_api_config['node']).tasks(job_in).status.get()

                if task_status['status'] == 'stopped':
                    break
        except ResourceException as e:
            raise ResourceException(e)


    def __proxmox_update_vm_vcpus(self, vmid, vcpus):
        try:
            update_vm_vcpus = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(vmid).config.post(
                cores=int(vcpus)
            )

            self.__proxmox_job_get_status(update_vm_vcpus)

            return 200, {'result': f"Updated CPU information (cpus: {vcpus}) for {vmid}"}
        except ResourceException as e:
            return 500, {'result': e.content}
        

    def __proxmox_update_vm_memory(self, vmid, memory):
        try:
            update_vm_memory = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(vmid).config.post(
                memory=int(memory)
            )

            self.__proxmox_job_get_status(update_vm_memory)

            return 200, {'result': f"Updated memory information (memory: {memory}) for {vmid}"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def __proxmox_get_vms(self):
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


    def __generate_gateway_from_ip_address(self, ip_address, last_quad=1):
        return '.'.join(''.join(ip_address.split('/')[0]).split('.')[0:3]) + f'.{last_quad}'


    #
    # VM stuff
    #
    def proxmox_check_if_vm_exists(self, vm_name = None):
        vm_exists = False

        proxmox_vms = self.__proxmox_get_vms()

        if vm_name in proxmox_vms:
            vm_exists = True

        return vm_exists
 
 
    def proxmox_clone_vm(self, json_in):
        try:
            for required_netbox_object in ['proxmox_vm_template', 'proxmox_vm_storage']:
                if not required_netbox_object in json_in['data']['custom_fields']:
                    raise ValueError(f"Missing {required_netbox_object} in VM configuration")

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
                    if 'data' in json_in and 'custom_fields' in json_in['data'] and 'proxmox_vmid' in json_in['data']['custom_fields']:
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

                clone_data = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(int(json_in['data']['custom_fields']['proxmox_vm_template'])).clone.post(
                    newid=new_vm_id,
                    full=1,
                    name=json_in['data']['name'],
                    storage=json_in['data']['custom_fields']['proxmox_vm_storage']
                )

                self.__proxmox_job_get_status(clone_data)

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
                    raise e
                
                # set scsi0 in NetBox
                try:
                    proxmox_vm_config = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(new_vm_id).config.get()

                    if 'bootdisk' in proxmox_vm_config:
                        os_disk = proxmox_vm_config['bootdisk']

                    if os_disk in proxmox_vm_config:
                        m = re.search(r'size=(\d+)([MG]){1}', proxmox_vm_config[os_disk])

                        if m:
                            disk_raw_size = m.group(1)

                            if m.group(2) == 'G':
                                disk_size = int(disk_raw_size) * 1000
                            elif m.group(2) == 'M':
                                disk_size = int(disk_raw_size)

                    nb_obj_add_vm_disk = self.netbox_api.virtualization.virtual_disks.create(
                        virtual_machine=nb_obj_update_vmid['id'],
                        name=proxmox_vm_config['bootdisk'],
                        size=disk_size,
                        description=f"OS/boot disk for {json_in['data']['name']}"
                    )

                    if not nb_obj_add_vm_disk:
                        raise ValueError("Unable to add VM disk to NetBox")
                except pynetbox.core.query.RequestError as e:
                    raise e

            # update VM vcpus and memory if defined
            if json_in['data']['vcpus']:
                self.__proxmox_update_vm_vcpus(new_vm_id, json_in['data']['vcpus'])

            if json_in['data']['memory']:
                self.__proxmox_update_vm_memory(new_vm_id, json_in['data']['memory'])

            return 200, {'result': f"VM {json_in['data']['name']} cloned successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_update_vm_resources(self, json_in):
        self.__json_data_check_proxmox_vmid_exists(json_in)
        
        # update VM vcpus and/or memory if defined
        if json_in['data']['vcpus']:
            self.__proxmox_update_vm_vcpus(json_in['data']['custom_fields']['proxmox_vmid'], json_in['data']['vcpus'])

        if json_in['data']['memory']:
            self.__proxmox_update_vm_memory(json_in['data']['custom_fields']['proxmox_vmid'], json_in['data']['memory'])


    def proxmox_start_vm(self, json_in):
        try:
            self.__json_data_check_proxmox_vmid_exists(json_in)

            start_data = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).status.start.post()

            self.__proxmox_job_get_status(start_data)

            return 200, {'result': f"VM {json_in['data']['custom_fields']['proxmox_vmid']} started successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_stop_vm(self, json_in):
        try: 
            self.__json_data_check_proxmox_vmid_exists(json_in)

            stop_data = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).status.stop.post()

            self.__proxmox_job_get_status(stop_data)

            return 200, {'result': f"VM {json_in['data']['custom_fields']['proxmox_vmid']} stopped successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_delete_vm(self, json_in):
        try:
            self.__json_data_check_proxmox_vmid_exists(json_in)

            self.proxmox_stop_vm(json_in)

            delete_data = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).delete()

            self.__proxmox_job_get_status(delete_data)

            return 200, {'result': f"VM {json_in['data']['custom_fields']['proxmox_vmid']} deleted successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}

    
    def proxmox_set_ipconfig0(self, json_in):
        try:
            self.__json_data_check_proxmox_vmid_exists(json_in)

            primary_ip = json_in['data']['primary_ip']['address']
            gateway = self.__generate_gateway_from_ip_address(primary_ip)

            create_ipconfig0 = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).config.post(
                ipconfig0=f"ip={primary_ip},gw={gateway}"
            )

            self.__proxmox_job_get_status(create_ipconfig0)

            return 200, {'result': f"ipconfig0 set for VM {json_in['data']['custom_fields']['proxmox_vmid']} successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_set_ssh_public_key(self, json_in):
        try:
            self.__json_data_check_proxmox_vmid_exists(json_in)

            proxmox_public_ssh_key = urllib.parse.quote(json_in['data']['custom_fields']['proxmox_public_ssh_key'].rstrip(), safe='')

            create_ssh_public_key = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).config.post(
                sshkeys=f"{proxmox_public_ssh_key}"
            )

            self.__proxmox_job_get_status(create_ssh_public_key)

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
                proxmox_vmid = self.__netbox_get_proxmox_vmid(json_in['data']['virtual_machine']['id'])

                config_data = {
                    f"{json_in['data']['name']}": f"{json_in['data']['custom_fields']['proxmox_disk_storage_volume']}:{int(json_in['data']['size'])/1000},backup=0,ssd=0"
                }

                add_disk_data = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(proxmox_vmid).config.post(
                    **config_data
                )

                self.__proxmox_job_get_status(add_disk_data)

                the_proxmox_vmid = proxmox_vmid

            return 200, {'result': f"Disk {json_in['data']['name']} resized for VM {the_proxmox_vmid} successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_resize_disk(self, json_in):
        try:
            proxmox_vmid = self.__netbox_get_proxmox_vmid(json_in['data']['virtual_machine']['id'])

            disk_resize_info = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(proxmox_vmid).resize.put(
                disk=json_in['data']['name'],
                size=f"{int(json_in['data']['size'])/1000}G"
            )

            self.__proxmox_job_get_status(disk_resize_info)

            return 200, {'result': f"Disk {json_in['data']['name']} for VM {proxmox_vmid} resized successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_delete_disk(self, json_in):
        try:
            if json_in['data']['name'] == 'scsi0':
                raise ValueError("Cannot delete VM OS disk")

            proxmox_vmid = self.__netbox_get_proxmox_vmid(json_in['data']['virtual_machine']['id'])

            self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(proxmox_vmid).unlink.put(idlist=json_in['data']['name'], force=1)

            return 200, {'result': f"Disk {json_in['data']['name']} for VM {json_in['data']['virtual_machine']['id']} deleted successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}


    #
    # LXC stuff
    #
    def proxmox_create_lxc(self, json_in):
        try:
            # json_in['data']['name']
            # json_in['data']['custom_fields']['proxmox_lxc_template']
            try:
                print("JSON IN", json_in['data'])
                if 'data' in json_in and 'custom_fields' in json_in['data'] and 'proxmox_vmid' in json_in['data']['custom_fields'] and json_in['data']['custom_fields']['proxmox_vmid']:
                    self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).config.get()
                else:
                    new_vm_id = self.proxmox_api.cluster.get('nextid')
            except ResourceException as e:
                if re.search(r'does\s+not\s+exist$', e.content):
                    print("SF", json_in['data']['custom_fields']['proxmox_vmid'])                
                    new_vm_id = json_in['data']['custom_fields']['proxmox_vmid']
                else:
                    return 500, {'result': e.content}
            
            if not new_vm_id:
                return 500, {'result': f"Unable to create VM id for {json_in['data']['name']}"}

            lxc_create_data = {
                'vmid': new_vm_id,
                'hostname': json_in['data']['name'],
                'ostemplate': json_in['data']['custom_fields']['proxmox_lxc_templates'],
                'cores': int(json_in['data']['vcpus']),
                'memory': int(json_in['data']['memory']),
                'storage': json_in['data']['custom_fields']['proxmox_vm_storage'],
                'password': 'netbox-proxmox-automation',
                'onboot': 1,
                'unprivileged': 1
            }

# ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC5MttN0meoS8aVfK/9E2V7XU0VpFO9+pkwcjzyvUW6GLyA/PURs7K3DU90EZki4TYbonSo0CwGDZanCsdsBHMpTADt6snbUU0LYa+LyjnLoatDkrjWDVks6uGcPuMIDJEAw2fTdW2/wXc483QIPUWS/ZMDXjvOoAL7WTlcDvV7LkRYgdi1nOC6pe2Bxn3FU+Bm5RwBS3iJZ/CplKFi0OtTz4miobC7Ke2gbQoQ3AcbYhz24zR9QzFqdmXmNV2Fhob7H5FXhWr/xMx16n3YRSWyX2yBi7HIq56GWdCEZLv8vB1Dj/mtcFxhZ0LQ9isg0o7qrQlpjo9bZ/PY0QiC6e51 identity-proxmox-vm

            if json_in['data']['custom_fields']['proxmox_public_ssh_key']:
                print("HAI PUBLIC SSH KEY")
                lxc_create_data['ssh-public-keys'] = json_in['data']['custom_fields']['proxmox_public_ssh_key']

            print("LXC CREATE DATA", lxc_create_data, new_vm_id)

            create_lxc_data = self.proxmox_api.nodes(self.proxmox_api_config['node']).lxc.create(**lxc_create_data)

            self.__proxmox_job_get_status(create_lxc_data)

            nb_obj_update_vmid = self.netbox_api.virtualization.virtual_machines.get(name=json_in['data']['name'])

            if nb_obj_update_vmid:
                nb_obj_update_vmid['custom_fields']['proxmox_vmid'] = new_vm_id
                nb_obj_update_vmid.save()

            print("AFTER LXC CREATE")

            return 200, {'result': f"LXC {json_in['data']['name']} (vmid: {new_vm_id}) created successfully"}
        except ResourceException as e:
            return 500, {'result': e.content}



    def proxmox_lxc_set_net0(self, json_in):
        try:
            self.__json_data_check_proxmox_vmid_exists(json_in)

            primary_ip = json_in['data']['primary_ip']['address']
            gateway = self.__generate_gateway_from_ip_address(primary_ip)

            self.proxmox_api.nodes(self.proxmox_api_config['node']).lxc(json_in['data']['custom_fields']['proxmox_vmid']).config.put(
                    net0=f"name=net0,bridge=vmbr0,ip={primary_ip},gw={gateway},firewall=1"
            )

            return 200, {'result': f"net0 for vmid {json_in['data']['custom_fields']['proxmox_vmid']} configured with IP {primary_ip} and gateway {gateway}"}
        except ResourceException as e:
            return 500, {'result': e.content}



    def proxmox_lxc_resize_disk(self, json_in):
        try:
            proxmox_vmid = self.__netbox_get_proxmox_vmid(json_in['data']['virtual_machine']['id'])

            disk_size = f"{int(json_in['data']['size'])/1000}G"

            disk_resize_info = self.proxmox_api.nodes(self.proxmox_api_config['node']).lxc(proxmox_vmid).resize.put(
                    disk='rootfs',
                    size=disk_size
            )

            self.__proxmox_job_get_status(disk_resize_info)

            return 200, {'result': f"Disk rootfs resized to {disk_size}"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_start_lxc(self, json_in):
        try:
            self.__json_data_check_proxmox_vmid_exists(json_in)

            start_data = self.proxmox_api.nodes(self.proxmox_api_config['node']).lxc(json_in['data']['custom_fields']['proxmox_vmid']).status.start.post()

            self.__proxmox_job_get_status(start_data)

            return 200, {'result': f"LXC (vmid: {json_in['data']['custom_fields']['proxmox_vmid']}) has been started"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_stop_lxc(self, json_in):
        try: 
            self.__json_data_check_proxmox_vmid_exists(json_in)

            stop_data = self.proxmox_api.nodes(self.proxmox_api_config['node']).lxc(json_in['data']['custom_fields']['proxmox_vmid']).status.stop.post()

            self.__proxmox_job_get_status(stop_data)

            return 200, {'result': f"LXC (vmid: {json_in['data']['custom_fields']['proxmox_vmid']}) has been stopped"}
        except ResourceException as e:
            return 500, {'result': e.content}


    def proxmox_delete_lxc(self, json_in):
        try:
            self.__json_data_check_proxmox_vmid_exists(json_in)

            #self.proxmox_stop_vm(json_in)

            delete_data = self.proxmox_api.nodes(self.proxmox_api_config['node']).lxc.delete(json_in['data']['custom_fields']['proxmox_vmid'])

            self.__proxmox_job_get_status(delete_data)

            return 200, {'result': f"LXC (vmid: {json_in['data']['custom_fields']['proxmox_vmid']}) has been deleted"}
        except ResourceException as e:
            return 500, {'result': e.content}


