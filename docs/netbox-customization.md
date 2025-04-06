# NetBox Customization

You will need to do some customization to NetBox to define the underlying Proxmox VM configuration(s).  This section covers the custom field choices and custom fields that you'll need to create in NetBox -- in order for you to facilitate automation.

### Custom Field Choices (for Proxmox VM and LXC automation)

You will need to perform some customization in NetBox before you can start automating Proxmox VMs and LXCs.

#### Automated NetBox Objects and the Creation of Custom Field Choices and Custom Fields

`netbox-proxmox-automation` version 1.1.0 and newer ships with a convenience script, `netbox_setup_objects_and_custom_fields.py`, that when used alongside a configuration file of your choice, will greatly simplify this process.  In the case of AWX/Tower/AAP, `netbox_setup_objects_and_custom_fields.py` will query your AWX/Tower/AAP instance for project and template(s) information; this information will then be used to create the corresponding webhooks and event rules in NetBox.

There exists a sample configuration file called `netbox_setup_objects.yml-sample` under the conf.d directory of this git repository.  Copy this file to a location of your choice, and season it to taste.  In the end you should have a configuration that looks something like this.

```
proxmox_api_config:
  api_host: proxmox-ip-or-hostname
  api_port: 8006
  api_user: proxmox_api_user
  api_token_id: name_of_proxmox_api_token
  api_token_secret: proxmox_api_secret_token
  verify_ssl: false
netbox_api_config:
  api_proto: http # or https
  api_host: name or ip of NetBox host
  api_port: 8000
  api_token: netbox_api_secret_token
  verify_ssl: false # or true, up to you
proxmox:
  cluster_name: proxmox-ve
netbox:
  cluster_role: Proxmox
  vm_role: "Proxmox VM"
```

Usage:

```
shell$ cd setup

shell$ pwd
/some/path/netbox-proxmox-automation/setup

shell$ python3 -m venv venv

shell$ source venv/bin/activate

(venv) shell$ pip install -r requirements.txt

(venv) shell$ ./netbox_setup_objects_and_custom_fields.py --config /path/to/your/configuration.yml
```

Then verify that everything has been created.  In the end, you should have Custom Fields for the following.

  - proxmox_node:
      - Object types: Virtual Machine
      - Label: Proxmox node
      - Group name: Proxmox (common)
      - Type: Selection
  - proxmox_vm_type:
      - Object types: Virtual Machine
      - Label: Proxmox VM Type
      - Group name: Proxmox (common)
      - Type: Selection
  - proxmox_vmid:
      - Object types: Virtual Machine
      - Label: Proxmox Virtual machine ID (vmid)
      - Group name: Proxmox (common)
      - Type: Text
  - proxmox_vm_storage:
      - Object types: Virtual Machine
      - Label: Proxmox VM Storage
      - Group name: Proxmox (common)
      - Type: Selection
  - proxmox_public_ssh_key:
      -  Object types: Virtual Machine
      - Label: Proxmox public SSH key
      - Group name: Proxmox (common)
      - Type: Text (long)
  - proxmox_lxc_templates:
      - Object types: Virtual Machine
      - Label: Proxmox LXC Templates
      - Group name: Proxmox LXC
      - Type: Selection
  - proxmox_disk_storage_volume:
      - Object types: Virtual Disk
      - Label: Proxmox Disk Storage Volume
      - Group name: Proxmox VM
      - Type: Selection
  - proxmox_vm_templates:
      - Object types: Virtual Machine
      - Label: Proxmox VM Templates
      - Group name: Proxmox VM
      - Type: Selection

And you have Custom Field Choices for the following:

  - proxmox-cluster-nodes: used by `proxmox_node` custom field
      - Choices: available Proxmox nodes
      - Default: first "discovered" Proxmox node
  - proxmox-lxc-templates: used by `proxmox_lxc_templates` custom field
      - Choices: "discovered" available Proxmox LXC images
      - Default: first "discovered" Proxmox LXC image
  - proxmox-vm-storage: used by `proxmox_vm_storage` custom field
      - Choices: "discovered" Proxmox storage volumes
      - Default: first "discovered" Proxmox storage volume
  - proxmox-vm-templates: used by `proxmox_vm_templates` custom field
      - Choices: "discovered" Proxmox VM templates
      - Default: first "discovered" Proxmox VM template, based on lowest discovered vmid
  - proxmox-vm-type: used by `proxmox_vm_type`
      - Choices: Virtual Machine, LXC Container
      - Default: Virtual Machine


