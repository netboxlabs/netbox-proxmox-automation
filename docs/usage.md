# Usage

`netbox-proxmox-automation` currently implements two automation use cases:
1. NetBox webhooks and event rules will use AWX or Tower/AAP to induce Proxmox automation
2. NetBox webhooks and event rules will use a Flask application to induce Proxmox automation

## What this implementation *is*

`netbox-proxmox-automation` is an implementation where you defined your *desired* VM states in NetBox.  Your desired VM state in NetBox then gets synchronized to Proxmox.

`netbox-proxmox-automation` uses cloud-init images to induce VM changes on Proxmox based on the *desired* state in NetBox.  Almost always these cloud-init images will be Debian or Debian-derived images (e.g. Debian or Ubuntu), RHEL-derived images (e.g. Rocky Linux), or maybe even Windows-based cloud-init images.  *(Windows cloud-init images are currently un-tested.)*  While you should be able to use a cloud-init image of choice with this automation, and due to the uncertain future of RHEL-derived Linuxes, *only* Ubuntu/Debian cloud images (cloud-init) are supported for the time being.  We welcome any reports around other cloud-init images, and will merge in this functionality as we are able.

Proxmox is highly conducive to using cloud-init images -- when cloud-init images are converted to templates.  You can define items like ssh keys and network configurations in Proxmox by way of using cloud-init images, and cloud-init will cascade these settings into your Proxmox VMs: *Dynamically*.  Further, Proxmox has a comprehensive API -- you can define VM resources, plus disk configurations and more -- where you can leverage automation to lay down your desired VM states in Proxmox with little effort.

NetBox models VMs in an intuitive way.  You can define roles for VMs, such as for Proxmox, and from there you can define both VM state (Active, Offline, etc) and other resources like vcpus, memory, network configuration, disks, and more (through customizations in NetBox).

This automation is based on the premise(s) that:

  1. You are using Python (version 3)
  2. You are using NetBox 4.1.0 or newer (NetBox 3.7.x should also work)
  3. You have a running Proxmox instance or cluster
  4. You have a running [AWX](https://github.com/ansible/awx) instance or are running [your own web service](https://github.com/netboxlabs/netbox-proxmox-automation/tree/main/example-netbox-webhook-flask-app) to handle webhooks and event rules
  5. You have converted a cloud-init image to a Proxmox VM template
  6. Your Promox VM template(s) has/have qemu-guest-agent installed, and that qemu-guest-agent has been enabled via cloud-init
  7. You have access to the NetBox and Proxmox APIs (via API tokens, respectively)
  8. Your NetBox API token and its underlying privileges can create, modify, and delete objects in NetBox
  9. Your Proxmox API token and its underlying privileges can both manage VMs and storage (query, create, delete, etc)

## What this implementation *is not*

`netbox-proxmox-automation` is not currently a NetBox plugin, but this may change.

[ProxBox](https://github.com/netdevopsbr/netbox-proxbox) is a neat implementation of pulling information from Proxmox into NetBox.  ProxBox has its place, most certainly, but what it does is *not* the aim of `netbox-proxmox-automation`.

Further, `netbox-proxmox-automation` does *not* deploy a future state for any Proxmox VM.  For example, let's say you deploy a Proxmox VM called 'vm1' and it's intended to be a(n) LDAP server.  The scope of `netbox-proxmox-automation` is to ensure that each VM that you document/model and deploy to Proxmox has a consistent baseline configuration, from which you can take future automation steps.  NetBox will document/model your *desired* Proxmox VM state, but additional automation states like package installations and configurations are left up to further automation that you might choose to do once your vitual machine is running in Proxmox.  As `netbox-proxmox-automation` is free for you to use and/or modify, you are welcome to introduce subsequent automations to `netbox-proxmox-automation` in your own environment.

