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
1. NetBox webhooks and event rules will use AWX (Tower, AAP) to induce Proxmox automation
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

`netbox-proxmox-automation` is *not* a NetBox plugin, and this is by design.

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

In the NetBox UI, you will need to create two custom field choices.
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

In the NetBox UI, you will need to create a series of custom fields.
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

## Initial Configuration: AWX (Tower, AAP)

*You only need to do this configuration step if you intend to use AWX (Tower, AAP) to handle your Proxmox automation.*

Put steps here

## Initial Configuration: Flask Application (Python)

*You only need to do this configuration step if you intend to use the example Flask application to handle your Proxmox automation.*

Open a shell on your local system.  *Do not* run these commands as the 'root' user.  The following commands should run on MacOS, Linux, and UNIX-like systems; you will need to run these commands during initial installation or upgrades of `netbox-proxmox-automation`.

```
shell$ cd /path/to/netbox-proxmox-automation

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
shell$ cd /path/to/netbox-proxmox-automation

shell$ source venv/bin/activate

(venv) shell$  # <--- this is the desired result
```

When in `venv`, you will need to create `app_config.yml`.

```
(venv) shell$ cd example-netbox-webhook-flask-app

(venv) shell$ cp -pi app_config.yml-sample app_config.yml
```

Then season `app_config.yml` to taste.  When you are ready to test your Flask application, do this:

```
(venv) shell$ flask run --debug
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
 * Restarting with stat
 * Debugger is active!
 * Debugger PIN: 134-610-085
```

## Initial Configuration: NetBox Event Rules and Webhooks

Put steps here

# Developers
- Nate Patwardhan &lt;npatwardhan@netboxlabs.com&gt;

# Known Issues / Roadmap

## Known Issues
- *Only* supports SCSI disk types (this is possibly fine as Proxmox predomininantly provisions disks as SCSI)
- Needs better reconciliation on the NetBox end when Proxmox->NetBox discovery is used

## Roadmap -- Delivery TBD
- DNS update support (requires NetBox `netbox-dns` plugin)
- Maybe evolve into to a NetBox plugin for Proxmox
