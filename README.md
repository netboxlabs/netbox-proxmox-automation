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

# What's New in 1.2.0
  - Adds LXC support
  - Adds the ability to define 'vmid' for both VM and LXC, rather than taking a default value from Proxmox
  - Adds "discovery" of Proxmox VM and LXC disks and auto-creation of VM disk objects in NetBox
  - Adds rudimentary Proxmox VM and LXC discovery through convenience script
  - Adds AWX initial setup through convenience script (uses awxkit)
  - Convenience script changes to accommodate LXC requirements
  - Can dynamically build webhooks and event rules from current AWX state through convenience script
  - Adds customization changes for LXC-specific requirements

# Developers
- Nate Patwardhan &lt;npatwardhan@netboxlabs.com&gt;

# Known Issues / Roadmap

## Known Issues
- *Only* supports SCSI disk types (this is possibly fine as Proxmox predomininantly provisions disks as SCSI)
- Does not currently support Proxmox VM creation to a Proxmox cluster, but is only node-based

## Roadmap -- Delivery
- Integration with NetBox Discovery/Assurance
- DNS update support (requires NetBox `netbox-dns` plugin)
- Maybe evolve into to a NetBox plugin for Proxmox
