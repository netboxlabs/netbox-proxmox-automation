import os, sys, re
import requests
import json
import base64

from requests.auth import HTTPBasicAuth
from awxkit import api, config, utils


class AnsibleAutomation:
    def __init__(self, cfg_data = {}):
        self.cfg_data = cfg_data

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
    

    def create_object(self, method_name = None, obj_name = None, payload = {}):
        got_obj = self.get_object_by_name(method_name, obj_name)

        if not got_obj:
            method = getattr(self.api_v2, method_name)
            got_obj = method.post(payload)

        return got_obj
        

    def __setup_http_basic_auth(self, username = None, password = None):
        return HTTPBasicAuth(username, password)


    def do_rest_api_request(self, in_uri = None, request_method = None, ssl_verify = False, data = {}):
        if in_uri.startswith('/') and self.aa_base_url.endswith('/'):
            in_uri = re.sub(r'^\/', '', in_uri)

        if not in_uri.endswith('/'):
            in_uri += '/'

        full_url = f"{self.aa_base_url}{in_uri}"

        awx_api_login_str = f"{self.cfg_data['username']}:{self.cfg_data['password']}"
        awx_api_login_str_auth = base64.b64encode(awx_api_login_str.encode('utf-8')).decode('utf-8')
        awx_auth_header = f"Authorization: Basic {awx_api_login_str_auth}"

        auth_in = self.__setup_http_basic_auth(self.cfg_data['username'], self.cfg_data['password'])

        headers = {
            'Content-Type': 'application/json'
        }

        if request_method == 'GET':
            response = requests.get(full_url, headers = headers, auth=auth_in, verify=ssl_verify)
        elif request_method == 'POST':
            response = requests.post(full_url, headers = headers, auth=auth_in, verify=ssl_verify, json=data)

        if response.status_code in (200, 201):
            return response.json()
        elif response.status_code == 204:
            return f"added {full_url}"
        else:
            print("ERR", full_url, response.text, response.status_code)
            return json.loads(response.text)

