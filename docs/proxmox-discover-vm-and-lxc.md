# Discover Proxmox VMs and LXCs and Adding Objects to Netbox

Starting with `netbox-proxmox-automation` 1.2.0, you are able to "discover" Proxmox VMs and LXCs and automatically create the related Virtual Machine objects in NetBox.  This is done by using a Proxmox API token to query the virtualization inventory, and based on VM category (Virtual Machines and LXC Containers), collecting everything that we know about virtualization objects in Proxmox -- then creating the related VM objects in NetBox.

*Note that you must follow the steps in [this document](./netbox-customization.md) before running this convenience script!*

`./setup/netbox-discovery-tool.py` was created so that you can document everything that you have in Proxmox in NetBox, but with the understanding that your future pattern will be to induce changes in Proxmox from the "intent" (i.e. desired state) that you've set in NetBox.
`./setup/netbox-discovery-tool.py` was not created to implement a perpetual "discovery" process against the inventory that lives in Proxmox.  It's meant to be a starting point in your automation journey.

`netbox-proxmox-automation` has a sample config file under the `conf.d` directory that's called `netbox_setup_objects.yml-sample`.  Make a copy of `netbox_setup_objects.yml-sample` to the location of your choice.  Then run `./setup/netbox-discovery-tool.py` as follows.

```
shell$ cd /path/to/netbox-proxmox-automation/setup

shell$ deactivate

shell$ python3 -m venv venv

shell$ source venv/bin/activate

shell$ pip install -r requirements.txt
```

## To Discover Proxmox VMs

Follow the steps above, then: `./netbox-discovery-tool.py vm --config /path/to/your-config.yml`

## To Discover Proxmox LXCs

Follow the steps above, then: `./netbox-discovery-tool.py lxc --config /path/to/your-config.yml`
