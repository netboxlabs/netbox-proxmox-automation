# netbox-proxmox-automation

## Clone and step into the repo

```
# git clone https://github.com/netboxlabs/netbox-proxmox-automation/
# cd netbox-proxmox-automation
```

## Install required python packages

```
# python3 -m venv venv
# source venv/bin/activate
(venv) # pip install -r requirements.txt
```

## Run mkdocs

```
(venv) # mkdocs serve
INFO    -  Building documentation...
INFO    -  Cleaning site directory
INFO    -  The following pages exist in the docs directory, but are not included in the "nav" configuration:
             - Administration Console/console-overview.md
             - NetBox Cloud/getting-started-with-nbc.md
INFO    -  Documentation built in 0.75 seconds
INFO    -  [13:37:39] Watching paths for changes: 'docs', 'mkdocs.yml'
INFO    -  [13:37:39] Serving on http://127.0.0.1:8000/
```

## :warning:

If you see errors like this...

> ERROR   -  Config value 'theme': Unrecognised theme name: 'material'. The available installed themes are: mkdocs, readthedocs
> ERROR   -  Config value 'markdown_extensions': Failed to load extension 'pymdownx.tabbed'.
>            ModuleNotFoundError: No module named 'pymdownx'


 Try uninstalling `mkdocs` from your package manager, (e.g. `brew uninstall mkdocs`) and just using the version installed by `pip`. It seems that `mkdocs` doesn't like it when you've installed it using different methods.

# Project Summary

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


