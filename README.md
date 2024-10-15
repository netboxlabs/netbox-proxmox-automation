# Project Summary

[NetBox](https://github.com/netbox-community/netbox) is a widely used tool for documenting/modeling networks (network devices, virtual machines, etc), and also provides a great IPAM solution.  [Proxmox](https://www.proxmox.com/en/) is a freely available virtualization technology that allows you to deploy virtual machines at scale, and perhaps in a clustered configuration.  NetBox has approximately 15,000 users in its open source community.  Proxmox has approximately 900,000 users in its open source community.

When you think of the challenges of a widely used network documentation solution and a widely used virtualization technology, this implementation represents the marriage between virtual machine documentation (NetBox) and the automation of virtual machine configurations (Proxmox).

`netbox-proxmox-ansible` uses [Ansible](https://www.ansible.com/) to automate management of your Proxmox VMs: With NetBox as your [*Network Source of Truth (NSoT)*](https://netboxlabs.com/blog/what-is-a-network-source-of-truth/), as NetBox was designed.  In other words, this automation will collect the *desired* (documented) state of (Proxmox) virtual machines in Netbox -- and deploy identical virtual machine configurations to Proxmox.

This automation handles both the creation and removal of Proxmox virtual machines.

*This implementation also supports discovering virtual machines in Proxmox, should you want to document and/or merge your (Proxmox) operational state into NetBox.*

When you use NetBox to create virtual machines in Proxmox, their *desired* state will be generated, including:
- hostname
- initial vm state (Staged)
- network interface(s)
- IP(s) for each network interface(s)
- primary network interface for each virtual machine
- state of each VM disk (disk name and size)
- update netbox-dns plugin for each virtual machine (if enabled)

When you use NetBox to remove virtual machines from Proxmox, their *desired* state will be generated, including:
- initial vm state (Decommissioning)
- identify Proxmox virtual machines that need to be removed
- desired vm state ahead of removal (Offline)
- update netbox-dns plugin for each virtual machine (if enabled)
- remove non-existent virtual machine objects in Netbox

Creating and deleting virtual machines in NetBox will both update virtual machine state in Proxmox *and* update your DNS, if your DNS implementation is supported by this automation.  *You will need the [netbox-dns plugin](https://github.com/peteeckel/netbox-plugin-dns) if you want to manage your DNS records in NetBox.*

When you discover virtual machines in Proxmox, this will create/merge virtual machine changes in NetBox.

## Usage

Basic usage of `netbox-proxmox-ansible`, to provision Proxmox virtual machines to their desired state(s), is as follows:

```
shell$ source venv/bin/activate

(venv) shell$ ansible-playbook -i inventory proxmox-vm-manager.yml --ask-vault-pass
```

Should you want to update the DNS as well as provision Proxmox virtual machines to their desired state(s), use the following command:

```
shell$ source venv/bin/activate

(venv) shell$ ansible-playbook -i inventory proxmox-vm-manager.yml --ask-vault-pass --ask-pass --ask-become-pass
```

The above will prompt you for a SSH password, the password that you would use for `sudo` commands, and finally your Ansible vault passphrase.

## What this implementation *is*

`netbox-proxmox-ansible` is a client-based implementation where you define virtual machine configurations (in YAML) then create your *desired* virtual machine states in NetBox.  Ansible then synchronizes your *desired* virtual machine states from NetBox to Proxmox by way of automation with Ansible.  The same can also be done in reverse: Where Proxmox holds your initial virtual machine states -- that you want to "discover" in Proxmox then document/merge in/into NetBox.

You *should* be able to run `netbox-proxmox-ansible` from *any* Windows, MacOS, or Linux/UNIX-like system -- so long as you have both Ansible and Python (version 3) installed.  (*Python 2 is long dead, so it is not supported here.*)

`netbox-proxmox-ansible` uses cloud-init images to induce virtual machine changes on Proxmox based on the *desired* state in NetBox (and vice versa).  Almost always these cloud-init images will be Debian or Debian-derived images (e.g. Debian or Ubuntu), RHEL-derived images (e.g. Rocky Linux), or maybe even Windows-based cloud-init images.  *(Windows cloud-init images are currently un-tested.)*  While you should be able to use a cloud-init image of choice with this automation, and due to the uncertain future of RHEL-derived Linuxes, *only* Ubuntu/Debian cloud images (cloud-init) are supported for the time being.  We welcome any reports around other cloud-init images, and will merge in this functionality as we are able.

Proxmox is highly conducive to using cloud-init images -- when cloud-init images are converted to templates.  You can define items like ssh keys and network configurations in Proxmox by way of using cloud-init images, and cloud-init will cascade these settings into your Proxmox virtual machines: *Dynamically*.  Further, Proxmox has a comprehensive API -- you can define virtual machine resources, plus disk configurations and more -- where you can leverage automation, in this case Ansible, to lay down your desired virtual machine states in Proxmox with little effort.

NetBox models virtual machines in an intuitive way.  You can define roles for virtual machines, such as for Proxmox, and from there you can define both virtual machine state (Active, Offline, etc) and other resources like vcpus, memory, network configuration, disks, and more (perhaps, also, through customizations in NetBox).

In this context, `netbox-proxmox-ansible` takes virtual machine configurations from NetBox then applies their (running) states to Proxmox.  Of course, it works in the opposite way as well.

This automation is based on the premise(s) that:
  1. You are using Python (version 3) on your client
  2. You are using a Python `venv`
  3. You have a running Proxmox instance or cluster
  4. You have a running NetBox instance
  5. You have converted a cloud-init image to a Proxmox virtual machine template
  6. Your Promox virtual machine template(s) has/have qemu-guest-agent installed, and that qemu-guest-agent has been enabled via cloud-init
  7. You have access to the NetBox and Proxmox APIs (via API tokens, respectively)
  8. Your NetBox API token and its underlying privileges can create, modify, and delete objects in NetBox
  9. Your Proxmox API token and its underlying privileges can both manage VMs and storage (query, create, delete, etc)
  10. If you want to make DNS changes:
  - You have installed the netbox-dns plugin in your NetBox instance (OPTIONAL)
  - You are running bind9 as your DNS server and have "admin" rights to make DNS changes (OPTIONAL)
  - You are able to run Ansible with elevated privileges (i.e. root, OPTIONAL, for DNS changes)

## What this implementation *is not*

`netbox-proxmox-ansible` is *not* a NetBox plugin; nor is it a script or a webhook (at this point in time).  And this is by design.

[ProxBox](https://github.com/netdevopsbr/netbox-proxbox) is a neat implementation of pulling information from Proxmox into NetBox.  ProxBox has its place, most certainly, but what it does is *not* the aim of `netbox-proxmox-ansible`.

Further, `netbox-proxmox-ansible` does *not* deploy a future state for any Proxmox virtual machine.  For example, let's say you deploy a Proxmox virtual machine called 'vm1' and it's intended to be a(n) LDAP server.  The scope of `netbox-proxmox-ansible` is to ensure that each virtual machine that you document/model and deploy to Proxmox has a consistent baseline configuration, from which you can take future automation steps.  NetBox will document/model your *desired* Proxmox virtual machine state, but additional automation states like package installations and configurations are left up to further automation that you might choose to do once your vitual machine is running in Proxmox.  As `netbox-proxmox-ansible` is free for you to use and/or modify, you are welcome to introduce subsequent automations to `netbox-proxmox-ansible` in your own environment.

# Installation

`netbox-proxmox-ansible` is intended to make your life as simple as possible.  Once you have a working Proxmox node (or cluster), have provisioned a Proxmox API token with the permissions noted above, a NetBox instance, a NetBox API token, and have (optionally) installed the `netbox-dns` plugin and a name server (which you have permissions to manage), the entire process of managing Proxmox virtual machines via NetBox involves three simple requirements.

  1. You have created a configuration file which holds your environment and virtual machine configurations: `vms.yml`
  2. You have created an encrypted configuration file which holds your API tokens and related information: `secrets.yml`.
  3. You are running a current version of Ansible (2.17.4 was used for developing `netbox-proxmox-ansible`), preferably with the ability to have elevated permissions (i.e. root) should you want to automate DNS changes -- and can install any dependencies required by `netbox-proxmox-ansible`.

While these various initial configuration notes might seem like a heavy lift, your initial configuration of `netbox-proxmox-ansible` should take less than an hour.  Plus, you will likely need to run these configuration steps only once.

## Initial Configuration: Python

Open a shell on your local system.  *Do not* run these commands as the 'root' user.  The following commands should run on MacOS, Linux, and UNIX-like systems; you will need to run these commands during initial installation or upgrades of `netbox-proxmox-ansible`.

```
shell$ cd /path/to/netbox-proxmox-ansible

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

With each usage of `netbox-proxmox-ansible`, make sure that you enter `venv` before running any Ansible commands.  Else this automation will not work.

```
shell$ cd /path/to/netbox-proxmox-ansible

shell$ source venv/bin/activate

(venv) shell$  # <--- this is the desired result
```

## Initial Configuration: Netbox collection for Ansible

```
shell$ source venv/bin/activate

(venv) shell$ ansible-galaxy collection install netbox.netbox
```

## Initial Configuration: Proxmox for Ansible via community.general collection

```
shell$ source venv/bin/activate

(venv) shell$ ansible-galaxy collection install community.general
```

## Initial Configuration: Ansible inventory file

You will need to create an inventory file to be able to use `netbox-proxmox-ansible`.

If you do not need DNS support, do this.

```
shell$ cd /path/to/netbox-proxmox-ansible

shell$ source venv/bin/activate

(venv) shell$ cat inventory
[proxmox]
name-or-ip-of-proxmox-node1
... etc ...
name-or-ip-of-proxmox-nodeN
```

If you need DNS support, do this:

```
shell$ cd /path/to/netbox-proxmox-ansible

shell$ source venv/bin/activate

(venv) shell$ cat inventory
[proxmox]
name-or-ip-of-proxmox-node1
... etc ...
name-or-ip-of-proxmox-nodeN
[dns]
name-or-ip-of-dns-server1
... etc ...
name-or-ip-of-dns-serverN
```

## Initial Configuration: Creating Proxmox virtual machine templates from (cloud-init) images

`netbox-proxmox-ansible` *only* supports cloud-init images.  The dynamic nature of Proxmox virtual machine automation requires this implementation to be able to set things, during the Proxmox virtual machine provisioning process, like network configuration, hostnames, and more.  While it's *possible* that `netbox-proxmox-ansible` *might* support your existing Proxmox virtual machine templates, it's *highly* recommended that you follow the procedure below -- for the best results.

As a cloud-init image is basically "blank", meaning that there is not broad network or SSH key configuration, this allows us to have total flexibility in the way that this automation takes a *desired* Proxmox virtual machine state from NetBox and generates anticipated changes to virtual machines -- in Proxmox.

This process is [well documented](https://pve.proxmox.com/wiki/Cloud-Init_Support) by the Proxmox team.  In the end it comes down to:
- logging into your Proxmox node(s) and running these commands as the 'root' user, or as a user who has adequate permissions to modify Proxmox virtual machines and the underlying storage
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

Then let the cloud-init images download.  Once the downloads have completed, you might want to take backups of the original cloud-init images -- as we will proceed with modifying these cloud-init images slightly before converting them to Proxmox virtual machine templates.  Taking backups of the original cloud-init images is helpful should you ever need to revert any customization you did before converting the cloud-init images into Proxmox virtual machine templates.  Run this, again, as 'root' on the proxmox-node of your choice.

```
proxmox-ve-node# cd /root/cloud-images/ubuntu

proxmox-ve-node# for img in `ls -1 *img`; do cp -pi $img $img.$(date +%Y-%m-%d); done
```

Now let's start preparing our cloud-init images so that we can convert them to Proxmox virtual machine templates.  We'll use the Ubuntu ('jammy') cloud image to illustrate this process.  You can use whatever cloud image you want to implement this process.

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

Run `virt-sysprep` to start resetting the cloud-init image -- ahead of cloning it to a Proxmox virtual machine later on.

```
proxmox-ve-node# virt-sysprep -a jammy-server-cloudimg-amd64.img
[   0.0] Examining the guest ...
[   3.7] Performing "abrt-data" ...
[   3.7] Performing "backup-files" ...
[   4.2] Performing "bash-history" ...
[   4.2] Performing "blkid-tab" ...
[   4.3] Performing "crash-data" ...
[   4.3] Performing "cron-spool" ...
[   4.3] Performing "dhcp-client-state" ...
[   4.3] Performing "dhcp-server-state" ...
[   4.3] Performing "dovecot-data" ...
[   4.3] Performing "ipa-client" ...
[   4.3] Performing "kerberos-hostkeytab" ...
[   4.3] Performing "logfiles" ...
[   4.5] Performing "machine-id" ...
[   4.5] Performing "mail-spool" ...
[   4.5] Performing "net-hostname" ...
[   4.5] Performing "net-hwaddr" ...
[   4.5] Performing "net-nmconn" ...
[   4.5] Performing "pacct-log" ...
[   4.5] Performing "package-manager-cache" ...
[   4.6] Performing "pam-data" ...
[   4.6] Performing "passwd-backups" ...
[   4.6] Performing "puppet-data-log" ...
[   4.6] Performing "rh-subscription-manager" ...
[   4.6] Performing "rhn-systemid" ...
[   4.6] Performing "rpm-db" ...
[   4.6] Performing "samba-db-log" ...
[   4.6] Performing "script" ...
[   4.6] Performing "smolt-uuid" ...
[   4.7] Performing "ssh-hostkeys" ...
[   4.7] Performing "ssh-userdir" ...
[   4.7] Performing "sssd-db-log" ...
[   4.7] Performing "tmp-files" ...
[   4.7] Performing "udev-persistent-net" ...
[   4.7] Performing "utmp" ...
[   4.7] Performing "yum-uuid" ...
[   4.7] Performing "customize" ...
[   4.7] Setting a random seed
virt-sysprep: warning: random seed could not be set for this type of guest
[   4.8] Setting the machine ID in /etc/machine-id
[   4.8] Performing "lvm-uuids" ...
```

Notice how `virt-sysprep` set `/etc/machine-id`.  We don't want that -- as the same machine-id will carry over to all Proxmox virtual machines when they are cloned.  Therefore, we need to truncate `/etc/machine-id` so that it will be automatically created as each Proxmox virtual machine is provisioned.

```
proxmox-ve-node# virt-customize -a jammy-server-cloudimg-amd64.img --truncate /etc/machine-id  
[   0.0] Examining the guest ...
[   3.8] Setting a random seed
virt-customize: warning: random seed could not be set for this type of 
guest
[   3.8] Truncating: /etc/machine-id
[   3.8] Finishing off
```

Now we are ready to create a Proxmox virtual machine from the Ubuntu ('jammy') cloud-init image -- that we have modified.  This breaks down into two (high-level) steps:
1. Create a Proxmox virtual machine, with a unique id, with various configuration options
2. Convert the Proxmox virtual machine into a Proxmox virtual machine template

First, create the Proxmox virtual machine, with a unique id, and configure its attributes.  We tend to use unique ids >= 9000 for Proxmox virtual machine templates, but you do as you will.  *Note that you cannot use duplicate virtual machine ids in Proxmox.*  You will need to run the `qm` command, as the 'root' user, on your Proxmox node, to configure the following Proxmox virtual machine attributes:

- create the Proxmox virtual machine
- import the cloud-init image to the Proxmox virtual machine
- set the SCSI (disk) hardware attributes for the Proxmox virtual machine root disk
- map an IDE disk to the cloud-init image
- define a boot disk for the Proxmox virtual machine
- define a serial port such that the Proxmox virtual machine is accessible through the Proxmox console
- set the QEMU agent to be enabled such that you can access various information from `qemu-guest-agent` when the Proxmox virtual machine is running

Regarding where you store the Ubuntu ('jammy') cloud-init image, you likely have options between faster and slower disks on your Proxmox nodes.  It's recommended that you store the Ubuntu ('jammy') cloud-init image on faster disks; this will lead to better virtual machine cloning performance.  Let's see which disks are available to us in Proxmox; in this case an SSD comprises our root volume, which is called 'local-lvm'.  There is a slower spinning drive configuration that's called 'pve-hdd'.

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

Here's the procedure to create a Proxmox virtual machine from the Ubuntu ('jammy') cloud-init image.

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

Second, convert the Proxmox virtual machine into a template.  You can then use this Proxmox virtual machine template in your `netbox-proxmox-ansible` automation.

Now convert the Proxmox virtual machine to a template.  *Note that this cannot be undone!*

```
proxmox-ve-node# qm template 9000
  Renamed "vm-9000-disk-0" to "base-9000-disk-0" in volume group "pve"
  Logical volume pve/base-9000-disk-0 changed.
```

You should now be able to use your Proxmox virtual machine template, with a virtual machine id (vmid) of 9000 (or whatever you choose) in your `netbox-proxmox-ansible` automation.

## Initial Configuration: NetBox objects + dependencies

Given the heirarchical nature of NetBox, you will need to create the following objects before using `netbox-proxmox-ansible` automation.  You should refer to the [NetBox planning guide](https://netboxlabs.com/docs/netbox/en/stable/getting-started/planning/) to address these dependencies before proceeding with `netbox-proxmox-ansible`.

Using NetBox's IPAM is a *requirement* of `netbox-proxmox-ansible`.  This is because `netbox-proxmox-ansible` is going to either assign a defined IP address to a specified inteface (or interfaces) on a Proxmox VM, or it's going to request an available IP address from NetBox's IPAM -- and assign the requested IP address to an interface (or interfaces) on a Proxmox VM.

Ahead of using this automation, make sure to create the following IPAM-related objects in NetBox:
- IPAM > RIRs
- IPAM > Aggregates (relate each aggregate to RIR)
- IPAM > Prefixes (use containers and set Active state for each active previx)

## Initial Configuration: NetBox API user + key

It is recommended that you do *not* create an API token for the NetBox 'admin' user.  Instead, create a new user in NetBox; then create a new permission for that API user -- that has sufficient read/write/modify permissions to modify the following object types in NetBox, at a minimum:

  - Devices
  - Interfaces (devices and virtual machines)
  - Virtual Machines (groups, clusters, virtual machines)

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

While it is possible to use passwords with the Netbox Ansible collection, `netbox-proxmox-ansible` does not allow this behavior.  Instead a NetBox API token is required.

In the NetBox UI:

1. Navigate to Admin > API Tokens
2. Add a new token, associating it with `api_user`, with the following characteristics: Write enabled (you can select other characteristics if you wish)

Once you've created a NetBox API token, store it some place safe in the meantime; most NetBox installations will obscure the API token once it's been created.

## Initial Configuration: Proxmox API user + key

While the Proxmox implementation that's part of the Ansible community.general collection allows you to use passwords when doing Proxmox automation, `netbox-proxmox-ansible` does not allow this behavior.

It is recommended that you do *not* create an API token for the Proxmox 'root' user.  Instead, create an `api_user` and an API token.  Then assign the required permissions to the `api_user`.  This procedure uses a combination of the Proxmox UI and the command line.  You need to be able to access Proxmox via and UI and SSH and become the 'root' user.  You will need to create an `api_user` in Proxmox, an API token, and set the requisite permissions in Proxmox so that the `api_user` can:

- Connect to Proxmox through the API
- Create, remove, modify Proxmox virtual machines
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
- If 'Administrator' is too broad a role, you can show which roles might be more amenable permissions wise: `pvesh get /access/roles --output-format yaml`.  Then select a more appropriate role for `api_user`, with the understanding that `api_user` needs full access to manage virtual machines and CRUD access to the underlying storage.

If you want to do everything, as noted above, on the Proxmox (SSH) command line, as root, the procedure would look like this:

```
proxmox-ve-shell# pveum user add api_user@pve --comment "Proxmox API User" --enable 1 --groups admin --expire 0 # create api_user@pve, enabled, non expiring, assigned to admin group

proxmox-ve-shell# pveum user token add api_user@pve api_user_token -privsep 0 # create API token for api_user with the name of api_user_token, and disable privilege separation

proxmox-ve-shell# pveum acl modify / -user api_user@pve -role Administrator # allow api_user@pve to access everything -- given Administrator role rights
```

For the command line above, note that you *will get the Proxmox API token via stdout only once*.  Make sure to copy and store this token in a safe place.  You will need it when we generate the Ansible `secrets.yml` configuration in the next step.

## Initial Configuration: Ansible vault and secrets

`netbox-proxmox-ansible` requires that you store secrets in a file called `secrets.yml`.  While `secrets.yml` is excluded in .gitignore, it is best practice to encrypt any file where secrets live.  For this purpose we will use [Ansible vault](https://docs.ansible.com/ansible/latest/vault_guide/index.html).

`secrets.yml` is used to store your Proxmox and NetBox authentication information (nodes, hosts, users, API tokens, etc) and must be in the following format:

```
---
proxmox:
  node: name-of-proxmox-node # (frequently proxmox-ve by default)
  api_host: hostname-or-ip-of-proxmox-api-host
  api_user: api_user@pve # season to taste
  api_token_id: id-of-api-user-token
  api_token_secret: some-api-token-secret-here
netbox:
  api_proto: http # or https, season to taste
  api_host: hostname-or-ip-of-netbox-host
  api_port: 80 # or season to taste
  api_token: some-api-token-secret-here
```

1. Copy `secrets.yml-sample` to `secrets.yml`: `cp -pi secrets.yml-sample secrets.yml`.
2. Generate a clear text `secrets.yml` with the format noted above.
3. Encrypt `secrets.yml` with the `ansible-vault` command: `ansible-vault encrypt secrets.yml`.  This will prompt you for a (new) passphrase and a passphrase confirmation.
4. Verify that `secrets.yml` has been encrypted: `head -1 secrets.yml`.  This should provide output like: `$ANSIBLE_VAULT;1.1;AES256`.
5. To view (a decrypted) `secrets.yml`, run this command: `ansible-vault view secrets.yml`.  This will prompt you for your passphrase.

# Authors
- Nate Patwardhan <npatwardhan@netboxlabs.com>

# Known Issues / Roadmap

## Known Issues
- Has not been tested with NetBox 4.0 or newer (it *should* work)
- `vm-cluster-manager.py` should be more intuitive and complete
- *Only* supports SCSI disk types

## Roadmap -- Delivery TBD
- Support other DNS implementations than bind9: Gandi, Squarespace, etc
- NetBox > 4.0 (transparent) support
- Better configuration process
