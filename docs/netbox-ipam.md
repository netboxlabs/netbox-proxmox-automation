# NetBox IPAM

Given the heirarchical nature of NetBox, you will need to create the following objects before using `netbox-proxmox-automation` automation.  You should refer to the [NetBox planning guide](https://netboxlabs.com/docs/netbox/en/stable/getting-started/planning/) to address these dependencies before proceeding with `netbox-proxmox-automation`.

Using NetBox's IPAM is a *requirement* of `netbox-proxmox-automation`.  This is because `netbox-proxmox-automation` is going to either assign a defined IP address to a specified inteface (or interfaces) on a Proxmox VM, or it's going to request an available IP address from NetBox's IPAM -- and assign the requested IP address to an interface (or interfaces) on a Proxmox VM.

Ahead of using this automation, make sure to create the following IPAM-related objects in NetBox:

- IPAM > RIRs
- IPAM > Aggregates (relate each aggregate to RIR)
- IPAM > Prefixes (use containers and set Active state for each active previx)
