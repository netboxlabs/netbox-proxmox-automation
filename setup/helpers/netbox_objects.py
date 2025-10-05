import os
import re
import pynetbox
import time


def __netbox_make_slug(in_str: str):
    return re.sub(r'\W+', '-', in_str).lower()


class NetBox:
    def _sanitize_value(self, key, value):
        # Mask sensitive fields
        sensitive_keys = {'password', 'token', 'secret'}
        if key in sensitive_keys:
            return '***'
        elif isinstance(value, dict):
            return {k: self._sanitize_value(k, v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._sanitize_value(key, v) for v in value]
        return value


    def _sanitize_payload(self):
        # Return a sanitized version of the payload
        return {key: self._sanitize_value(key, value) for key, value in self.payload.items()}
    

    def __init__(self, url, token, payload) -> None:
        # NetBox API details
        self.netbox_url = url
        self.netbox_token = token
        self.payload = payload
        self.object_type = None
        self.obj = None
        self.multi_obj = None
        self.required_fields = []

        self.__init_api()


    def __init_api(self):
        # Initialize pynetbox API connection
        self.nb = pynetbox.api(self.netbox_url, token=self.netbox_token)

        if 'X_NETBOX_BRANCH' in os.environ:
            print(f"BRANCH SESSION HEADER {os.environ['X_NETBOX_BRANCH']}", self.nb)
            self.nb.http_session.headers["X-NetBox-Branch"] = os.environ['X_NETBOX_BRANCH']


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
                print(f"Object updated successfully with sanitized payload: '{self._sanitize_payload()}'.")
            else:
                print(f"No changes detected for sanitized payload: '{self._sanitize_payload()}'.")
        # If the object doesn't exist then create it
        else:
            if self.hasRequired:
                self.object_type.create(self.payload)
                if 'name' in self.payload:
                    print(f"Object (has required) '{self.payload['name']}' created successfully.")
                    if hasattr(self, 'find_key_mult'):
                        self.findByMulti(self.find_key_mult)
                    else:
                        self.findBy('name')
                elif 'model' in self.payload:
                    print(f"Object (has required) '{self.payload['model']}' created successfully.")
                    self.findBy('model')


class NetBoxSites(NetBox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
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
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.dcim.manufacturers
        self.required_fields = [ 
            "name",
            "slug"
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxPlatforms(NetBox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.dcim.platforms
        self.required_fields = [ 
            "name",
            "slug"
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxDeviceTypes(NetBox):
    def __init__(self, url, token, payload, find_key = 'model') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
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
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.dcim.interface_templates
        self.required_fields = [
            "device_type",
            "name",
            "type" 
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxDeviceRoles(NetBox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
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
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
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
    def __init__(self, url, token, payload, find_key = 'device_id') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.dcim.interfaces
        self.required_fields = [ 
            "device_id"
        ]
        self.find_key = find_key
        self.findByFilter(self.find_key)


class NetBoxDeviceInterfaceMacAddressMapping(NetBox):
    def __init__(self, url, token, device_id: int, interface_name: str, payload) -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)

        self.__netbox_update_interface_for_proxmox_node_by_device_id(device_id, interface_name, self.payload)


    def __netbox_assign_mac_address_for_proxmox_node_by_object_id(self, assigned_object_id: int, mac_address: str):
        try:
            mac_address_data = {
                'mac_address': mac_address,
                'assigned_object_type': 'dcim.interface',
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


    def __netbox_update_interface_for_proxmox_node_by_device_id(self, device_id: int, interface_name: str, interface_data: dict):
        try:
            interface = self.nb.dcim.interfaces.get(device_id=device_id, name=interface_name)

            if not interface:
                raise ValueError(f"Interface {interface_name} not found on device id: {device_id}")

            assigned_mac_address = self.__netbox_assign_mac_address_for_proxmox_node_by_object_id(interface.id, interface_data['mac'])

            interface.enabled = interface_data['enabled']

            if 'id' in assigned_mac_address:
                interface.primary_mac_address = assigned_mac_address['id']
            else:
                interface.primary_mac_address = assigned_mac_address.id

            interface.save()
        except pynetbox.RequestError as e:
            raise ValueError(e, e.error)


class NetBoxDeviceCreateBridgeInterface(NetBox):
    def __init__(self, url, token, payload) -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.dcim.interfaces
        self.required_fields = [ 
            "device",
            "bridge",
            "name"
        ]
        self.find_key_mult = {'device_id': self.payload['device'], 'bridge': self.payload['bridge'], 'name': self.payload['name']}
        self.findByMulti(self.find_key_mult)
        self.createOrUpdate()


class NetBoxTags(NetBox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.extras.tags
        self.required_fields = [ 
            "name",
            "slug"
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxCustomFields(NetBox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
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
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.extras.custom_field_choice_sets
        self.required_fields = [ 
            "name",
            "extra_choices",

        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxClusterTypes(NetBox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.virtualization.cluster_types
        self.required_fields = [ 
            "name",
            "slug",
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxClusterGroups(NetBox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.virtualization.cluster_groups
        self.required_fields = [ 
            "name",
            "slug",
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxClusters(NetBox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
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
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
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
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)

        """
        self.object_type = self.nb.virtualization.interfaces
        self.required_fields = [ 
            "name",
            "virtual_machine"
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()
        """

        self.object_type = self.nb.virtualization.interfaces
        nb_vm_int = self.object_type.create(payload)
        

class NetBoxIPAddresses(NetBox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.ipam.ip_addresses
        self.required_fields = [ 
            "address",
            "status",    
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxWebhooks(NetBox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
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
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
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
