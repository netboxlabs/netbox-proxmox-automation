import os, sys, re

from awxkit import api, config, utils
from awxkit.api import ApiV2, job_templates, projects
from awxkit.api.resources import resources


class AnsibleAutomationAWX:
    def __init__(self, cfg_data = {}):
        self.cfg_data = cfg_data['ansible_automation']
        self.proxmox_cfg_data = cfg_data['proxmox_api_config']
        self.netbox_cfg_data = cfg_data['netbox_api_config']

        aa_url = f"{self.cfg_data['http_proto']}://{self.cfg_data['host']}:{str(self.cfg_data['http_port'])}/"

        if not aa_url.endswith('/'):
            aa_url += '/'

        aa_user = self.cfg_data['username']
        aa_pass = self.cfg_data['password']

        self.aa_base_url = aa_url

        config.base_url = self.aa_base_url
        config.credentials = utils.PseudoNamespace(
            {'default':
                {'username': aa_user, 'password': aa_pass}
            }
        )

        connection = api.Api()
        connection.load_session().get()
        self.api_v2 = connection.available_versions.v2.get()


    def get_object_by_name(self, method_name = None, obj_name = None):
        method = getattr(self.api_v2, method_name)
        get_obj = method.get(name=obj_name)['results']

        if get_obj:
            return get_obj[0]
        
        return {}
    

    def get_object_by_id(self, method_name = None, obj_id = None):
        method = getattr(self.api_v2, method_name)
        get_obj = method.get(id=obj_id)['results']

        if get_obj:
            return get_obj[0]
        
        return {}


    def get_object_id(self, method_name = None, obj_name = None):
        object_id = 0

        found_obj = self.get_object_by_name(method_name, obj_name)

        if found_obj:
            object_id = found_obj['id']

        return object_id
    

    def get_objects_by_kwargs(self, method_name = None, **kwargs):
        method = getattr(self.api_v2, method_name)
        get_obj = method.get(**kwargs)['results']

        if get_obj:
            return get_obj
        
        return {}
    

    def create_object(self, method_name = None, obj_name = None, payload = {}):
        got_obj = self.get_object_by_name(method_name, obj_name)

        if not got_obj:
            method = getattr(self.api_v2, method_name)
            got_obj = method.post(payload)

        return got_obj

    
    def delete_object_by_name(self, method_name = None, obj_name = None):
        del_obj = self.get_object_by_name(method_name, obj_name)

        if not del_obj:
            return False
        
        try:
            return self.delete_object(del_obj)
        except:
            return False
    

    def delete_object(self, the_object = None):
        if not the_object:
            return False
        
        try:
            the_object.delete()
            return True
        except:
            return False



