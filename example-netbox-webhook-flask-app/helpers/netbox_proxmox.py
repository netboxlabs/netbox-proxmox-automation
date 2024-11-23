import pynetbox
import requests
import urllib

from proxmoxer import ProxmoxAPI

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
            raise e


    def __proxmox_job_get_status(self, job_in):
        try:
            while True:
                task_status = self.proxmox_api.nodes(self.proxmox_api_config['node']).tasks(job_in).status.get()

                if task_status['status'] == 'stopped':
                    break
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)        


    def __proxmox_update_vm_vcpus(self, vmid, vcpus):
        try:
            update_vm_vcpus = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(vmid).config.post(
                cores=int(vcpus)
            )

            self.__proxmox_job_get_status(update_vm_vcpus)
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)        
        

    def __proxmox_update_vm_memory(self, vmid, memory):
        try:
            update_vm_memory = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(vmid).config.post(
                memory=int(memory)
            )

            self.__proxmox_job_get_status(update_vm_memory)
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


    def __generate_gateway_from_ip_address(self, ip_address, last_quad=1):
        return '.'.join(''.join(ip_address.split('/')[0]).split('.')[0:3]) + f'.{last_quad}'


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
                new_vm_id = self.proxmox_api.cluster.get('nextid')
                
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

            # update VM vcpus and memory if defined
            if json_in['data']['vcpus']:
                self.__proxmox_update_vm_vcpus(new_vm_id, json_in['data']['vcpus'])

            if json_in['data']['memory']:
                self.__proxmox_update_vm_memory(new_vm_id, json_in['data']['memory'])
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)        


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
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)


    def proxmox_stop_vm(self, json_in):
        try: 
            self.__json_data_check_proxmox_vmid_exists(json_in)

            stop_data = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).status.stop.post()

            self.__proxmox_job_get_status(stop_data)
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)


    def proxmox_delete_vm(self, json_in):
        try:
            self.__json_data_check_proxmox_vmid_exists(json_in)

            self.proxmox_stop_vm(json_in)

            delete_data = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).delete()

            self.__proxmox_job_get_status(delete_data)
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)

    
    def proxmox_set_ipconfig0(self, json_in):
        try:
            self.__json_data_check_proxmox_vmid_exists(json_in)

            primary_ip = json_in['data']['primary_ip']['address']
            gateway = self.__generate_gateway_from_ip_address(primary_ip)

            create_ipconfig0 = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).config.post(
                ipconfig0=f"ip={primary_ip},gw={gateway}"
            )

            self.__proxmox_job_get_status(create_ipconfig0)
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)


    def proxmox_set_ssh_public_key(self, json_in):
        try:
            self.__json_data_check_proxmox_vmid_exists(json_in)

            proxmox_public_ssh_key = urllib.parse.quote(json_in['data']['custom_fields']['proxmox_public_ssh_key'].rstrip(), safe='')

            create_ssh_public_key = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(json_in['data']['custom_fields']['proxmox_vmid']).config.post(
                sshkeys=f"{proxmox_public_ssh_key}"
            )

            self.__proxmox_job_get_status(create_ssh_public_key)
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)


    def proxmox_add_disk(self, json_in):
        try:
            if json_in['data']['name'] == 'scsi0':
                self.proxmox_resize_disk(json_in)
            else:
                proxmox_vmid = self.__netbox_get_proxmox_vmid(json_in['data']['virtual_machine']['id'])

                config_data = {
                    f"{json_in['data']['name']}": f"{json_in['data']['custom_fields']['proxmox_disk_storage_volume']}:{int(json_in['data']['size'])/1000},backup=0,ssd=0"
                }

                add_disk_data = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(proxmox_vmid).config.post(
                    **config_data
                )

                self.__proxmox_job_get_status(add_disk_data)
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)


    def proxmox_resize_disk(self, json_in):
        try:
            proxmox_vmid = self.__netbox_get_proxmox_vmid(json_in['data']['virtual_machine']['id'])

            disk_resize_info = self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(proxmox_vmid).resize.put(
                disk=json_in['data']['name'],
                size=f"{int(json_in['data']['size'])/1000}G"
            )

            self.__proxmox_job_get_status(disk_resize_info)
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)


    def proxmox_delete_disk(self, json_in):
        try:
            if json_in['data']['name'] == 'scsi0':
                raise ValueError("Cannot delete VM OS disk")

            proxmox_vmid = self.__netbox_get_proxmox_vmid(json_in['data']['virtual_machine']['id'])

            self.proxmox_api.nodes(self.proxmox_api_config['node']).qemu(proxmox_vmid).unlink.put(idlist=json_in['data']['name'], force=1)
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(e)
