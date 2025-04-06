# NetBox Proxmox Automation

[NetBox](https://github.com/netbox-community/netbox) is the world's most popular Network Source of Truth (NSoT) with tens of thousands of installations globally.  It is used extensively for documenting/modeling networks (network devices, virtual machines, etc), and also provides a great IPAM solution.  [Proxmox](https://www.proxmox.com/en/) is a freely available virtualization technology that allows you to deploy virtual machines (VMs) at scale, and perhaps in a clustered configuration.  Proxmox has approximately [900,000 hosts and more than 130,000 users in its open source community](https://www.proxmox.com/en/about/press-releases/proxmox-virtual-environment-8-1).

When you think of the challenges of a widely used network documentation solution and a widely used virtualization technology, this implementation is an integration between virtual machine documentation (NetBox) and the automation of Proxmox virtual machine (VM) and container (LXC) deployment and configuration.

This automation handles creation, removal, and changes of/to Proxmox VMs *and* LXCs.  The underlying automation uses [webhooks](https://demo.netbox.dev/static/docs/additional-features/webhooks/) and [event rules](https://netboxlabs.com/docs/netbox/en/stable/features/event-rules/) in NetBox.  When you induce a change in NetBox, this will set the desired VM state(s) in Proxmox.

When you create/update/delete VM objects (for Proxmox VM) in NetBox, the following will take place in Proxmox:

- when you create a VM object in NetBox (name, status == Staged, VM Type == Virtual Machine, chosen Proxmox VM template name), this will clone a VM in Proxmox of the same name, from the defined template
- when you add a SSH key to a NetBox VM object (status == Staged), a SSH key will be added to the VM settings in Proxmox
- when you add a primary IP address to a NetBox VM object (status == Staged), this will update the VM settings in Proxmox for ipconfig0
- when you add or resize VM disks (scsi0 - scsiN) for a NetBox VM object (status == Staged), this will:
    - resize scsi0 on the Proxmox VM to the size that was defined in NetBox
    - create scsi1 - scsiN on the Proxmox VM and set them to their specified sizes
    - resize scsi1 - scsiN on the Proxmox VM and resize them to their specified sizes (*NOTE: Proxmox does not allow you to shrink disks!*)
- when you remove a disk or disks from a NetBox VM object, this will remove the corresponding disks from the Proxmox VM (*NOTE: this does not include scsi0 as that is the OS disk*)

Further:

- when you set a VM's state to 'Active' in NetBox, this will start a VM in Proxmox
- when you set a VM's state to 'Offline' in NetBox, this still stop a VM in Proxmox
- when you remove a VM from NetBox, this will stop and remove a VM in Proxmox.

When you create/update/delete VM objects (for Proxmox LXC) in NetBox, the following will take place in Proxmox:

- when you create a VM object in NetBox (name, status == Staged, VM Type == LXC Container, chosen Proxmox VM template name, defined public SSH key), this will clone a LXC in Proxmox of the same name, from the defined template, and will also set the public SSH key (*NOTE: In LXC, you can only set the public SSH key once, and that's during the cloning process!*)
- when you add a primary IP address to a NetBox VM object (status == Staged), this will update the VM settings in Proxmox for netif for the LXC
- when you add or resize the VM disk (rootfs) for a NetBox VM object (status == Staged), this will:
    - resize rootfs on the Proxmox LXC to the size that was defined in NetBox

Further:

- when you set a VM's state to 'Active' in NetBox, this will start a LXC in Proxmox
- when you set a VM's state to 'Offline' in NetBox, this still stop a LXC in Proxmox
- when you remove a VM from NetBox, this will stop and remove a LXC in Proxmox.
