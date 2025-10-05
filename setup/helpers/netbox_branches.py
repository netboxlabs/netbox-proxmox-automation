import os, sys, re
import time

import pynetbox

class NetBoxBranches:
    def __init__(self, nb_obj, branch_name: str, branch_timeout: str):
        self.nb = nb_obj
        self.default_branch_timeout = 120
        self.branch_name = branch_name
        self.branches = {}

        if int(branch_timeout) == 0:
            self.branch_timeout = self.default_branch_timeout
        else:
            self.branch_timeout = branch_timeout

        self.__collect_branches()


    def __collect_branches(self):
        try:
            for collect_branch in list(self.nb.plugins.branching.branches.all()):
                if not getattr(collect_branch, 'name'):
                    raise ValueError(f"Branch {self.branch_name} is missing name attribute")
                
                self.branches[collect_branch.name] = {}                    
                self.branches[collect_branch.name]['schema_id'] = collect_branch.schema_id
                self.branches[collect_branch.name]['status'] = str(collect_branch.status).lower()
        except pynetbox.RequestError as e:
            raise ValueError(f"Error collecting branches")


    def show_branches(self):
        try:
            self.__collect_branches()
            print(self.branches)
        except pynetbox.RequestError as e:
            raise ValueError(f"Error showing branches")


    def get_branch(self):
        try:
            branch_info = self.nb.plugins.branching.branches.get(name=self.branch_name)

            if not branch_info:
                return None
            
            return branch_info
        except pynetbox.RequestError as e:
            raise ValueError(f"Error getting branch: {self.branch_name}")


    def __get_branch_status(self):
        try:
            branch_info = self.get_branch()

            if not branch_info:
                raise ValueError(f"Unable to get status for branch {self.branch_name}")
            
            return dict(branch_info)['status']['value']
        except pynetbox.RequestError as e:
            raise ValueError(f"Error getting status of branch: {self.branch_name}")


    def create_branch(self):
        try:
            if not self.get_branch():
                print(f"Creating branch {self.branch_name}")
                created_branch = self.nb.plugins.branching.branches.create(name=self.branch_name)

                if not created_branch:
                    raise ValueError(f"Unable to create branch {self.branch_name}")
                
                # check branch status over interval
                check_interval = 1

                if not getattr(self, 'branch_timeout'):
                    branch_timeout = self.default_branch_timeout
                else:
                    branch_timeout = self.branch_timeout

                while True:
                    branch_status = self.__get_branch_status()

                    if branch_status == 'ready':
                        self.branches[self.branch_name] = {}
                        self.branches[self.branch_name]['status'] = branch_status
                        self.branches[self.branch_name]['schema_id'] = self.get_branch().schema_id
                        break

                    if check_interval <= branch_timeout:
                        time.sleep(1)
                        check_interval += 1

                    if check_interval > branch_timeout:
                        raise ValueError(f"Branch {self.branch_name} not set to ready status in {branch_timeout} seconds")
        except pynetbox.RequestError as e:
            raise ValueError(f"Error creating branch: {self.branch_name}")


    def delete_branch(self):
        try:
            branch_to_delete = self.get_branch()

            if branch_to_delete:        
                branch_to_delete.delete()

            del self.branches[self.branch_name]
        except pynetbox.RequestError as e:
            raise ValueError(f"Error deleting branch: {self.branch_name}")
    

    def branch_changes(self):
        try:
            branch_info = self.nb.plugins.branching.changes.get(branch=self.branches[self.branch_name]['schema_id'])

            if not branch_info:
                return None
            
            return branch_info
        except pynetbox.RequestError as e:
            raise ValueError(f"Error getting branch: {self.branch_name}")


    def activate_branch(self):
        try:
            if self.branch_name in self.branches and self.branches[self.branch_name]['status'] == 'merged':
                raise ValueError(f"Branch {self.branch_name} is already of status {self.branches[self.branch_name]['status']}.  Please delete this branch before running this script again.")
            
            self.create_branch()
            self.nb.http_session.headers['X-NetBox-Branch'] = self.branches[self.branch_name]['schema_id']
        except pynetbox.RequestError as e:
            raise ValueError(f"Error deleting branch: {self.branch_name}")
