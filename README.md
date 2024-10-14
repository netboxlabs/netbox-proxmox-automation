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

`netbox-proxmox-ansible` is a client-based implementation where you define virtual machine configurations (in YAML) then create your *desired* virtual machine states in NetBox.  Ansible then automates your *desired* virtual machine states from NetBox to Proxmox.  The same can also be done in reverse: Where Proxmox holds your initial virtual machine states -- that you want to "discover" in Proxmox then document/merge in/into NetBox.

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

# Installation

`netbox-proxmox-ansible` is intended to make your life as simple as possible.  Once you have a working Proxmox node (or cluster), have provisioned a Proxmox API token with the permissions noted above, a NetBox instance, a NetBox API token, and have (optionally) installed the `netbox-dns` plugin and a name server (which you have permissions to manage), the entire process of managing Proxmox virtual machines via NetBox involves three simple requirements.

  1. You have created a configuration file which holds your environment and virtual machine configurations: `vms.yml`
  2. You have created an encrypted configuration file which holds your API tokens and related information: `secrets.yml`.
  3. You are running a current version of Ansible (2.17.4 was used for developing `netbox-proxmox-ansible`), preferably with the ability to have elevated permissions (i.e. root) should you want to automate DNS changes -- and can install any dependencies required by `netbox-proxmox-ansible`.

## Inital Setup (Python)

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

## Initial Setup (Netbox collection for Ansible)

```
shell$ source venv/bin/activate

(venv) shell$ ansible-galaxy collection install netbox.netbox
```

## Initial Setup (Proxmox for Ansible via community.general collection)

```
shell$ source venv/bin/activate

(venv) shell$ ansible-galaxy collection install community.general
```

## Initial Setup (Ansible vault and secrets)

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

## Initial Setup (Proxmox API user + key)

here

## Initial Setup (NetBox API user + key)

here

There are two key parts to this automation:
  1. `vm-manager.py`
  2. `vm-cluster-manager.py`

`vm-manager.py`:
  1. creates (or deletes) the VM (or VMs) in NetBox
  2. creates network interfaces and allocates IP addresses in NetBox (IPAM) -- either statically or dynamically
  3. creates and configures (or delete(s)) the VM(s) in Proxmox
  4. `vm-manager.py` will also update the DNS for each VM, for both creation and deletion, if configured
  
  The data flow looks like this, regardless of whether you are creating or deleting a VM in Proxmox.

  `Client -> NetBox API call (VMs, interfaces, and IPAM) -> Proxmox API (VMs and storage) -> NetBox API call (netbox-dns for DNS data) -> Ansible runner -> (bind9) DNS changes`

`vm-cluster-manager.py` interactively creates a Proxmox VM cluster and cluster nodes in NetBox.  You need at least one Proxmox vm cluster and one Proxmox vm node before you can run `vm-manager.py`.

# Initial Installation

## `netbox-proxmox-ansible` Dependencies

  From your terminal, run: `. ./setup.sh`

This should install everything you need and drop you into a Python `venv`.  You *must* run all future commands in a Python venv.

If you want to do this manually, do this:

  ```
  terminal% deactivate

  terminal% rm -rf venv

  terminal% python3 -m venv venv

  terminal% source venv/bin/activate

  terminal% pip install -r requirements.txt
  ```

## Initial Configuration

1. Make sure that you have a working NetBox API token
2. Make sure that you have a working Proxmox API token; this token should have sufficient privileges to query storage on Proxmox and to operate on VMs (start, stop, delete, etc)
3. You will see a series of configuration stubs under the `conf.d` directory.  Copy each configuration (e.g. `cd conf.d ; cp -pi netbox.yml-sample netbox.yml`) so that you've written configurations for:
    - ansible
    - dns
    - netbox
    - proxmox
    - ssh
    - ssl
    - vm_info
4. If you want to do DNS updates, you'll need to install the [netbox-dns plugin](https://github.com/peteeckel/netbox-plugin-dns) in your NetBox instance
5. Make sure that you have administrator access to your bind9 instance (if DNS has been enabled in your configuration)
6. Run `vm-cluster-manager.py` if you need assistance in creating Proxmox VM cluster(s) and Proxmox VM node(s)

## VM Configuration
1. Write a new `vm-info.yml`; `cd conf.d ; cp vm-info.yml-sample vm-info.yml` and season `vm_info.yml` to taste
2. `vm-info.yml` is required by `vm-manager.py`

### `vm-info.yml` Required Fields

In the 'global' section of `vm_info.yml`, the following fields are *required*:
  - default_tenant
  - dns_forward_zone (if using DNS)
  - dns_reverse_zone (if using DNS)
  - default_proxmox_node_name
  - default_vm_template_name

For each VM in the `vms` section of `vm_info.yml`, the following fields are *required*:
  - name
  - vcpus (integer)
  - memory (in MB, integer)
  - storage (in GB, integer)
  - proxmox_storage (usually local-lvm should be chosen, but consult your Proxmox storage configuration for options)

