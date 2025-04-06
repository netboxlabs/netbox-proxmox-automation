# Initial Configuration: NetBox Event Rules and Webhooks (AWX/Tower/AAP)

There are two key components to automating Proxmox VM management in NetBox.

1. webhooks
2. event rules

A webhook in NetBox will consume the payload of data from an event rule.  An event rule announces changes to an object type inside of NetBox (in this case, a Virtual Machine and its related object types) -- then sends the payload of data around those changes to a webhook.  The webhook will handle the Proxmox automation(s) as you've defined it/them.

For the sake of automation, every event rule that you create in NetBox requires either a Webhook or a Script.

Regardless of whether you are using a Flask (or other) application for Proxmox automation, or you are using AWX/Tower/AAP, this automation should trigger anytime that a Proxmox VM is changed in NetBox such that:

- a Proxmox VM has been created in NetBox with a status of 'Staged'
- a Proxmox VM in NetBox (with a status of 'Staged') has a changed network configuration
- a Proxmox VM in NetBox (with a status of 'Staged') adds new disks
- a Proxmox VM in NetBox (with a status of 'Staged') has a changed disk configuration
- a Proxmox VM in NetBox has been set to a status of 'Active'
- a Proxmox VM in NetBox has been set to a status of 'Offline'
- a Proxmox VM in NetBox has been removed


### AWX/Tower/AAP

As noted earlier, AWX/Tower/AAP will perform Proxmox automation through separate (job) templates.  This section walks you through how (NetBox) webhooks and (NetBox) event rules are handled by AWX.

#### Automated Webhook and Event Rules Configuration

If you'd prefer to manually create the webhook and event rules in NetBox, you can skip to the next section.  Otherwise, proceed with the following to automate the creation of the webhook and event rules in NetBox.

`netbox-proxmox-automation` version 1.1.0 and newer ships with a convenience script, `netbox_setup_webhook_and_event_rules.py`, that when used alongside a configuration file of your choice, will greatly simplify this process.  In the case of AWX/Tower/AAP, `netbox_setup_webhook_and_event_rules.py` will query your AWX/Tower/AAP instance for project and template(s) information; this information will then be used to create the corresponding webhooks and event rules in NetBox.

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
automation_type: ansible_automation
ansible_automation:
  host: name or ip of AWX/Tower/AAP host
  http_proto: http or https
  http_port: 80 or whatever
  ssl_verify: false # or true
  username: awx_user # should have permissions to view both projects and templates
  password: awx_password
  project_name: netbox-proxmox-ee-test1 # or whatever you named your project
```

Usage:

```
shell$ cd setup

shell$ pwd
/some/path/netbox-proxmox-automation/setup

shell$ python3 -m venv venv

shell$ source venv/bin/activate

(venv) shell$ pip install -r requirements.txt

(venv) shell$ ./netbox_setup_webhook_and_event_rules.py --config /path/to/your/configuration.yml
```

Then verify that everything has been created.
