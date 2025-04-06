## Configure Flask Application (Python)

*You only need to do this configuration step if you intend to use the Flask application to handle your Proxmox automation.*

Open a shell on your local system.  *Do not* run these commands as the 'root' user.  The following commands should run on MacOS, Linux, and UNIX-like systems; you will need to run these commands during initial installation or upgrades of `netbox-proxmox-automation`.

```
shell$ cd /path/to/netbox-proxmox-automation/netbox-event-driven-automation-flask-app

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
shell$ cd /path/to/netbox-proxmox-automation/netbox-event-driven-automation-flask-app

shell$ source venv/bin/activate

(venv) shell$  # <--- this is the desired result
```

When in `venv`, you will need to create `app_config.yml`.

```
(venv) shell$ cd /path/to/netbox-proxmox-automation/netbox-event-driven-automation-flask-app

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

The above `flask` command will start the Flask application on port 8000 (or whatever you specify with the `-p` argument) and will bind on the IP address (or IP addresses) that were specified with the `-h` argument.  In this case, we used 0.0.0.0 with the `-h` argument, so the Flask application will listen on all interfaces.  The `--debug` argument indicates that we will run a single-threaded web service and that we will show output to stdout.

*You will want to use `gunicorn.py` or some other WSGI server to run the Flask application in production.*  This is documented [here](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/), but here's an annotated version of how to use gunicorn to run netbox-event-driven-automation-flask-app.

1. Make sure that you are in the netbox-event-driven-automation-flask-app directory: `cd /path/to/netbox-proxmox-automation/netbox-event-driven-automation-flask-app`

2. Leave `venv`: `deactivate`

3. Remove existing `venv`: `rm -rf venv`

4. Create new `venv`: `python3 -m venv venv`

5. Enter new `venv`: `source venv/bin/activate`

6. `pip` install requirements: `pip install -r requirements.txt`

7. Run the application: `gunicorn -w 4 -b 0.0.0.0:9000 'app:app'`, or season this command to taste for how you want to bind, including your preferred port number for listening.

You can then start using `netbox-event-driven-automation-flask-app` from NetBox!

Granted, there are myriad ways to do this, including using NGINX to proxy connections to this Flask application, but that's an exercise that's left up to the reader for the time being.




