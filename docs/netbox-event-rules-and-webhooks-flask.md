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

As noted [here](#initial-configuration-flask-application-python), you will need to have a running Flask application *before* you can start handling events (i.e. object changes) inside of NetBox.

#### Flask Application: Webhook

`example-netbox-webhook-flask-app` implements a catch-all for virtual machine events that happen in NetBox.  Events will call the webhook, and in turn the webhook will dispatch Proxmox VM changes via the Proxmox API.

You need to create the webhook, in NetBox, first.  Navigate over to Operations > Integrations > Webhooks, and add something like the following.  *This, and the IP address of where you are running the Flask application, needs to match what you defined `netbox_webhook_name` in `app_config.yml`.*

```
(venv) shell$ grep netbox_webhook_name app_config.yml
netbox_webhook_name: "netbox-proxmox-webhook"
```

In this case, our URI will be `netbox-proxmox-webhook` (the trailing slash is critical!), and our webhook will be listening on the public interface and port that were specified when we started our Flask application.  When you add the webhook to NetBox (use the '+' button), it should look something like this.

![netbox-proxmox-flask-app-webhook-image](./images/netbox-proxmox-flask-app-webhook.png)

#### Flask Application: Event Rules

You will need to add the following event rules to NetBox to update Proxmox when virtual machines have been created, updated, and/or deleted.
1. `proxmox-vm-add-disk` takes a Proxmox virtual machine disk that was added to NetBox then automates disk addition in Proxmox

![Netbox Proxmox VM add disk image](./images/proxmox-vm-add-disk.png)

2. `proxmox-vm-created` takes a Proxmox virtual machine that was created in NetBox then automates Proxmox VM cloning; the Proxmox VM in NetBox status should be set to 'Staged', and the selected Proxmox VM template cannot be null

![NetBox Proxmox VM created image](./images/proxmox-vm-created.png)

3. `proxmox-vm-delete-disk` takes a Proxmox virtual machine disk that was removed from NetBox then removes the non-OS disk from Proxmox; this *does not* include `scsi0`, which is the OS disk that's been provisioned in Proxmox

![NetBox Proxmox VM delete disk image](./images/proxmox-vm-delete-disk.png)

4. `proxmox-vm-deleted` takes a Proxmox virtual machine that was deleted from NetBox then stops/removes the VM from Proxmox

![NetBox Proxmox VM deleted image](./images/proxmox-vm-deleted.png)

5. `proxmox-vm-resize-disk` takes a Proxmox virtual machine disk that was changed in NetBox then resizes the disk in Proxmox (*cannot downsize a disk, by design*); this can be used for *any* Proxmox VM disk

![NetBox Proxmox VM resize disk image](./images/proxmox-vm-resize-disk.png)

6. `proxmox-vm-started` takes a Proxmox virtual machine whose state was changed to 'Active' in NetBox and starts the VM in Proxmox

![NetBox Proxmox VM started image](./images/proxmox-vm-started.png)

7. `proxmox-vm-stopped` takes a Proxmox virtual machine whose state was changed to 'Offline' in NetBox and stops the VM in Proxmox

![NetBox Proxmox VM stopped image](./images/proxmox-vm-stopped.png)

8. `proxmox-vm-update-network-config` takes a Proxmox virtual machine whose network configuration was changed in NetBox (IP address, SSH public key), with the NetBox status set to 'Staged', and adds those network configuration settings to Proxmox

![NetBox Proxmox VM update network config image](./images/proxmox-vm-update-network-config.png)

9. `proxmox-vm-updated` takes any Proxmox virtual machine updates (vcpus, memory, etc) in NetBox, where the Proxmox VM status is set to 'Staged', and changes those settings in Proxmox

![NetBox Proxmox VM updated](./images/proxmox-vm-updated.png)

