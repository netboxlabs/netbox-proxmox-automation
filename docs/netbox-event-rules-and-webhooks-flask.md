# Initial Configuration: NetBox Event Rules and Webhooks (Flask application)

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


### Flask Application

You will need to have a running Flask application *before* you can start handling events (i.e. object changes) inside of NetBox.

#### Automated Webhook and Event Rules Configuration

If you'd prefer to manually create the webhook and event rules in NetBox, you can skip to the next section.  Otherwise, proceed with the following to automate the creation of the webhook and event rules in NetBox.

`netbox-proxmox-automation` version 1.1.0 and newer ships with a convenience script, `netbox_setup_webhook_and_event_rules.py`, that when used alongside a configuration file of your choice, will greatly simplify this process.

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
automation_type: flask_application
flask_application:
  host: name or ip of where Flask application is running
  http_proto: http or https
  http_port: 9000 or whatever
  ssl_verify: false # or true
  netbox_webhook_name: "netbox-proxmox-webhook"
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

Then verify that everything has been created.  In the end, you should see a singular webhook and a series of event rules.

