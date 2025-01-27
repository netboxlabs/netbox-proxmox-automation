import pynetbox

class Netbox:
    def __init__(self, url, token, payload) -> None:
        # NetBox API details
        self.netbox_url = url
        self.netbox_token = token
        self.payload = payload
        self.object_type = None
        self.obj = None
        self.required_fields = []
        self.init_api()


    def init_api(self):
        # Initialize pynetbox API connection
        self.nb = pynetbox.api(self.netbox_url, token=self.netbox_token)


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
                            print(f"Updating '{key}' from '{getattr(self.obj, key)}' to '{value}'")
                            setattr(self.obj, key, value)
                            updated = True 
                else:
                    if getattr(self.obj, key) != value:
                        print(f"Updating '{key}' from '{getattr(self.obj, key)}' to '{value}'")
                        setattr(self.obj, key, value)
                        updated = True                
            if updated:
                self.obj.save()
                # TODO: error handling here
                print(f"Object '{self.payload}' updated successfully.")
            else:
                print(f"No changes detected for '{self.payload}'.")
        # If the object doesn't exist then create it
        else:
            if self.hasRequired:
                self.object_type.create(self.payload)
                if 'name' in self.payload:
                    print(f"Object (has required) '{self.payload['name']}' created successfully.")
                    self.findBy('name')


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
