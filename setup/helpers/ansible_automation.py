import os, sys, re
from awxkit import api, config, utils

class AnsibleAutomation:
    def __init__(self, cfg_data = {}):
        self.cfg_data = cfg_data

        aa_url = f"{self.cfg_data['http_proto']}://{self.cfg_data['host']}:{str(self.cfg_data['http_port'])}/"

        if not aa_url.endswith('/'):
            aa_url += '/'

        aa_user = self.cfg_data['username']
        aa_pass = self.cfg_data['password']

        config.base_url = aa_url
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
            return get_obj
        
        return {}


    def get_object_id(self, method_name = None, obj_name = None):
        object_id = 0

        found_obj = self.get_object_by_name(method_name, obj_name)

        if found_obj:
            object_id = found_obj['id']

        return object_id
    

    def create_object(self, method_name = None, obj_name = None, payload = {}):
        got_obj = self.get_object_by_name(method_name, obj_name)

        if not got_obj:
            method = getattr(self.api_v2, method_name)
            got_obj = method.post(payload)

        return got_obj
        