### `vm_info.yml` Optional Fields

For each VM in the `vms` section of `vm_info.yml`, the following fields are *optional*:
  - proxmox_node_name (if not set, VM will be deployed on `default_proxmox_node_name`)
  - vm_template_name (if not set, VM will be created from `default_vm_template_name`)

# How to Use netbox-proxmox-ansible

## `vm-manager.py` Usage

`vm_info.yml` needs to exist before using `vm-manager.py`!

Use the `--verbose` option for any `vm-manager.py` argument to show, *gasp*, verbose output.

```
prompt% source venv/bin/activate

(venv) prompt% ./vm-manager.py --help
usage: vm-manager.py [-h] {createvm,deletevm} ...

Proxmox VM Command-line Based Manager

positional arguments:
  {createvm,deletevm}  sub-command help
    createvm           createvm help action
    deletevm           deletevm help action

options:
  -h, --help           show this help message and exit

End Options

(venv) prompt% ./vm-manager.py createvm --help
usage: vm-manager.py createvm [-h] [--hostname HOSTNAME] [-v]

options:
  -h, --help           show this help message and exit
  --hostname HOSTNAME  name of vm to create
  -v, --verbose        show verbose output

(venv) prompt% ./vm-manager.py deletevm --help
usage: vm-manager.py deletevm [-h] [--hostname HOSTNAME] [-v]

options:
  -h, --help           show this help message and exit
  --hostname HOSTNAME  name of vm to create
  -v, --verbose        show verbose output
```

### Creating VM(s)

To create *all* VMs listed in `vm_info.yml`:

  ```
  prompt% source venv/bin/activate

  (venv) prompt% ./vm-manager.py createvm
  ```

If successful, VM(s) will be created in NetBox, in Proxmox, and if DNS updates have been enabled -- on your primary bind9 server.

### Creating VM by name

To create a VM, by name, as listed in `vm_info.yml`:

  ```
  prompt% source venv/bin/activate

  (venv) prompt% ./vm-manager.py createvm --hostname name-of-matching-vm-from-vms-yml-config
  ```

If successful, VM will be created in NetBox, in Proxmox, and if DNS updates have been enabled -- on your primary bind9 server.

### Deleting VM(s)

To delete *all* VMs listed in `vm_info.yml`:

  ```
  prompt% source venv/bin/activate

  (venv) prompt% ./vm-manager.py deletevm
  ```

If successful, VM(s) will be delete in NetBox, in Proxmox, and if DNS updates have been enabled -- from your primary bind9 server.

### Deleting VM by name

To delete a VM, by name, as listed in `vm_info.yml`:

  ```
  prompt% source venv/bin/activate

  (venv) prompt% ./vm-manager.py deletevm --hostname name-of-matching-vm-from-vms-yml-config
  ```

If successful, VM will be deleted in NetBox, in Proxmox, and if DNS updates have been enabled -- from your primary bind9 server.

## `vm-cluster-manager.py` Usage

`vm-cluster-manager.py` does not take any arguments.  Instead it is a configurator that uses the Python `questionary` module.  It will ask you a series of questions about your environment and will create any objects in NetBox that don't already exist.  *NOTE: You need to be able to run Ansible with elevated privileges (e.g. root) to be able to run `vm-cluster-manager.py`.*

*Only* run `vm-cluster-manager.py` if:
  - Your Proxmox VM node is running and available on your network
  - You haven't already configured virtual machine cluster types in NetBox
  - You haven't already configured at least one Proxmox VM cluster in NetBox
  - You haven't added Proxmox VM nodes as Devices in NetBox
  - You might be missing Sites, Locations, Tenants, etc in NetBox

When you run `vm-cluster-manager.py` it will:
  - Inspect the hardware of the Proxmox VM node that you want to add
  - Add Sites, Locations, Tenants, etc that are related to your Proxmox VM node
  - Add Cluster Types (Proxmox)
  - Add Manufacturer and Platform info (if it doesn't already exist)
  - Add hardware information (make, model, serial number) for your Proxmox VM node
  - Add Device for your Proxmox VM node
  - Add active/inactive network device information for your Proxmox VM node

Ultimately, running `vm-cluster-manager.py`, if necessary, will tie your VM(s) to the right Proxmox VM cluster when you run `vm-manager.py`.  Without this information in NetBox, `vm-manager.py` is not bound to function correctly.

# Working with Ubuntu/Debian Cloud Images

This process is [well documented](https://pve.proxmox.com/wiki/Cloud-Init_Support) by the Proxmox team.  In the end it comes down to:
- downloading a cloud image
- following the documented process in the previous link
- converting your image to a Proxmox VM template
- ensuring that your Proxmox VM template has an associated SSH (public) key.

The automated VM cloning and configuration process will handle IP allocation/configuration and host naming.  The default user for an Ubuntu cloud image is always 'ubuntu'.

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
