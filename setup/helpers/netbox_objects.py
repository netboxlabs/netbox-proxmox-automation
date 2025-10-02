import os
import pynetbox
import time

class Netbox:
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
                    self.findBy('name')
                elif 'model' in self.payload:
                    print(f"Object (has required) '{self.payload['model']}' created successfully.")
                    self.findBy('model')


class NetBoxSites(Netbox):
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


class NetBoxManufacturers(Netbox):
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


class NetBoxDeviceTypes(Netbox):
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


class NetBoxDeviceInterfaceTemplates(Netbox):
    def __init__(self, url, token, payload, find_key = 'name') -> None:
        # Initialize the Netbox superclass with URL and token
        super().__init__(url, token, payload)
        self.object_type = self.nb.dcim.device_types
        self.required_fields = [
            "device_type",
            "name",
            "type" 
        ]
        self.find_key = find_key
        self.findBy(self.find_key)
        self.createOrUpdate()


class NetBoxDeviceRoles(Netbox):
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


class NetBoxDevices(Netbox):
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


class NetBoxTags(Netbox):
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


class NetboxCustomFields(Netbox):
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


class NetboxCustomFieldChoiceSets(Netbox):
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


class NetboxClusterTypes(Netbox):
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


class NetboxClusters(Netbox):
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


class NetboxVirtualMachines(Netbox):
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


class NetboxVirtualMachineInterface(Netbox):
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
        

class NetboxIPAddresses(Netbox):
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


class NetboxWebhooks(Netbox):
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


class NetboxEventRules(Netbox):
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
