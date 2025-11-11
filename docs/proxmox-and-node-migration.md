# NetBox and Proxmox Node Migration

It is well known that Proxmox can support both clustering and single nodes.  When using a Proxmox cluster, one can select a respective virtual machine (VM) and migrate the VM to any available Proxmox nodes.

As NetBox requires that virtual machines are assigned to a virtual cluster, this gives you the ability to migrate virtual machines between Proxmox nodes.  `netbox-proxmox-automation` 2025.11.01 implements an *experimental* feature that allows you to migrate Proxmox VMs between Proxmox nodes, simply when you make changes to the intended state of a Proxmox VM in NetBox.  This is done through event-driven automation in `netbox-proxmox-automation`, such that changing the assigned `proxmox_node` custom field in NetBox will trigger an event -- and this event will migrate the VM from the existing Proxmox node to a specified Proxmox node.  Whether you are using the included Flask application or are using AWX/Tower/AAP, both automation strategies should work for this purpose.

*NOTE: LXC migration is not supported.  This is a technical blocker based on Proxmox currently.*

*NOTE 2: This only works for NetBox (Proxmox) VMs that are in a state of 'active' or 'offline'*

To do this, you must do three things before attempting to induce Proxmox VM migration by way of NetBox.

1. you have a running Proxmox cluster or clusters
2. you have created a `netbox-proxmox-automation` configuration for each of your Proxmox clusters
3. you have created all custom fields with the `netbox_setup_objects_and_custom_fields.py` script
4. you have defined your automation strategy and run the `netbox_setup_webhook_and_event_rules.py` script
5. your NetBox is up to date with VM and customization information

Once you have done the above, all that it takes to induce this automation is to select a Proxmox VM in NetBox, *edit* that object, toggle the name of the `proxmox_node` custom field, then click the Save button.  This will kick off the (node) migration in Proxmox.
