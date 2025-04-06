# Proxmox LXC Templates

`netbox-proxmox-automation` is intended to make your life as simple as possible.  Once you have a working Proxmox node (or cluster), have provisioned a Proxmox API token (the permission is able to manage both VMs and storage), a NetBox instance, a NetBox API token, the entire process of managing Proxmox VMs via NetBox involves these simple requirements.

  1. You have defined a webhook that will be used to facilitate your automation
  2. You have defined an event rule that uses the webhook in Step 1 -- for automating Proxmox VM operations based on VM state in NetBox
  3. You have a web application that handles events via webhooks

    - [netbox-webhook-flask-app](https://github.com/netboxlabs/netbox-proxmox-automation/tree/main/netbox-webhook-flask-app) is a web application that you can use to facilitate Proxmox automation by handling event rules from NetBox.
    
        *-or-*
    
    - You are running AWX and have created (job) templates to handle events via webhooks


## Initial Configuration: Working with LXC (Linux Container) in Proxmox

This is documented [here](https://pve.proxmox.com/wiki/Linux_Container).  *Before you can use `netbox-proxmox-automation`, you must have downloaded at least one LXC container, as documented in the previous link, on your Proxmox node.*

