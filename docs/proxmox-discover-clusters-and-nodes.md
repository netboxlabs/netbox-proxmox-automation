# Discover Proxmox Clusters and Nodes

Starting with `netbox-proxmox-automation` 2025.11.01, you are able to discover Proxmox cluster and nodes information by way of a convenience script, `netbox-discover-proxmox-cluster-and-nodes.py`.  `netbox-discover-proxmox-cluster-and-nodes.py` is located under the `setup` directory; you should run this script *before* attempting to "discover" VMs and/or LXCs and importing them into NetBox.

*Note that you must follow the steps in [this document](./netbox-customization.md) before running this convenience script!*

In NetBox, *all* virtual machines, or in the parlance of Proxmox (virtual machines and/or LXC), are required to be associated with a virtualization cluster in NetBox.  Therefore, whether you have a single-node Proxmox installation or have implemented a Proxmox cluster, *all* of your Proxmox installations will be reflected as clusters in NetBox.  Given that, `netbox-discover-proxmox-cluster-and-nodes.py` collects the following information about your Proxmox cluster and nodes.

  - Make and manufacturer of underlying hardware that's running Proxmox
  - CPU and memory information for each node that's running Proxmox
  - Serial number
  - Network interfaces (name, type, MAC address, enabled)
  - IP addresses
  - Proxmox version and release level, i.e. Platform

*You will need the following commands to be installed on your Proxmox node(s) for this to work, and you'll need root access (direct or via sudo) for this to work*:

  - dmidecode
  - 'ethtool' command
  - 'ip' command
  - lshw

After collecting this information, `netbox-discover-proxmox-cluster-and-nodes.py` turns around and creates the related objects in NetBox.

  - Manufacturer
  - Device Roles
  - Platforms
  - Device Types
  - Devices
  - IP Addresses (for Devices with interface mappings)
  - Virtual Machine Cluster (with Device mappings)

Once the Proxmox node(s) has/have been added to NetBox, you can start discovering VMs and LXCs in Proxmox.

`netbox-proxmox-automation` has a sample config file under the `conf.d` directory that's called `netbox_setup_objects.yml-sample`.  Make a copy of `netbox_setup_objects.yml-sample` to the location of your choice.  Then run `./setup/netbox-discover-proxmox-cluster-and-nodes.py` as follows.

```
shell$ cd /path/to/netbox-proxmox-automation/setup

shell$ deactivate

shell$ python3 -m venv venv

shell$ source venv/bin/activate

shell$ pip install -r requirements.txt

shell$ ./netbox-discover-proxmox-cluster-and-nodes.py --config ../path/to/your-config.yml
```

*Note that you will need one config file for each Proxmox cluster, or in the case of multiple, single Proxmox nodes, you will need a config file for each of those.*
