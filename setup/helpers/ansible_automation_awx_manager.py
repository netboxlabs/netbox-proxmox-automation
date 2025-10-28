import re
import time

from . ansible_automation_awx import AnsibleAutomationAWX

class AnsibleAutomationAWXManager(AnsibleAutomationAWX):
    def create_organization(self, org_name = None):
        try:
            org_payload = {
                'name': org_name
            }

            created_organization = self.create_object('organizations', org_name, org_payload)

            if not created_organization:
                raise ValueError(f"Unable to create organization: {e}")

            self.org_id = created_organization['id']
        except Exception as e:
            raise ValueError(f"Exception occurred when creating organization {org_name}: {e}")


    def create_inventory(self, inventory_name = None):
        try:
            inventory_payload = {
                'name': inventory_name,
                'organization': self.org_id
            }

            created_inventory = self.create_object('inventory', inventory_name, inventory_payload)

            if not created_inventory:
                raise ValueError(f"Unable to create inventory: {e}")

            self.inventory_id = created_inventory['id']
        except Exception as e:
            raise ValueError(f"Exception occurred when creating inventory {inventory_name}: {e}")


    def create_host(self, host_name = None, host_var_data = None):
        try:
            host_payload = {
                'name': host_name,
                'enabled': True,
                'inventory': self.inventory_id,
                'variables': host_var_data
            }

            create_host = self.create_object('hosts', host_name, host_payload)

            if not create_host:
                raise ValueError(f"Unable to create host: {host_name}")

            self.host_id = create_host['id']
        except Exception as e:
            raise ValueError(f"Exception occurred when creating host {host_name}: {e}")


    def create_execution_environment(self, ee_name = None, ee_image_name = None):
        try:
            ee_payload = {
                'name': ee_name,
                'image': ee_image_name,
                'organization': self.org_id
            }

            if hasattr(self, 'ee_reg_cred_id'):
                ee_payload['credential'] = self.ee_reg_cred_id

            created_ee_env = self.create_object('execution_environments', ee_name, ee_payload)

            if not created_ee_env:
                raise ValueError(f"Unable to create execution environment: {ee_name}")

            self.ee_id = created_ee_env['id']
        except Exception as e:
            raise ValueError(f"Exception occurred when creating execution environment {ee_name}: {e}")


    def create_project(self, project_name = None, scm_type = None, scm_url = None, scm_branch = None):
        try:
            project_payload = {
                'name': project_name,
                'organization': self.org_id,
                'scm_type': scm_type,
                'scm_url': scm_url,
                'scm_branch': scm_branch,
                'default_environment': self.ee_id
            }

            created_project = self.create_object('projects', project_name, project_payload)

            # Wait for project completion to complete, pausing 0.25s per iteration
            while True:
                proj_status = self.get_object_by_name('projects', project_name)

                if proj_status['status'] == 'successful':
                    break

                if proj_status['status'] == 'failed':
                    raise ValueError(f"Unable to sync playbooks for project {project_name}")

                time.sleep(0.25)

            if not created_project:
                raise ValueError(f"Unable to create project: {e}")

            self.project = created_project
            self.project_id = created_project['id']
        except Exception as e:
            raise ValueError(f"Exception occurred when creating project {project_name}: {e}")


    def create_credential_type(self, credential_type_name = None):
        try:
            ct_payload = {
                'name': credential_type_name,
                'kind': "cloud",
                'inputs': {
                    'fields': [
                        {'id': "proxmox_api_host", 'type': "string", 'label': "Proxmox API Host"},
                        {'id': "proxmox_api_port", 'type': "string", 'label': "Proxmox API Port"},
                        {'id': "proxmox_api_user", 'type': "string", 'label': "Proxmox API User"},
                        {'id': "proxmox_api_user_token", 'type': "string", 'label': "Proxmox API Token ID"},
                        {'id': "proxmox_node", 'type': "string", 'label': "Proxmox Node"},
                        {'id': "proxmox_api_token_secret", 'type': "string", 'label': "Proxmox API Token", 'secret': True},
                        {'id': "netbox_api_proto", 'type': "string", 'label': "NetBox HTTP Protocol"},
                        {'id': "netbox_api_host", 'type': "string", 'label': "NetBox API host"},
                        {'id': "netbox_api_port", 'type': "string", 'label': "NetBox API port"},
                        {'id': "netbox_api_token", 'type': "string", 'label': "NetBox API token", 'secret': True}
                    ],
                    'required': [
                        'proxmox_api_host',
                        'proxmox_api_port',
                        'proxmox_api_user',
                        'proxmox_api_user_token',
                        'proxmox_node',
                        'proxmox_api_token_secret',
                        'netbox_api_host',
                        'netbox_api_port',
                        'netbox_api_proto',
                        'netbox_api_token'
                    ]
                },
                'injectors': {
                    'extra_vars': {
                        "netbox_env_info": {
                            "api_host": '{{ netbox_api_host }}',
                            "api_port": '{{ netbox_api_port }}',
                            "api_proto": '{{ netbox_api_proto }}',
                            "api_token": '{{ netbox_api_token }}'
                        },
                        "proxmox_env_info": {
                            "node": '{{ proxmox_node }}',
                            "api_host": '{{ proxmox_api_host }}',
                            "api_port": '{{ proxmox_api_port }}',
                            "api_user": '{{ proxmox_api_user }}',
                            "api_token_id": '{{ proxmox_api_user_token }}',
                            "api_token_secret": '{{ proxmox_api_token_secret }}'
                        }
                    }
                }
            }

            create_credential_type = self.create_object('credential_types', credential_type_name, ct_payload)

            if not create_credential_type:
                raise ValueError(f"Unable to create credential type: {e}")

            self.credential_type_id = create_credential_type['id']
        except Exception as e:
            raise ValueError(f"Exception occurred when creating credential type {credential_type_name}: {e}")


    def create_credential(self, credential_name = None):
        try:
            credential_payload = {
                'name': credential_name,
                'credential_type': self.credential_type_id,
                'organization': self.org_id,
                'inputs': {
                    'netbox_api_host': self.netbox_cfg_data['api_host'],
                    'netbox_api_port': str(self.netbox_cfg_data['api_port']),
                    'netbox_api_proto': self.netbox_cfg_data['api_proto'],
                    'netbox_api_token': self.netbox_cfg_data['api_token'],
                    'proxmox_node': self.proxmox_cfg_data['node'],
                    'proxmox_api_host': self.proxmox_cfg_data['api_host'],
                    'proxmox_api_port': str(self.proxmox_cfg_data['api_port']),
                    'proxmox_api_user': self.proxmox_cfg_data['api_user'],
                    'proxmox_api_user_token': self.proxmox_cfg_data['api_token_id'],
                    'proxmox_api_token_secret': self.proxmox_cfg_data['api_token_secret']
                }
            }

            create_credential = self.create_object('credentials', credential_name, credential_payload)

            if not create_credential:
                raise ValueError(f"Unable to create credential: {e}")

            self.credential_id = create_credential['id']
            self.credential_name = credential_name
        except Exception as e:
            raise ValueError(f"Exception occurred when creating credential {credential_name}: {e}")


    def create_job_template(self, playbook_name = None):
        if not hasattr(self, 'created_job_templates'):
            self.created_job_templates = []

        try:
            job_template_name = re.sub(r'^playbooks/awx\-', '', playbook_name.split('.')[0])

            job_template_payload = {
                'name': job_template_name,
                'job_type': 'run',
                'inventory': self.inventory_id,
                'organization': self.org_id,
                'project': self.project_id,
                'execution_environment': self.ee_id,
                'playbook': playbook_name,
                'ask_variables_on_launch': True,
                'ask_credential_on_launch': True
            }

            created_job_template = self.create_object('job_templates', job_template_name, job_template_payload)

            if not created_job_template:
                raise ValueError(f"Unable to create job template: {job_template_name}")

            self.created_job_templates.append(created_job_template)
        except Exception as e:
            raise ValueError(f"Exception occurred when creating job template {playbook_name}: {e}")

    
    def create_job_template_credential(self, template_id):
        try:
            the_cred = self.get_object_by_name('credentials', self.credential_name)

            if not the_cred:
                raise ValueError(f"Unable to get credentials object for {self.credential_name}")
                
            jt_entry = self.get_object_by_id('job_templates', template_id)

            if not jt_entry:
                raise ValueError(f"Unable to find job_templates {template_id}")

            if not jt_entry['summary_fields']['credentials']:
                jt_entry.add_credential(the_cred)
        except Exception as e:
            raise ValueError(f"Exception occurred when creating credential for template {template_id}: {e}")
    

    def get_project(self, project_name = None):
        try:
            get_project = self.get_object_by_name('projects', project_name)

            if not get_project:
                raise ValueError(f"Unable to get project {project_name}")

            self.project = get_project
            self.project_id = get_project['id']
        except Exception as e:
            raise ValueError(f"Exception occurred when retrieving project {self.project['name']}: {e}")


    def get_playbooks(self):
        try:
            aa_playbooks = []

            for playbook_item in self.get_object_by_id('projects', self.project_id).get_related('playbooks'):
                if not playbook_item.startswith('playbooks/'):
                    continue

                if playbook_item.endswith('.yml') or playbook_item.endswith('.yaml'):