## Usage

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
  4. You have a running [AWX](https://github.com/ansible/awx) instance or are running [your own web service](./example-netbox-webhook-flask-app) to handle webhooks and event rules
  5. You have converted a cloud-init image to a Proxmox VM template
  6. Your Promox VM template(s) has/have qemu-guest-agent installed, and that qemu-guest-agent has been enabled via cloud-init
  7. You have access to the NetBox and Proxmox APIs (via API tokens, respectively)
  8. Your NetBox API token and its underlying privileges can create, modify, and delete objects in NetBox
  9. Your Proxmox API token and its underlying privileges can both manage VMs and storage (query, create, delete, etc)

## What this implementation *is not*

`netbox-proxmox-automation` is not currently a NetBox plugin, but this may change.

[ProxBox](https://github.com/netdevopsbr/netbox-proxbox) is a neat implementation of pulling information from Proxmox into NetBox.  ProxBox has its place, most certainly, but what it does is *not* the aim of `netbox-proxmox-automation`.

Further, `netbox-proxmox-automation` does *not* deploy a future state for any Proxmox VM.  For example, let's say you deploy a Proxmox VM called 'vm1' and it's intended to be a(n) LDAP server.  The scope of `netbox-proxmox-automation` is to ensure that each VM that you document/model and deploy to Proxmox has a consistent baseline configuration, from which you can take future automation steps.  NetBox will document/model your *desired* Proxmox VM state, but additional automation states like package installations and configurations are left up to further automation that you might choose to do once your vitual machine is running in Proxmox.  As `netbox-proxmox-automation` is free for you to use and/or modify, you are welcome to introduce subsequent automations to `netbox-proxmox-automation` in your own environment.

# Installation

`netbox-proxmox-automation` is intended to make your life as simple as possible.  Once you have a working Proxmox node (or cluster), have provisioned a Proxmox API token with the permissions noted above, a NetBox instance, a NetBox API token, the entire process of managing Proxmox VMs via NetBox involves three simple requirements.

  1. You have defined event rules and webhooks for VM operations in NetBox
  2. You have a web service that handles events via webhooks
  - You are running a web service that handles events via webhooks, e.g. [example-netbox-webhook-flask-app](example-netbox-webhook-flask-app) *-or-*
  - You are running AWX and have created templates to handle events via webhooks


## Initial Configuration: Creating Proxmox VM templates from (cloud-init) images

`netbox-proxmox-automation` *only* supports cloud-init images.  The dynamic nature of Proxmox VM automation requires this implementation to be able to set things, during the Proxmox VM provisioning process, like network configuration, hostnames, and more.  While it's *possible* that `netbox-proxmox-automation` *might* support your existing Proxmox VM templates, it's *highly* recommended that you follow the procedure below -- for the best results.

As a cloud-init image is basically "blank", meaning that there is not broad network or SSH key configuration, this allows us to have total flexibility in the way that this automation takes a *desired* Proxmox VM state from NetBox and generates anticipated changes to VMs -- in Proxmox.

This process is [well documented](https://pve.proxmox.com/wiki/Cloud-Init_Support) by the Proxmox team.  In the end it comes down to:
- logging into your Proxmox node(s) and running these commands as the 'root' user, or as a user who has adequate permissions to modify Proxmox VMs and the underlying storage
- downloading a cloud image
- following the documented process in the previous link
- ensuring that your cloud-init image has included `qemu-guest-agent`; `qemu-guest-agent` is *required* for the discovery of network interfaces/settings and underlying platform information
- converting your cloud-init image to a Proxmox VM template

The automated VM cloning and configuration process will handle IP allocation/configuration, host naming, ssh key configuration and more.  The default user for an Ubuntu cloud image is always 'ubuntu'; please refer to the documentation (about default users) for other cloud images.

The first step before modifying cloud-init images, obviously, is to download the cloud-init images.  Here's an example that will download the jammy, focal, and noble releases of Ubuntu, in parallel, as root, to a Proxmox node.

```
proxmox-ve-node# cd /root

proxmox-ve-node# mkdir -p cloud-images/ubuntu

proxmox-ve-node# cd cloud-images/ubuntu

proxmox-ve-node# for r in jammy focal noble; do wget "https://cloud-images.ubuntu.com/${r}/current/${r}-server-cloudimg-amd64.img" & done
```

Then let the cloud-init images download.  Once the downloads have completed, you might want to take backups of the original cloud-init images -- as we will proceed with modifying these cloud-init images slightly before converting them to Proxmox VM templates.  Taking backups of the original cloud-init images is helpful should you ever need to revert any customization you did before converting the cloud-init images into Proxmox VM templates.  Run this, again, as 'root' on the proxmox-node of your choice.

```
proxmox-ve-node# cd /root/cloud-images/ubuntu

proxmox-ve-node# for img in `ls -1 *img`; do cp -pi $img $img.$(date +%Y-%m-%d); done
```

Now let's start preparing our cloud-init images so that we can convert them to Proxmox VM templates.  We'll use the Ubuntu ('jammy') cloud image to illustrate this process.  You can use whatever cloud image you want to implement this process.

You will need to install the `virt-customize` and `virt-sysprep` tools on your Proxmox node, as the 'root' user.  These are part of the `guestfs-tools` package, which might or might not have been installed when you installed Proxmox initially.

```
proxmox-ve-node# apt-get update ; apt-get install guestfs-tools
```

Let's start working on the Ubuntu ('jammy') cloud-init image, as the 'root' user on our Proxmox node.  You'll need to use `virt-customize` for this step.  We are going to install `qemu-guest-agent` on the Ubuntu ('jammy') cloud-init image: `virt-customize -a jammy-server-cloudimg-amd64.img --install qemu-guest-agent`

Output should be something like this if things have succeeded.

```
[   0.0] Examining the guest ...
[  10.5] Setting a random seed
virt-customize: warning: random seed could not be set for this type of 
guest
[  10.5] Setting the machine ID in /etc/machine-id
[  10.5] Installing packages: qemu-guest-agent
[  32.8] Finishing off
```

Run `virt-sysprep` to start resetting the cloud-init image -- ahead of cloning it to a Proxmox VM later on.

```
proxmox-ve-node# virt-sysprep -a jammy-server-cloudimg-amd64.img
[   0.0] Examining the guest ...
[   3.7] Performing "abrt-data" ...
[   3.7] Performing "backup-files" ...
[   4.2] Performing "bash-history" ...

... etc ...

[   4.7] Performing "utmp" ...
[   4.7] Performing "yum-uuid" ...
[   4.7] Performing "customize" ...
[   4.7] Setting a random seed
virt-sysprep: warning: random seed could not be set for this type of guest
[   4.8] Setting the machine ID in /etc/machine-id
[   4.8] Performing "lvm-uuids" ...
```

Notice how `virt-sysprep` set `/etc/machine-id`.  We don't want that -- as the same machine-id will carry over to all Proxmox VMs when they are cloned.  Therefore, we need to truncate `/etc/machine-id` so that it will be automatically created as each Proxmox VM is provisioned.

```
proxmox-ve-node# virt-customize -a jammy-server-cloudimg-amd64.img --truncate /etc/machine-id  
[   0.0] Examining the guest ...
[   3.8] Setting a random seed
virt-customize: warning: random seed could not be set for this type of 
guest
[   3.8] Truncating: /etc/machine-id
[   3.8] Finishing off
```

Now we are ready to create a Proxmox VM from the Ubuntu ('jammy') cloud-init image -- that we have modified.  This breaks down into two (high-level) steps:
1. Create a Proxmox VM, with a unique id, with various configuration options
2. Convert the Proxmox VM into a Proxmox VM template

First, create the Proxmox VM, with a unique id, and configure its attributes.  We tend to use unique ids >= 9000 for Proxmox VM templates, but you do as you will.  *Note that you cannot use duplicate VM ids in Proxmox.*  You will need to run the `qm` command, as the 'root' user, on your Proxmox node, to configure the following Proxmox VM attributes:

- create the Proxmox VM
- import the cloud-init image to the Proxmox VM
- set the SCSI (disk) hardware attributes for the Proxmox VM root disk
- map an IDE disk to the cloud-init image
- define a boot disk for the Proxmox VM
- define a serial port such that the Proxmox VM is accessible through the Proxmox console
- set the QEMU agent to be enabled such that you can access various information from `qemu-guest-agent` when the Proxmox VM is running

Regarding where you store the Ubuntu ('jammy') cloud-init image, you likely have options between faster and slower disks on your Proxmox nodes.  It's recommended that you store the Ubuntu ('jammy') cloud-init image on faster disks; this will lead to better VM cloning performance.  Let's see which disks are available to us in Proxmox; in this case an SSD comprises our root volume, which is called 'local-lvm'.  There is a slower spinning drive configuration that's called 'pve-hdd'.

```
proxmox-ve-node# pvesh get /storage --output-format yaml
---
- content: images,rootdir
  digest: 0b59487c0e528e7eabc9293079ac26389ac1b91b
  storage: local-lvm
  thinpool: data
  type: lvmthin
  vgname: pve
- content: iso,backup,vztmpl
  digest: 0b59487c0e528e7eabc9293079ac26389ac1b91b
  path: /var/lib/vz
  storage: local
  type: dir
- content: rootdir,images
  digest: 0b59487c0e528e7eabc9293079ac26389ac1b91b
  nodes: proxmox-ve
  shared: 0
  storage: pve-hdd
  type: lvm
  vgname: pve-hdd
```

As noted, 'local-lvm' is our SSD storage, so let's use that.  We'll need to keep track of the name 'local-lvm' as it's required when running the `qm` commands.

Here's the procedure to create a Proxmox VM from the Ubuntu ('jammy') cloud-init image.

```
proxmox-ve-node# qm create 9000 --name jammy-server-cloudimg-amd64-template --ostype l26 --cpu cputype=host --cores 1 --sockets 1 --memory 1024 --net0 virtio,bridge=vmbr0

proxmox-ve-node# # qm list | grep jammy
      9000 jammy-server-cloudimg-amd64-template stopped    1024               0.00 0         


proxmox-ve-node# qm importdisk 9000 jammy-server-cloudimg-amd64.img local-lvm -format qcow2
importing disk 'jammy-server-cloudimg-amd64.img' to VM 9001 ...
format 'qcow2' is not supported by the target storage - using 'raw' instead
  Logical volume "vm-9001-disk-1" created.
transferred 0.0 B of 2.2 GiB (0.00%)
transferred 22.5 MiB of 2.2 GiB (1.00%)

... etc ...

transferred 2.2 GiB of 2.2 GiB (99.64%)
transferred 2.2 GiB of 2.2 GiB (100.00%)
Successfully imported disk as 'unused0:local-lvm:vm-9000-disk-0'


proxmox-ve-node# qm set 9000 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-9000-disk-0
update VM 9000: -scsi0 local-lvm:vm-9000-disk-0 -scsihw virtio-scsi-pci


proxmox-ve-node# qm set 9000 --ide2 local-lvm:cloudinit
update VM 9000: -ide2 local-lvm:cloudinit
  Logical volume "vm-9000-cloudinit" created.
ide2: successfully created disk 'local-lvm:vm-9000-cloudinit,media=cdrom'
generating cloud-init ISO


proxmox-ve-node# qm set 9000 --boot c --bootdisk scsi0
update VM 9000: -boot c -bootdisk scsi0


proxmox-ve-node# qm set 9000 --serial0 socket --vga serial0
update VM 9000: -serial0 socket -vga serial0


proxmox-ve-node# qm set 9000 --agent enabled=1
update VM 9000: -agent enabled=1
```

Second, convert the Proxmox VM into a template.  You can then use this Proxmox VM template in your `netbox-proxmox-automation` automation.

Now convert the Proxmox VM to a template.  *Note that this cannot be undone!*

```
proxmox-ve-node# qm template 9000
  Renamed "vm-9000-disk-0" to "base-9000-disk-0" in volume group "pve"
  Logical volume pve/base-9000-disk-0 changed.
```

You should now be able to use your Proxmox VM template, with a VM id (vmid) of 9000 (or whatever you choose) in your `netbox-proxmox-automation` automation.

## Initial Configuration: NetBox objects + dependencies

Given the heirarchical nature of NetBox, you will need to create the following objects before using `netbox-proxmox-automation` automation.  You should refer to the [NetBox planning guide](https://netboxlabs.com/docs/netbox/en/stable/getting-started/planning/) to address these dependencies before proceeding with `netbox-proxmox-automation`.

Using NetBox's IPAM is a *requirement* of `netbox-proxmox-automation`.  This is because `netbox-proxmox-automation` is going to either assign a defined IP address to a specified inteface (or interfaces) on a Proxmox VM, or it's going to request an available IP address from NetBox's IPAM -- and assign the requested IP address to an interface (or interfaces) on a Proxmox VM.

Ahead of using this automation, make sure to create the following IPAM-related objects in NetBox:
- IPAM > RIRs
- IPAM > Aggregates (relate each aggregate to RIR)
- IPAM > Prefixes (use containers and set Active state for each active previx)

## Initial Configuration: NetBox API user + key

It is recommended that you do *not* create an API token for the NetBox 'admin' user.  Instead, create a new user in NetBox; then create a new permission for that API user -- that has sufficient read/write/modify permissions to modify the following object types in NetBox, at a minimum:

  - Devices
  - Interfaces (devices and VMs)
  - VMs (groups, clusters, VMs)

### Create NetBox User + Group
 
In the NetBox UI:

1. Navigate to Admin > Users
2. Create a new user called `api_user`, or a user of your choice
3. Navigate to Admin > Groups
4. Create a new group called `api_user_group`, or a group of your choice
5. Navigate to Admin > Users, select `api_user` (or the user that you created), click the Edit button, and associate `api_user` with the group that you just created.

### Create NetBox Permissions

In the Netbox UI:

1. Navigate to Admin > Permissions
2. Create a new permission called `api_user_permissions` (or whatever you want to call it) and ensure that this permission has read/write/update/delete rights for the object types, at a minimum, noted above.  Associate the user and/or group with the permission that you've created.

### Create NetBox API Token

While it is possible to use passwords with the Netbox Ansible collection, `netbox-proxmox-automation` does not allow this behavior.  Instead a NetBox API token is required.

In the NetBox UI:

1. Navigate to Admin > API Tokens
2. Add a new token, associating it with `api_user`, with the following characteristics: Write enabled (you can select other characteristics if you wish)

Once you've created a NetBox API token, store it some place safe in the meantime; (most) NetBox installations will obscure the API token once it's been created.

## Initial Configuration: NetBox Customization

You will need to do some customization to NetBox to define the underlying Proxmox VM configuration(s).  This section covers the custom field choices and custom fields that you'll need to create in NetBox -- in order for you to facilitate automation.

### NetBox Customization: Custom Field Choices (for Proxmox VM templates and storage)

In the NetBox UI, you will need to create the following custom field choices.
1. `proxmox-node` will be used to correlate a Proxmox node to the Proxmox VM that you will provision
2. `proxmox-vm-templates` will be used to correlate a Proxmox VM template with the Proxmox VM that you will provision
3. `proxmox-vm-storage` will be used to correlate an underlying Proxmox VM storage volume with the Proxmox VM you will provision

In the NetBox UI, navigate to Customization > Custom Field Choices


#### proxmox-node

Create custom field choices for Proxmox VM Node(s).  When you click the '+' button, you will be presented with an Edit screen.  Fill the form as shown below.  Note that your choices will represent a list of Proxmox cluster nodes.  You will need to login to the Proxmox UI to get the list of Proxmox cluster nodes.

![Screenshot of Proxmox VM Cluster Nodes Edit screen](./images/proxmox-cluster-nodes-edit.png)

When you are done, your Custom Field Choices for Proxmox VM node(s) should look like this.

![Screenshot of Proxmox VM Cluster Nodes View screen](./images/proxmox-cluster-nodes-saved.png)


#### proxmox-vm-templates

Create custom field choices for Proxmox VM Templates.  When you click the '+' button, you will be presented with an Edit screen.  Fill the form as shown below.  Note that your choices will have a (Proxmox) VMID to name-of-template mapping.  You will need to login to the Proxmox UI to get the VMID to name-of-template mappings.

![Screenshot of Proxmox VM Templates Edit screen](./images/proxmox-vm-templates-edit.png)

When you are done, your Custom Field Choices for Proxmox VM templates should look like this.

![Screenshot of Proxmox VM Templates View screen](./images/proxmox-vm-templates-saved.png)


#### proxmox-vm-storage

Create custom field choices for Proxmox VM Storage.  When you click the '+' button, you will be presented with an Edit screen.  Fill the form as shown below.  Note that your choices will represent the name/value of each Proxmox storage volume.  You will need to login to the Proxmox UI to get a list of Proxmox storage volumes.

![Screenshot of Proxmox VM Storage Edit screen](./images/proxmox-vm-storage-edit.png)

When you are done, your Custom Field Choices for Proxmox VM storage should look like this.

![Screenshot of Proxmox VM Storage View screen](./images/proxmox-vm-storage-saved.png)


### NetBox Customization: Custom Fields (for Proxmox VMs)

In the NetBox UI, you will need to create a series of custom fields, as noted below.
1. `proxmox_node` will be used to correlate a Proxmox cluster node with the Proxmox VM that you want to create
2. `proxmox_vm_template` will be used to correlate a Proxmox VM template with the Proxmox VM that you want to create
3. `proxmox_vm_storage` will be used to correlate a Proxmox VM storage volume with the Proxmox VM that you want to create
4. `proxmox_disk_storage_volume` will be used to correlate a Proxmox VM storage volume with each Proxmox VM disk that you want to create
5. `proxmox_public_ssh_key` will be used to assign a public SSH key that you will use to login to a Proxmox VM
6. `proxmox_vmid` will be used to document the Proxmox `vmid` that was created when the Proxmox VM was created

In the NetBox UI, navigate to Customization > Custom Fields


#### proxmox_node

Create a custom field for Proxmox Node.  It will be called `proxmox_node`.  Here is what `proxmox_node` should look like after you've made your changes.

![Screenshot of proxmox_node in NetBox UI](./images/proxmox-node.png)


#### proxmox_vm_template

Create a custom field for Proxmox VM template.  It will be called `proxmox_vm_template`.  Here is what `proxmox_vm_template` should look like after you've made your changes.

![Screenshot of proxmox_vm_template in NetBox UI](./images/proxmox-vm-template.png)

#### proxmox_vm_storage

Create a custom field for Proxmox VM storage.  It will be called `proxmox_vm_storage`.  Here is what `proxmox_vm_storage` should look like after you've made your changes.

![Screenshot of proxmox_vm_storage in NetBox UI](./images/proxmox-vm-storage.png)

#### proxmox_disk_storage_volume

Create a custom field for Proxmox disk storage volume.  It will be called `proxmox_disk_storage_volume`.  Here is what `proxmox_disk_storage_volume` should look like after you've made your changes.

![Screenshot of proxmox_disk_storage_volume in NetBox UI](./images/proxmox-disk-storage-volume.png)

#### proxmox_public_ssh_key

Create a custom field for Proxmox VM public SSH key.  It will be called `proxmox_public_ssh_key`.  Here is what `proxmox_public_ssh_key` should look like after you've made your changes.

![Screenshot of proxmox_public_ssh_key in NetBox UI](./images/proxmox-public-ssh-key.png)

#### proxmox_vmid

Create a custom field for Proxmox VMID.  It will be called `proxmox_vmid`.  Here is what `proxmox_vmid` should look like after you've made your changes.  *Note that `proxmox_vmid` is set automatically during the Proxmox VM provisioning process.  Any VMID that you specified will be discarded.*

![Screenshot of proxmox_vmid in NetBox UI](./images/proxmox-vmid.png)


## Initial Configuration: Proxmox API user + key

While the Proxmox implementation that's part of the Ansible community.general collection allows you to use passwords when doing Proxmox automation, `netbox-proxmox-automation` does not allow this behavior.

It is recommended that you do *not* create an API token for the Proxmox 'root' user.  Instead, create an `api_user` and an API token.  Then assign the required permissions to the `api_user`.  This procedure uses a combination of the Proxmox UI and the command line.  You need to be able to access Proxmox via and UI and SSH and become the 'root' user.  You will need to create an `api_user` in Proxmox, an API token, and set the requisite permissions in Proxmox so that the `api_user` can:

- Connect to Proxmox through the API
- Create, remove, modify Proxmox VMs
- Access (CRUD) Proxmox storage

1. Create `api_user` via the Proxmox UI
- Login to the Proxmox UI (typically as root@pam or as a user with the equivalent permissions)
- Navigate to 'Datacenter' in top left corner of the UI
- Expand the 'Permissions' pane in the center of the UI
- Navigate to Permissions > Users in the center of the UI
  - Click Users
  - Click Add
    - Make sure that the 'Advanced' checkbox is checked
    - Create a user called `api_user` (or whatever you want to call it)
    - The realm should be set to `pve` or 'Proxmox VE Authentication server' (i.e. do not create a user account and use PAM for authentication)
    - Group should be set to `admins`
    - Make sure that 'enabled' is checked
    - Make sure that 'expire' is set to 'never'
    - Do *not* set a password for the user, unless it is required
    - Click OK
2. Create `api_token` via the Proxmox UI
- Navigate to Permissions > API Tokens in the center of the UI
  - Click the Add button
    - Select User from the drop down menu
    - Give the token ID a name
    - Uncheck Privilege Separation
    - Make sure that Expire is set to 'never'
    - Click OK
    - This is the *only* time that your Proxmox API token will be shown in clear text.  Please store it in a safe space, as it will be required when configuring `secrets.yml` in the next section of this document.
3. Login to the Proxmox node via SSH
- Become root: `sudo su -`
- Add `api_user` to the correct role.  For example: `pveum acl modify / -user api_user@pve -role Administrator`
- If 'Administrator' is too broad a role, you can show which roles might be more amenable permissions wise: `pvesh get /access/roles --output-format yaml`.  Then select a more appropriate role for `api_user`, with the understanding that `api_user` needs full access to manage VMs and CRUD access to the underlying storage.

If you want to do everything, as noted above, on the Proxmox (SSH) command line, as root, the procedure would look like this:

```
proxmox-ve-shell# pveum user add api_user@pve --comment "Proxmox API User" --enable 1 --groups admin --expire 0 # create api_user@pve, enabled, non expiring, assigned to admin group

proxmox-ve-shell# pveum user token add api_user@pve api_user_token -privsep 0 # create API token for api_user with the name of api_user_token, and disable privilege separation

proxmox-ve-shell# pveum acl modify / -user api_user@pve -role Administrator # allow api_user@pve to access everything -- given Administrator role rights
```

For the command line above, note that you *will get the Proxmox API token via stdout only once*.  Make sure to copy and store this token in a safe place.  You will need it when we generate the Ansible `secrets.yml` configuration in the next step.

Use `netbox-proxmox-discover-vms.yml` to discover and Proxmox VMs which aren't already in NetBox.  This procedure will also make incremental changes to existing Proxmox VMs in NetBox -- such as adding MAC address to network interfaces.

Usage:

```
shell$ cd /path/to/netbox-proxmox-automation

shell$ source venv/bin/activate

(venv) shell$ ansible-playbook -i inventory netbox-proxmox-discover-vms.yml --ask-vault-pass
```

## Initial Configuration: Flask Application (Python)

*You only need to do this configuration step if you intend to use the example Flask application to handle your Proxmox automation.*

Open a shell on your local system.  *Do not* run these commands as the 'root' user.  The following commands should run on MacOS, Linux, and UNIX-like systems; you will need to run these commands during initial installation or upgrades of `netbox-proxmox-automation`.

```
shell$ cd /path/to/netbox-proxmox-automation/example-netbox-webhook-flask-app

shell$ deactivate # this will fail if there is no configured venv

shell$ rm -rf venv

shell$ python3 -m venv venv

shell$ source venv/bin/activate

(venv) shell$ pip install -r requirements.txt # this will install all of the dependencies
```

To leave `venv`, simply type 'deactivate'.

```
(venv) shell$ deactivate
shell$
```

With each usage of `netbox-proxmox-automation`, make sure that you enter `venv` before running any Ansible commands.  Else this automation will not work.

```
shell$ cd /path/to/netbox-proxmox-automation/example-netbox-webhook-flask-app

shell$ source venv/bin/activate

(venv) shell$  # <--- this is the desired result
```

When in `venv`, you will need to create `app_config.yml`.

```
(venv) shell$ cd /path/to/netbox-proxmox-automation/example-netbox-webhook-flask-app

(venv) shell$ cp -pi app_config.yml-sample app_config.yml
```

Then season `app_config.yml` to taste.  When you are ready to test your Flask application, do this:

```
(venv) shell$ flask run -h 0.0.0.0 -p 8000 --debug 
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:8000
 * Running on http://X.X.X.X:8000
Press CTRL+C to quit
 * Restarting with stat
 * Debugger is active!
 * Debugger PIN: XXX-XXX-XXX
```

The above `flask` command will start the Flask application on port 8000 (or whatever you specify with the `-p` argument) and will bind on the IP address (or IP addresses) that were specified with the `-h` argument.  In this case, we used 0.0.0.0 with the `-h` argument, so the Flask application will listen on all interfaces.  The `--debug` argument indicates that we will run a single-threaded web service and that we will show output to stdout.  *You will want to use `gunicorn.py` or some other WSGI server to run the Flask application in production.*

## Initial Configuration: AWX or Tower/AAP

*You only need to do this configuration step if you intend to use AWX or Tower/AAP to handle your Proxmox automation.*

Certainly, you do not need to do Ansible automation by using webhooks and event rules (triggering) in NetBox.  [This weblog](https://netboxlabs.com/blog/getting-started-with-network-automation-netbox-ansible/) shows you how you can use [Ansible](https://www.ansible.com/) with NetBox, as network source of truth, to induce changes in your environment -- by using a pull method for your automation from any client on your network.  In this example, you'll be able to run `ansible-playbook`, alongside a dynamic inventory (NetBox) to induce automation, or in this case automating changes to Proxmox VMs.

However, many other NetBox users want to use NetBox as NSoT (network source of truth) to facilitate their Proxmox VM automation.  Changes to Proxmox VMs in NetBox will result in automation being kicked off, in this case via [AWX](https://github.com/ansible/awx), or perhaps for a Red Hat commercial customer, through [Tower/AAP](https://www.redhat.com/en/solutions/it-automation?sc_cid=7015Y000003sm3kQAA&gad_source=1&gclid=CjwKCAiAl4a6BhBqEiwAqvrqugh1f-1RfeP-NQxOKYhSbwJqUPVqGqR1A0ScrGMdNhLUbdTayU-EOhoCg00QAvD_BwE&gclsrc=aw.ds).  By using webhooks and event rules in NetBox, AWX or Tower/AAP are more than capable of inducing Proxmox automation.  In fact, using AWX or Tower/AAP is the preferred method for large environments -- where Proxmox VM deployment is a part of an underlying CI/CD.

For those who are unfamiliar, AWX is the upstream (community, i.e. free) version of AAP.  Functionally, AWX works the same way as Tower/AAP, but without the commercial support.  AWX is an excellent alternative as you work through NetBox/Proxmox automation, but there can be a heavy lift when it comes to configuring AWX for the first time.  This section talks through the steps you'll need to be able to run AWX and to begin your Proxmox VM automation journey with NetBox.

### Installing AWX with docker-compose

AWX (or Tower/AAP) are typically installed in an environment where Kuberenetes (k8s) is available.  However, should you have Docker/docker-compose running on your local system, you should be able to install AWX [this way](https://github.com/ansible/awx/blob/devel/tools/docker-compose/README.md).

Once you have installed AWX (or Tower/AAP) in your environment, and are able to login, as an 'admin' user through the UI, you can start configuring AWX (or Tower/AAP) to facilitate your Proxmox VM automation.  *Note that you can add whatever user(s)/group(s) that you want to AWX, but make sure that whatever user(s)/group(s) you add to AWX have the appropriate permissions to manage the following.*

#### Create Github (or your Git of choice) Credential in AWX

1. Login to the AWX UI
2. Navigate to Resources > Credentials
3. Create a new credential, as specified below, of type 'Source Control'.  Call it whatever you want, then make sure to copy and paste your SSH private key and (if required) SSH passphrase here.

![AWX image git credential image](./images/awx-scm-credential-new.png)

#### Select Inventory in AWX

Navigate to Resources > Inventories.  'Demo Inventory' should be sufficient for `netbox-promox-automation`.

![AWX default inventory image](./images/awx-default-inventory.png)

#### Create Execution Environment in AWX

Typically, when `ansible` or `ansible-playbook` is/are executed from the command line, this is done via a Python3 `venv`.  However, with AWX, there is no such capability to interact with a command line to leverage `venv` to do a `pip install` of Python module dependencies.

As a result, you will need to use an [Execution Environment](https://ansible.readthedocs.io/projects/awx/en/latest/userguide/execution_environments.html) in AWX.  Your Execution Environment is a container image that will include all of the (Python) module dependencies that you'll need to facilitate Proxmox automation, and this container image will live in your container registry of choice.  

*You (probably) only need to create an Exection Environment once for `netbox-proxmox-automation` with AWX.*

In the end, your Execution Environment should look like this in AWX.

![AWX Execution Environment image](./images/awx-execution-environment.png)

To create your Execution Environment, you need to do the following.

1. On your AWX host, create a directory structure like this.

![AWX Execution Environment directory tree image](./images/awx-execution-environment-tree.png)

2. On your AWX host, create and change to the directory where your Execution Environment will live: `mkdir -p /home/ubuntu/awx/execution-environments/ubuntu-env1; cd /home/ubuntu/awx/execution-environments/ubuntu-env1`

3. On your AWX host, setup a Python 3 `venv`: `cd /home/ubuntu/awx/execution-environments/ubuntu-env1 ; python3 -m venv venv ; source venv/bin/activate`

4. On your AWX host, create a file called `execution-environment.yml`.  It should look like the following.

![AWX Execution Environment config file image](./images/awx-execution-environment-yml.png)

Note that `execution-environment.yml` contains two requirement lines.  One is for Ansible Galaxy, and the other is for Python 3.

5. Create `dependencies/requirements.txt` and `dependencies/requirements.yml`.

`requirements.txt` will include the Python 3 module dependencies.

```
(venv) shell$ mkdir dependencies

(venv) shell$ cat dependencies/requirements.txt
ansible
ansible-core
ansible-runner
bcrypt
certifi
cffi
charset-normalizer
cryptography
dnspython
docutils
idna
Jinja2
lockfile
MarkupSafe
packaging
paramiko
pexpect
prompt-toolkit
proxmoxer
ptyprocess
pycparser
PyNaCl
pynetbox
python-daemon
PyYAML
questionary
requests
resolvelib
six
urllib3
wcwidth
```

`requirements.yml` will define the Ansible collections to include.  In this case we want to include the awx collection, the community.general collection (where the Proxmox Ansible modules live), and the netbox.netbox collection, which will interface with the NetBox API.

```
(venv) shell$ mkdir dependencies

(venv) shell$ cat dependencies/requirements.yml
---
collections:
  - awx.awx
  - community.general
  - netbox.netbox
```

6. Finally, build the new Execution Environment image, and push to your container registry, which in this case lives on localhost (local to AWX)

![AWX Build Execution Environment commands image](./images/awx-ansible-build-ee.png)

Once you have built your Execution Environment, which is based on the default AWX Execution Environment, you can proceed with Proxmox automation in AWX.

#### Add NetBox and Proxmox Credential Types to AWX

Navigate to Administration > Credential Types in AWX, and create a credential type called 'NetBox Proxmox Creds'.

![AWX Netbox Proxmox Creds image](./images/awx-netbox-proxmox-creds.png)

Input configuration should include the following:

```
fields:
  - id: proxmox_api_host
    type: string
    label: Proxmox API Host
  - id: proxmox_api_user
    type: string
    label: Proxmox API User
  - id: proxmox_api_user_token
    type: string
    label: Proxmox API Token ID
  - id: proxmox_node
    type: string
    label: Proxmox Node
  - id: proxmox_api_token_secret
    type: string
    label: Proxmox API Token
    secret: true
  - id: netbox_api_proto
    type: string
    label: NetBox HTTP Protocol
  - id: netbox_api_host
    type: string
    label: NetBox API host
  - id: netbox_api_port
    type: string
    label: NetBox API port
  - id: netbox_api_token
    type: string
    label: NetBox API token
    secret: true
required:
  - proxmox_api_host
  - proxmox_api_user
  - proxmox_api_user_token
  - proxmox_node
  - proxmox_api_token_secret
  - netbox_api_host
  - netbox_api_port
  - netbox_api_proto
  - netbox_api_token
```

Injector configuration should include the following (yes, `extra_vars` is required, as is `netbox_env_info` and `proxmox_env_info`):

```
extra_vars:
  netbox_env_info:
    api_host: '{{ netbox_api_host }}'
    api_port: '{{ netbox_api_port }}'
    api_proto: '{{ netbox_api_proto }}'
    api_token: '{{ netbox_api_token }}'
  proxmox_env_info:
    node: '{{ proxmox_node }}'
    api_host: '{{ proxmox_api_host }}'
    api_user: '{{ proxmox_api_user }}'
    api_token_id: '{{ proxmox_api_user_token }}'
    api_token_secret: '{{ proxmox_api_token_secret }}'
```

#### Add NetBox/Proxmox Credentials to AWX

Navigate to Resources > Credentials in AWX, and create a credential called 'NetBox Proxmox Credentials'.

![NetBox Proxmox Credentials Image](./images/awx-netbox-proxmox-credentials.png)

#### Add Project to AWX

Navigate to Resources > Projects in AWX, and create a new Project called 'netbox-proxmox-ee-test1'.

![NetBox Proxmox Create Project image](./images/awx-create-project.png)

Click the 'Sync' button in the AWX UI to ensure that git synchronization is successful.  If this step is *not* successful, then *do not proceed* -- as you troubleshoot.  Otherwise, proceed.

#### Add (project) Templates to AWX

In AWX, a (project) template provides a web accessible means of triggering automation, i.e. via a webhook.  Each (project) template represents an Ansible playbook -- each Ansible playbook represents a file that was synchronized from git when you created the project in AWX -- where the playbook will perform Proxmox automation.

For example, when you have defined a Proxmox VM in NetBox (alongside its default resources), you can use `awx-clone-vm-and-set-resources.yml` to automate the cloning of a VM and setting its resources in Proxmox.

![NetBox Proxmox clone vm and set resources image](./images/awx-proxmox-clone-vm-and-set-resources.png)

When you create *any* template in AWX for Proxmox automation, you will need to set 'Prompt on launch' to true (tick checkbox) for both 'Credentials' and 'Variables', as shown below.

![NetBox Proxmox clone vm and set resources edit image](./images/awx-netbox-proxmox-template-clone-resources-edit.png)

`netbox-proxmox-ansible` provides a series of Ansible playbooks that you can use to create fully-functioning Proxmox VMs based on their desired configuration states in NetBox.  You will need to create a (project) template for each playbook in AWX.

`netbox-proxmox-automation` implements the following Ansible playbooks.

| Ansible playbook | Purpose |
| --- | --- |
| awx-proxmox-add-vm-disk.yml | Adds a disk to Proxmox VM (*not* scsi0, which is the OS disk) |
| awx-proxmox-clone-vm-and-set-resources.yml | Clones a Proxmox VM template to a Proxmox VM and sets resources like vcpu and memory |
| awx-proxmox-remove-vm-disk.yml | Removes a non-OS disk (i.e. not scsi0) from a Proxmox VM |
| awx-proxmox-remove-vm.yml | Removes a Proxmox VM |
| awx-proxmox-resize-vm-disk.yml | Resizes a Proxmox VM disk |
| awx-proxmox-set-ipconfig0.yml | Sets ipconfig0 for Proxmox VM and adds ssh key|
| awx-proxmox-start-vm.yml | Starts Proxmox VM |
| awx-proxmox-stop-vm.yml | Stops Proxmox VM |


## Initial Configuration: NetBox Event Rules and Webhooks

There are two key components to automating Proxmox VM management in NetBox.
1. webhooks
2. event rules

A webhook in NetBox will consume the payload of data from an event rule.  An event rule announces changes to an object type inside of NetBox (in this case, a Virtual Machine and its related object types) -- then sends the payload of data around those changes to a webhook.  The webhook will handle the Proxmox automation(s) as you've defined it/them.

For the sake of automation, every event rule that you create in NetBox requires either a Webhook or a Script.

Regardless of whether you are using a Flask (or other) application for Proxmox automation, or you are using AWX or Tower/AAP, this automation should trigger anytime that a Proxmox VM is changed in NetBox such that:
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


### AWX or Tower/AAP

As noted earlier, AWX or Tower/AAP will perform Proxmox automation through separate (project) templates.  This section walks you through how (NetBox) webhooks and (NetBox) event rules are handled by AWX.

#### AWX or Tower/AAP Webhook

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


#### AWX or Tower/AAP Event Rules

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


# Developers
- Nate Patwardhan &lt;npatwardhan@netboxlabs.com&gt;

# Known Issues / Roadmap

## Known Issues
- *Only* supports SCSI disk types (this is possibly fine as Proxmox predomininantly provisions disks as SCSI)
- Does not currently support Proxmox VM creation to a Proxmox cluster, but is only node-based
- Needs better reconciliation on the NetBox end when Proxmox->NetBox discovery is used

## Roadmap -- Delivery
- DNS update support (requires NetBox `netbox-dns` plugin)
- Maybe evolve into to a NetBox plugin for Proxmox
