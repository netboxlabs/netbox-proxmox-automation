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

As noted earlier, AWX/Tower/AAP will perform Proxmox automation through separate (project) templates.  This section walks you through how (NetBox) webhooks and (NetBox) event rules are handled by AWX.

#### AWX/Tower/AAP Webhook

To use NetBox webhooks with AWX, each NetBox webhook for Proxmox VM management will point at a separate AWX (project) template.  In AWX, each (project) template has a unique ID.  When we execute a webhook in NetBox, in this case we're using AWX, the (NetBox) webhook will in turn point at the (project) template ID in AWX -- and tell AWX to launch the template, i.e. to run the automation.

AWX webhooks are created this way in NetBox.

![NetBox Proxmox AWX webhooks image](./images/netbox-awx-webhooks.png)

Let's take a look at the `proxmox-vm-create-and-set-resources-awx` webhook.

![NetBox Proxmox VM Create and Set Resources AWX webhook image](./images/netbox-proxmox-vm-create-and-set-resources-awx-webhook.png)

Regardless of which AWX template you use as a (NetBox) webhook, you must include the following when you define the webhook in NetBox.

- HTTP Method: POST
- Payload URL: http(s)://hostname:port/api/v2/job_templates/JOBTEMPLATEID/launch/
- HTTP Content Type: application/json
- Additional Headers: Authorization: Basic BASE64-ENCODED-AWX-USER-AND-PASSWORD
- Body Template
  - *Must* set `extra_vars` in JSON format
  - In this example, set `extra_vars['vm_config']` (JSON format) to include what was shown in the image above.

`proxmox-remove-vm-awx` webhook

![NetBox Proxmox remove VM AWX webhook image](./images/proxmox-remove-vm-awx.png)

`proxmox-start-vm-awx` webhook

![NetBox Proxmox start VM AWX webhook image](./images/proxmox-start-vm-awx.png)

`proxmox-stop-vm-awx` webhook

![NetBox Proxmox stop VM AWX webhook image](./images/proxmox-stop-vm-awx.png)

`proxmox-vm-add-disk-awx` webhook

![NetBox Proxmox stop VM AWX webhook image](./images/proxmox-vm-add-disk-awx.png)

`proxmox-vm-assign-ip-address-awx` webhook

![NetBox Proxmox VM assign IP address AWX webhook image](./images/proxmox-vm-assign-ip-address-awx.png)

`proxmox-vm-configure-ipconfig0-and-ssh-key-awx` webhook

![NetBox Proxmox VM configure ipconfig0 and ssh key AWX webhook image](./images/proxmox-vm-configure-ipconfig0-and-ssh-key-awx.png)

`proxmox-vm-remove-disk-awx` webhook

![NetBox Proxmox VM remove disk AWX webhook image](./images/proxmox-vm-remove-disk-awx.png)

`proxmox-vm-resize-disk-awx` webhook

![NetBox Proxmox VM resize disk AWX webhook image](./images/proxmox-vm-resize-disk-awx.png)


#### AWX/Tower/AAP Event Rules

Now let's take a look at the NetBox event rules that call an AWX webhook (project template) with Proxmox VM and VM disk object changes in Netbox.

![NetBox Proxmox VM event rules AWX image](./images/netbox-proxmox-event-rules-awx.png)

`proxmox-vm-create-and-set-resources`

![NetBox Proxmox VM create and set resources event rule AWX image](./images/proxmox-vm-create-and-set-resources-awx-event-rule.png)

`proxmox-resize-vm-disk`

![NetBox Proxmox VM resize VM disk event rule AWX image](./images/proxmox-resize-vm-disk-awx-event-rule.png)

`proxmox-set-ipconfig-and-ssh-key`

![NetBox Proxmox VM set ipconfig and ssh key event rule AWX image](./images/proxmox-set-ip-config-and-ssh-key-awx-event-rule.png)

`proxmox-vm-active`

![NetBox Proxmox VM set active event rule AWX image](./images/proxmox-vm-active-awx-event-rule.png)

`proxmox-vm-add-disk`

![NetBox Proxmox VM add disk event rule AWX image](./images/proxmox-vm-add-disk-awx-event-rule.png)

`proxmox-vm-offline`

![NetBox Proxmox VM offline event rule AWX image](./images/proxmox-vm-offline-awx-event-rule.png)

`proxmox-vm-remove`

![NetBox Proxmox VM remove event rule AWX image](./images/proxmox-vm-remove-awx-event-rule.png)

`proxmox-vm-remove-disk`

![NetBox Proxmox VM remove disk event rule AWX image](./images/proxmox-vm-remove-disk-awx-event-rule.png)

`proxmox-vm-resize-os-disk`

![NetBox Proxmox VM resize OS disk event rule AWX image](./images/proxmox-vm-resize-os-disk-awx-event-rule.png)