#                    if not re.search(r'/', playbook_item):
                    aa_playbooks.append(playbook_item)

            return aa_playbooks
        except Exception as e:
            raise ValueError(f"Exception occurred when retrieving playbooks for project {self.project['name']}: {e}")
    

    def get_job_templates_for_project(self):
        try:
            if not hasattr(self, 'job_templates'):
                self.job_templates = []

            for item in self.get_objects_by_kwargs('job_templates', project=self.project_id):
                self.job_templates.append(self.get_object_by_id('job_templates', item.id))
        except Exception as e:
            raise ValueError(f"Exception occurred when retrieving project templates for project {self.project['name']}: {e}")


    def delete_project(self):
        try:
            self.delete_object(self.project)
        except Exception as e:
            raise ValueError(f"Exception occurred when deleting project {self.project['name']}: {e}")
    

    def delete_job_template(self, job_template = None):
        try:
            self.delete_object(job_template)
        except Exception as e:
            raise ValueError(f"Exception occurred when deleting job template {job_template}: {e}")
    

    def delete_credential(self, credential_name = None):
        try:
            self.delete_object_by_name('credentials', credential_name)
        except Exception as e:
            raise ValueError(f"Exception occurred when deleting credential {credential_name}: {e}")
    

    def delete_credential_type(self, credential_type = None):
        try:
            self.delete_object_by_name('credential_types', credential_type)
        except Exception as e:
            raise ValueError(f"Exception occurred when deleting credential type {credential_type}: {e}")
    

    def delete_host(self, host_name = None):
        try:
            self.delete_object_by_name('hosts', host_name)
        except Exception as e:
            raise ValueError(f"Exception occurred when deleting host {host_name}: {e}")


    def delete_inventory(self, inventory_name = None):
        try:
            self.delete_object_by_name('inventory', inventory_name)
        except Exception as e:
            raise ValueError(f"Exception occurred when deleting inventory {inventory_name}: {e}")

