import os, sys, re
import time

import pynetbox

class NetBoxBranches:
    def __init__(self, nb_obj):
        self.nb = nb_obj.nb
        self.branch_name = None
        self.all_branches_obj = None
        self.branch_obj = None
        self.branches = {}
        self.default_branch_timeout = 30

        self.__collect_branches()


    def __collect_branches(self):
        try:
            for collect_branch in list(self.nb.plugins.branching.branches.all()):
                branch_info = dict(collect_branch)

                if 'name' in branch_info:
                    self.branches[branch_info['name']] = collect_branch.schema_id
        except pynetbox.RequestError as e:
            raise ValueError(f"Error collecting branches")


    def show_branches(self):
        try:
            self.__collect_branches()
            print(self.branches)
        except pynetbox.RequestError as e:
            raise ValueError(f"Error showing branches")


    def get_branch(self, branch_name: str):
        try:
            branch_info = (self.nb.plugins.branching.branches.get(name=branch_name))

            if not branch_info:
                return None
            
            return branch_info
        except pynetbox.RequestError as e:
            raise ValueError(f"Error getting branch: {branch_name}")


    def get_branch_status(self, branch_name: str):
        try:
            branch_info = self.get_branch(branch_name)

            if not branch_info:
                raise ValueError(f"Unable to get status for branch {branch_name}")
            
            return dict(branch_info)['status']['value']
        except pynetbox.RequestError as e:
            raise ValueError(f"Error getting status of branch: {branch_name}")


    def create_branch(self, branch_name: str, branch_timeout=0):
        try:
            if not self.get_branch(branch_name):
                created_branch = self.nb.plugins.branching.branches.create(name=branch_name)

                if not created_branch:
                    raise ValueError(f"Unable to create branch {branch_name}")
                
                # check branch status over interval
                check_interval = 1

                if not branch_timeout:
                    branch_timeout = self.default_branch_timeout

                while True:
                    branch_status = self.get_branch_status(branch_name)

                    if branch_status == 'ready':
                        self.branches[branch_name] = self.get_branch(created_branch).schema_id
                        break

                    if check_interval <= branch_timeout:
                        time.sleep(1)
                        check_interval += 1

                    if check_interval > branch_timeout:
                        raise ValueError(f"Branch {branch_name} not set to ready status in {branch_timeout} seconds")
        except pynetbox.RequestError as e:
            raise ValueError(f"Error creating branch: {branch_name}")


    def delete_branch(self, branch_name: str):
        try:
            branch_to_delete = self.get_branch(branch_name)

            if branch_to_delete:        
                branch_to_delete.delete()

            del self.branches[branch_name]
        except pynetbox.RequestError as e:
            raise ValueError(f"Error deleting branch: {branch_name}")
    

    def activate_branch(self, branch_name: str):
        try:
            branch_to_activate = self.get_branch(branch_name)

            if not branch_to_activate:
                raise ValueError(f"Unable to active branch: {branch_to_activate}")

            self.nb.activate_branch(branch_name)
        except pynetbox.RequestError as e:
            raise ValueError(f"Error deleting branch: {branch_name}")
