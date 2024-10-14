# Project Summary

[NetBox](https://github.com/netbox-community/netbox) is a widely used tool for documenting networks.  [Proxmox](https://www.proxmox.com/en/) is a freely available virtualization technology that allows you to deploy virtual machines at scale, and perhaps in a clustered configuration.  NetBox has approximately 15,000 users of its open source project.  Proxmox has approximately 900,000 users of its open source project.

When you think of the challenges of a widely used network documentation solution and a widely used virtualization implementation, this implementation represents the marriage between virtual machine documentation (NetBox) and the automation of virtual machine configurations (Proxmox).

`netbox-proxmox-ansible` uses [Ansible](https://www.ansible.com/) to implement a series of tools to manage your Proxmox VMs: With NetBox as your [*Network Source of Truth (NSoT)*](https://netboxlabs.com/blog/what-is-a-network-source-of-truth/), as NetBox was designed.  In other words, this automation will collect the *desired* state of (Proxmox) virtual machines in Netbox -- and deploy identical virtual machine configurations to Proxmox.

This automation handles both the creation and removal of Proxmox virtual machines.

*This implementation also supports discovering virtual machines in Proxmox, should you want to document your (Proxmox) operational state in NetBox.*

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

Creating and deleting virtual machines, in NetBox, will both update virtual machine state in Proxmox *and* update your DNS, if your DNS implementation is supported by this automation.  *You will need the [netbox-dns plugin](https://github.com/peteeckel/netbox-plugin-dns) if you want to manage DNS records in NetBox.*

When you discover virtual machines in Proxmox, this will create/reconcile virtual machine changes in NetBox.

## What this implementation *is*

`netbox-proxmox-ansible` is a client-based implementation where you define virtual machine configurations (in YAML) then create your *desired* virtual machine states in NetBox.  Ansible then automates your *desired* virtual machine states in Proxmox.  The same can also be done in reverse: Where Proxmox holds your initial virtual machine states -- that you then want to document in NetBox.

You should be able to run `netbox-proxmox-ansible` from *any* Windows, MacOS, or Linux/UNIX-like system -- so long as you have both Ansible and Python (version 3) installed.  (*Python 2 is long dead, so it is not supported here.*)

`netbox-proxmox-ansible` uses cloud-init images to induce virtual machine changes on Proxmox based on the *desired* state in NetBox (and vice versa).

## What this implementation *is not*

`netbox-proxmox-ansible` is *not* a NetBox plugin; nor is it a script.  And this is by design.

[ProxBox](https://github.com/netdevopsbr/netbox-proxbox) is a neat implementation of pulling information from Proxmox into NetBox.  It has its place, most certainly, but what it does is *not* the aim of `netbox-proxmox-ansible`.

While you should be able to use your Linux distribution of choice with this automation, due to the uncertain future of RHEL-derived Linuxes, *only* Ubuntu/Debian cloud images (cloud-init) are supported for the time being.

This automation is based on the premise(s) that:
  1. You have a running Proxmox instance or cluster
  2. You have a running NetBox instance
  3. You are running bind9 and have access to make DNS changes
  4. You are using Python 3
  5. You are using a((n) Ubuntu) cloud image that has been configured (qemu-guest-agent has been enabled) and converted into a Proxmox VM template
  6. You have access to the Proxmox API (via API token)
  7. You have access to the NetBox API (via API token)
  8. You are able to run Ansible with elevated privileges (i.e. root).
    - This is required by `vm-manager.py` to be able to make DNS updates.
    - This is required by `vm-cluster-manager.py` to get hardware information for your Proxmox VM node.

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

This should install everything you need and drop you into a Python 3 `venv`.  You *must* run all future commands in a Python 3 venv.

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

`vm-cluster-manager.py` does not take any arguments.  Instead it is a configurator that uses the Python 3 `questionary` module.  It will ask you a series of questions about your environment and will create any objects in NetBox that don't already exist.  *NOTE: You need to be able to run Ansible with elevated privileges (e.g. root) to be able to run `vm-cluster-manager.py`.*

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

## Roadmap -- Delivery TBD
- Support other DNS implementations than bind9: Gandi, Squarespace, etc
- NetBox > 4.0 (transparent) support
- Better configuration process
