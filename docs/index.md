# NetBox Proxmox Automation (netbox-proxmox-automation)

[NetBox](https://github.com/netbox-community/netbox) is a widely used tool for documenting/modeling networks (network devices, virtual machines, etc), and also provides a great IPAM solution.  [Proxmox](https://www.proxmox.com/en/) is a freely available virtualization technology that allows you to deploy virtual machines (VMs) at scale, and perhaps in a clustered configuration.  NetBox has approximately 15,000 users in its open source community.  Proxmox has approximately [900,000 hosts and more than 130,000 users in its open source community](https://www.proxmox.com/en/about/press-releases/proxmox-virtual-environment-8-1).

When you think of the challenges of a widely used network documentation solution and a widely used virtualization technology, this implementation is an integration between virtual machine documentation (NetBox) and the automation of virtual machine (VM) configurations (Proxmox).

This automation handles creation, removal, and changes of/to Proxmox VMs.  The underlying automation uses [webhooks](https://demo.netbox.dev/static/docs/additional-features/webhooks/) and [event rules](https://netboxlabs.com/docs/netbox/en/stable/features/event-rules/) in NetBox.  When you induce a change in NetBox, this will set the desired VM state(s) in Proxmox.

When you create VM objects in NetBox, the following will take place in Proxmox:
- when you create a VM object in NetBox (name, status == Staged, chosen Proxmox VM template name), this will clone a VM in Proxmox of the same name, from the defined template
- when you add a SSH key and/or primary IP address to a NetBox VM object (status == Staged), this will update the VM settings in Proxmox -- adding ipconfig0 and ssh key settings
- when you add disks (scsi0 - scsiN) to a NetBox VM object (status == Staged), this will:
  - resize scsi0 on the Proxmox VM to the size that was defined in NetBox
  - create scsi1 - scsiN on the Proxmox VM and set them to their specified sizes
- when you remove a disk or disks from a NetBox VM object, this will remove the corresponding disks from the Proxmox VM (*NOTE: this does not include scsi0 as that is the OS disk*)

Further:
- when you set a VM's state to 'active' in NetBox, this will start a VM in Proxmox
- when you set a VM's state to 'offline' in NetBox, this still stop a VM in Proxmox
- when you remove a VM from NetBox, this will stop and remove a VM in Proxmox.
