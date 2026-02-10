import os
import re
import pynetbox
import requests
import time

from . netbox_branches import NetBoxBranches


def __netbox_make_slug(in_str: str):
    return re.sub(r'\W+', '-', in_str).lower()


class NetBox:
    def _sanitize_value(self, key, value):
        # Mask sensitive fields
        sensitive_keys = {
            'password',
            'token',
            'secret',
            # Network-identifying fields that should not be logged in clear text
            'mac_address',
            'mac',
            'ip-address',
            'ip_address',
        }
        if key in sensitive_keys:
            return '***'
        elif isinstance(value, dict):
            return {k: self._sanitize_value(k, v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._sanitize_value(key, v) for v in value]
        return value


    def _sanitize_payload(self):
        # Return a sanitized version of the payload
        return {key: self._sanitize_value(key, value) for key, value in self.payload.items()} if self.payload else {}
    

    def __init__(self, url, token, options, payload) -> None:
        # NetBox API details
        self.netbox_url = url
        self.netbox_token = token
        self.payload = payload
        self.object_type = None
        self.obj = None
        self.multi_obj = None
        self.required_fields = []

        self.debug = options['debug']

        if self.debug:
            # Log a sanitized version of the payload to avoid exposing sensitive data
            print(f"INCOMING PAYLOAD __init__: {self._sanitize_payload()}")
            print()

        self.__init_api(options)


    def __init_api(self, options: dict):
        # Initialize pynetbox API connection
        try:
            self.nb = pynetbox.api(self.netbox_url, token=self.netbox_token)

            if self.debug:
                print(f"INCOMING OPTIONS __init_api: {options}")
                print()

            if 'verify_ssl' in options:
                self.nb.http_session.verify = options['verify_ssl']
            else:
                self.nb.http_session.verify = False
        except requests.exceptions.SSLError as e:
            raise ValueError(f"SSL error (pynetbox): {e}")
        except pynetbox.RequestError as e:
            raise ValueError(f"pynetbox request error: {e}")
        except pynetbox.core.query.ContentError as e:
            raise ValueError(f"pynetbox content error: {e}")
        except pynetbox.core.query.AllocationError as e:
            raise ValueError(f"pynetbox allocation error: {e}")
        except NameError as e:
            raise ValueError(f"pynetbox name error: {e}")

        if 'branch' in options:
            branch_timeout = 0

            if 'branch_timeout' in options:
                branch_timeout = int(options['branch_timeout'])

            self.nbb = NetBoxBranches(self.nb, options['branch'], branch_timeout)
            self.nbb.activate_branch()        


    def findBy(self, key):
        self.obj = self.object_type.get(**{key: self.payload[key]})
    

    def findByMulti(self, dict_in):
        self.obj = self.object_type.get(**dict_in)


    def findByFilter(self, key):
        self.multi_obj = self.object_type.filter(**{key: self.payload[key]})


    @property
    def hasRequired(self):
        missing = []
        for key in self.required_fields:
            if key not in self.payload:
                missing.append(key)
        if missing:
            print(f"missing required fields {', '.join(missing)}")
            return False
        else: 
            return True

    def createOrUpdate(self):
        # If object exists see if we need to update it
        if self.obj:
            # Do we need to save?
            updated = False

            for key, value in self.payload.items():
                if isinstance(value, dict):
                    if hasattr(self.obj, key):
                        child_key = next(iter(value))
                        child_value = value[child_key]
                        if not hasattr(self.obj, key) or not hasattr(getattr(self.obj, key), child_key) or getattr(getattr(self.obj, key), child_key) != child_value:
                            setattr(self.obj, key, value)
                            updated = True
                            print(f"Updated field '{key}' successfully.")
                else:
                    if getattr(self.obj, key) != value:
                        setattr(self.obj, key, value)
                        updated = True
                        print(f"Updated field '{key}' successfully.")
            if updated:
                self.obj.save()
                # TODO: error handling here
                print("Object updated successfully.")
            else:
                print("No changes detected.")
        # If the object doesn't exist then create it
        else:
            if self.hasRequired:
                self.object_type.create(self.payload)
                if 'name' in self.payload:
                    print("Object (has required) created successfully.")
                    if hasattr(self, 'find_key_mult'):
                        self.findByMulti(self.find_key_mult)
                    else:
                        self.findBy('name')
                elif 'model' in self.payload:
                    print("Object (has required) created successfully.")
                    self.findBy('model')
                elif 'address' in self.payload:
                    print("Object (has required) created successfully.")
                    self.findBy('address')


class NetBoxSites(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.dcim.sites
        self.required_fields = [ 
            "name",
            "slug",
            "status"
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxManufacturers(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.dcim.manufacturers
        self.required_fields = [ 
            "name",
            "slug"
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxPlatforms(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.dcim.platforms
        self.required_fields = [ 
            "name",
            "slug"
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxDeviceTypes(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'model') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.dcim.device_types
        self.required_fields = [
            "manufacturer",
            "model", 
            "slug",
            "u_height"
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxDeviceTypesInterfaceTemplates(NetBox):
    def __init__(self, url, token, options, payload) -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.dcim.interface_templates
        self.required_fields = [
            "device_type",
            "name",
            "type" 
        ]
            
        self.find_key_mult = {'device_type': payload['device_type'], 'name': payload['name'], 'type': payload['type']}
        self.findByMulti(self.find_key_mult)
        self.createOrUpdate()


class NetBoxDeviceRoles(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.dcim.device_roles
        self.required_fields = [ 
            "name",
            "slug",
            "vm_role"
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxDevices(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.dcim.devices
        self.required_fields = [ 
            "name",
            "role",
            "device_type",
            "site"
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxDevicesInterfaces(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'device_id') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.dcim.interfaces
        self.required_fields = [ 
            "device_id"
        ]
        self.find_key = find_key
        self.findByFilter(self.find_key)


class NetBoxDeviceInterface(NetBox):
    def __init__(self, url, token, options, payload) -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.dcim.interfaces
        self.required_fields = [ 
            "device",
            "name"
        ]
        self.find_key_mult = {'device_id': self.payload['device'], 'name': self.payload['name']}
        self.findByMulti(self.find_key_mult)

        if self.debug:
            print(f"\tFOUND OBJ NetBoxDeviceInterface: {self.obj}")

        self.createOrUpdate()


class NetBoxDeviceBridgeInterface(NetBox):
    def __init__(self, url, token, options, payload) -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.dcim.interfaces
        self.required_fields = [ 
            "device",
            "bridge",
            "name"
        ]
        self.find_key_mult = {'device_id': self.payload['device'], 'bridge': self.payload['bridge'], 'name': self.payload['name']}
        self.findByMulti(self.find_key_mult)
        self.createOrUpdate()


class NetBoxObjectInterfaceMacAddressMapping(NetBox):
    def __init__(self, url, token, options, obj_type: str, device_id: int, interface_name: str, payload) -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)

        self.__netbox_update_interface_for_proxmox_node_by_device_id(obj_type, device_id, interface_name, self.payload)


    def __netbox_assign_mac_address_for_proxmox_node_by_object_id(self, assigned_object_id: int, assigned_object_type: str, mac_address: str):
        try:
            mac_address_data = {
                'mac_address': mac_address,
                'assigned_object_type': assigned_object_type,
                'assigned_object_id': assigned_object_id
            }

            check_mac_address = self.nb.dcim.mac_addresses.get(assigned_object_id=assigned_object_id, mac_address=mac_address)

            if not check_mac_address:
                new_mac_address = self.nb.dcim.mac_addresses.create(**mac_address_data)

                if not new_mac_address:
                    raise ValueError(f"Unable to create mac address {mac_address} for interface id: {assigned_object_id}")

                return new_mac_address

            return check_mac_address        
        except pynetbox.RequestError as e:
            raise ValueError(e, e.error)


    def __netbox_update_interface_for_proxmox_node_by_device_id(self, object_type: str, device_id: int, interface_name: str, interface_data: dict):
        try:
            interface = self.nb.dcim.interfaces.get(device_id=device_id, name=interface_name)

            if interface:
                interface_mac = self.__netbox_assign_mac_address_for_proxmox_node_by_object_id(interface.id, object_type, interface_data['mac'])

                interface.enabled = interface_data['enabled']

                if interface_mac:
                    if 'id' in interface_mac:
                        interface.primary_mac_address = interface_mac['id']
                    else:
                        interface.primary_mac_address = interface_mac.id

                interface.save()
        except pynetbox.RequestError as e:
            raise ValueError(e, e.error)


class NetBoxTags(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.extras.tags
        self.required_fields = [ 
            "name",
            "slug"
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxCustomFields(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.extras.custom_fields
        self.required_fields = [ 
            "weight",
            "filter_logic",
            "search_weight",
            "object_types",
            "type",
            "name",
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxCustomFieldChoiceSets(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.extras.custom_field_choice_sets
        self.required_fields = [ 
            "name",
            "extra_choices",

        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxClusterTypes(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.virtualization.cluster_types
        self.required_fields = [ 
            "name",
            "slug",
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxClusterGroups(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.virtualization.cluster_groups
        self.required_fields = [ 
            "name",
            "slug",
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxClusters(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.virtualization.clusters
        self.required_fields = [ 
            "name",
            "type",
            "status",
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxVirtualMachines(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.virtualization.virtual_machines
        self.required_fields = [ 
            "name",
            "cluster",
            "status"
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxVirtualMachineInterface(NetBox):
    def __init__(self, url, token, options, obj_type, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)

        self.object_type = self.nb.virtualization.interfaces
        self.required_fields = [ 
            "name",
            "virtual_machine",
            "mac_address"
        ]

        if self.debug:
            # Log a sanitized version of the payload to avoid exposing sensitive data
            print(f"NetBoxVirtualMachineInterface payload: {self._sanitize_payload()}")
            print()

        self.find_key_mult = {'virtual_machine_id': self.payload['virtual_machine'], 'name': self.payload['name']}
        self.findByMulti(self.find_key_mult)
        self.createOrUpdate()

        if 'mac_address' in self.payload:
            self.payload['mac'] = self.payload.pop('mac_address')

        if not 'enabled' in self.payload:
            self.payload['enabled'] = True

        self.__netbox_update_interface_for_proxmox_node_by_vm_id(obj_type, self.payload['virtual_machine'], self.payload['name'], self.payload)


    def __netbox_assign_mac_address_for_vm_interface_by_object_id(self, assigned_object_id: int, assigned_object_type: str, mac_address: str):
        try:
            mac_address_data = {
                'mac_address': mac_address,
                'assigned_object_type': assigned_object_type,
                'assigned_object_id': assigned_object_id
            }

            check_mac_address = self.nb.dcim.mac_addresses.get(assigned_object_id=assigned_object_id, mac_address=mac_address)

            if not check_mac_address:
                new_mac_address = self.nb.dcim.mac_addresses.create(**mac_address_data)

                if not new_mac_address:
                    raise ValueError(f"Unable to create mac address {mac_address} for interface id: {assigned_object_id}")

                return new_mac_address

            return check_mac_address        
        except pynetbox.RequestError as e:
            raise ValueError(e, e.error)


    def __netbox_update_interface_for_proxmox_node_by_vm_id(self, object_type: str, vm_id: int, interface_name: str, interface_data: dict):
        try:
            interface = self.nb.virtualization.interfaces.get(virtual_machine_id=vm_id, name=interface_name)

            if interface:
                if self.debug:
                    print(F"VM IF INFO: {dict(interface)}")
                    print()

                interface_mac = None
                if interface_data['mac']:
                    interface_mac = self.__netbox_assign_mac_address_for_vm_interface_by_object_id(interface.id, object_type, interface_data['mac'])

                interface.enabled = interface_data['enabled']

                if interface_mac:
                    if 'id' in interface_mac:
                        interface.primary_mac_address = interface_mac['id']
                    else:
                        interface.primary_mac_address = interface_mac.id

                interface.save()
        except pynetbox.RequestError as e:
            raise ValueError(e, e.error)

class NetBoxIPAddresses(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.ipam.ip_addresses
        self.required_fields = [ 
            "address",
            "status",    
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxWebhooks(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.extras.webhooks
        self.required_fields = [ 
            'name',
            'ssl_verification',
            'http_method',
            'http_content_type',
            'payload_url',
            'additional_headers',
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxEventRules(NetBox):
    def __init__(self, url, token, options, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, options, payload)
        self.object_type = self.nb.extras.event_rules
        self.required_fields = [ 
            "name",
            "enabled",
            "object_types",
            "event_types",
            "action_type",
            "action_object_type",
            "action_object_id",
            "conditions"    
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()
