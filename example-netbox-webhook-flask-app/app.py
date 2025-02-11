import logging
import json
import yaml

from datetime import datetime

# adapted from: https://majornetwork.net/2019/10/webhook-listener-for-netbox/

from helpers.netbox_proxmox import NetBoxProxmoxHelper

from flask import Flask, Response, request, jsonify
from flask_restx import Api, Resource, fields

VERSION = '1.1.0'

app_config_file = 'app_config.yml'

with open(app_config_file) as yaml_cfg:
    try:
        app_config = yaml.safe_load(yaml_cfg)
    except yaml.YAMLError as exc:
        print(exc)

if not 'netbox_webhook_name' in app_config:
    raise ValueError(f"'netbox_webhook_name' missing in {app_config_file}")

app = Flask(__name__)
api = Api(app, version="1.0.0", title="NetBox-Proxmox Webhook Listener",
        description="NetBox-Proxmox Webhook Listener")
ns = api.namespace(app_config['netbox_webhook_name'])

# set debug (enabled/disabled)
DEBUG = False

if app.debug:
    DEBUG = True


APP_NAME = "netbox-proxmox-webhook-listener"

logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s")
file_logging = logging.FileHandler("{}.log".format(APP_NAME))
file_logging.setFormatter(formatter)
logger.addHandler(file_logging)

webhook_request = api.model("Webhook request from NetBox", {
    'username': fields.String,
    'data': fields.Raw(description="Object data from NetBox"),
    'event': fields.String,
    'timestamp': fields.String,
    'model': fields.String,
    'request_id': fields.String,
})

# For session logging, c/o sol1
session = {
  'name': "example-netbox-webhook-flask-app",
  'version': VERSION,
  'version_lastrun': VERSION,
  'server_start': "",
  'status': {
    'requests': 0,
    'last_called': ""
  },
}


@ns.route("/status/", methods=['GET'])
class WebhookListener(Resource):
    @ns.expect(webhook_request)

    def get(self):
        _session = session.copy()
        _session['version_lastrun'] = VERSION
        _session['status']['requests'] += 1
        _session['status']['last_called'] = datetime.now()
        logger.info(f"{request.full_path}, {request.remote_addr}, Status request with data {request.get_data()}")
        return jsonify(_session)


# For handling event rules
@ns.route("/")
class WebhookListener(Resource):
    @ns.expect(webhook_request)
    def post(self):
        try:
            webhook_json_data = request.json
        except:
            webhook_json_data = {}

        logger.info("{}".format(webhook_json_data))

        if not webhook_json_data or "model" not in webhook_json_data or "event" not in webhook_json_data:
            return {"result":"invalid input"}, 400

        if DEBUG:
            print(f"INCOMING DATA FOR WEBHOOK {webhook_json_data['event']} --> {webhook_json_data['model']}\n", webhook_json_data)

        """
        LXC CREATE:
        INCOMING DATA FOR WEBHOOK created --> virtualmachine
        {'event': 'created', 'timestamp': '2025-02-01T15:57:37.884945+00:00', 'model': 'virtualmachine',
        'username': 'admin', 'request_id': 'da4892d1-e8ea-4b7b-9245-40e5e92f0fc6',
        'data': {'id': 433, 'url': '/api/virtualization/virtual-machines/433/', 'display_url': '/virtualization/virtual-machines/433/',
        'display': 'foo2', 'name': 'foo2', 'status': {'value': 'active', 'label': 'Active'},
        'site': None,
        'cluster': {'id': 1, 'url': '/api/virtualization/clusters/1/', 'display': 'proxmox-ve', 'name': 'proxmox-ve', 'description': ''},
        'device': None, 'serial': '', 'role': None, 'tenant': None, 'platform': None, 'primary_ip': None, 'primary_ip4': None, 'primary_ip6': None,
        'vcpus': 1.0, 'memory': 2048, 'disk': 20000, 'description': '', 'comments': '', 'config_template': None, 'local_context_data': None, 'tags': [],
        'custom_fields': {'proxmox_node': 'proxmox-ve', 'proxmox_vm_type': 'lxc', 'proxmox_vmid': None, 
        'proxmox_lxc_templates': 'local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst',
        'proxmox_public_ssh_key': None, 'proxmox_vm_storage': 'local-lvm', 'proxmox_vm_templates': '9000'},
        'created': '2025-02-01T15:57:37.836976Z', 'last_updated': '2025-02-01T15:57:37.837007Z', 'interface_count': 0, 'virtual_disk_count': 0},
        'snapshots': {'prechange': None, 'postchange': {'created': '2025-02-01T15:57:37.836Z', 'last_updated': '2025-02-01T15:57:37.837Z', 'description': '', 'comments': '', 'local_context_data': None, 'config_template': None, 'site': None, 'cluster': 1, 'device': None, 'tenant': None, 'platform': None, 'name': 'foo2', '_name': 'foo00000002', 'status': 'active', 'role': None, 'primary_ip4': None, 'primary_ip6': None, 'vcpus': '1', 'memory': 2048, 'disk': 20000, 'serial': '', 'interface_count': 0, 'virtual_disk_count': 0, 'custom_fields': {'proxmox_node': 'proxmox-ve', 'proxmox_vm_type': 'lxc', 'proxmox_vmid': None, 'proxmox_lxc_templates': 'local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst', 'proxmox_public_ssh_key': None, 'proxmox_vm_storage': 'local-lvm', 'proxmox_vm_templates': '9000'}, 'tags': []}}}
 
        LXC REMOVE:
        INCOMING DATA FOR WEBHOOK deleted --> virtualmachine
        {'event': 'deleted', 'timestamp': '2025-02-01T16:00:29.618552+00:00', 'model': 'virtualmachine', 'username': 'admin', 'request_id': '7d5fca97-2919-4f87-b86b-091d74f10018', 'data': {'id': 433, 'url': '/api/virtualization/virtual-machines/433/', 'display_url': '/virtualization/virtual-machines/433/', 'display': 'foo2', 'name': 'foo2', 'status': {'value': 'active', 'label': 'Active'}, 'site': None, 'cluster': {'id': 1, 'url': '/api/virtualization/clusters/1/', 'display': 'proxmox-ve', 'name': 'proxmox-ve', 'description': ''}, 'device': None, 'serial': '', 'role': None, 'tenant': None, 'platform': None, 'primary_ip': None, 'primary_ip4': None, 'primary_ip6': None, 'vcpus': 1.0, 'memory': 2048, 'disk': 20000, 'description': '', 'comments': '', 'config_template': None, 'local_context_data': None, 'tags': [], 'custom_fields': {'proxmox_node': 'proxmox-ve', 'proxmox_vm_type': 'lxc', 'proxmox_vmid': None, 'proxmox_lxc_templates': 'local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst', 'proxmox_public_ssh_key': None, 'proxmox_vm_storage': 'local-lvm', 'proxmox_vm_templates': '9000'}, 'created': '2025-02-01T15:57:37.836976Z', 'last_updated': '2025-02-01T15:57:37.837007Z', 'interface_count': 0, 'virtual_disk_count': 0}, 'snapshots': {'prechange': {'created': '2025-02-01T15:57:37.836Z', 'description': '', 'comments': '', 'local_context_data': None, 'config_template': None, 'site': None, 'cluster': 1, 'device': None, 'tenant': None, 'platform': None, 'name': 'foo2', '_name': 'foo00000002', 'status': 'active', 'role': None, 'primary_ip4': None, 'primary_ip6': None, 'vcpus': '1.00', 'memory': 2048, 'disk': 20000, 'serial': '', 'interface_count': 0, 'virtual_disk_count': 0, 'custom_fields': {'proxmox_node': 'proxmox-ve', 'proxmox_vmid': None, 'proxmox_vm_type': 'lxc', 'proxmox_vm_storage': 'local-lvm', 'proxmox_vm_templates': '9000', 'proxmox_lxc_templates': 'local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst', 'proxmox_public_ssh_key': None}, 'tags': []}, 'postchange': None}}
        """

        if not 'proxmox_node' in webhook_json_data['data']['custom_fields']:
            return jsonify({'missing Proxmox node': 'missing Proxmox node'}), 500
        
        proxmox_node = webhook_json_data['data']['custom_fields']['proxmox_node']

        tc = NetBoxProxmoxHelper(app_config, proxmox_node)

        if webhook_json_data['model'] == 'virtualmachine':
            if webhook_json_data['data']['custom_fields']['proxmox_vm_type'] == 'vm':
                if webhook_json_data['data']['status']['value'] == 'staged':
                    if webhook_json_data['event'] == 'created':
                        results = tc.proxmox_clone_vm(webhook_json_data)
                    elif webhook_json_data['event'] == 'updated':
                        results = tc.proxmox_update_vm_resources(webhook_json_data)

                        if webhook_json_data['data']['primary_ip'] and webhook_json_data['data']['primary_ip']['address']:
                            results = tc.proxmox_set_ipconfig0(webhook_json_data)

                        if 'proxmox_public_ssh_key' in webhook_json_data['data']['custom_fields'] and webhook_json_data['data']['custom_fields']['proxmox_public_ssh_key']:
                            results = tc.proxmox_set_ssh_public_key(webhook_json_data) 
                elif webhook_json_data['event'] == 'updated' and webhook_json_data['data']['status']['value'] == 'offline':
                    results = tc.proxmox_stop_vm(webhook_json_data)
                elif webhook_json_data['event'] == 'updated' and webhook_json_data['data']['status']['value'] == 'active':
                    results = tc.proxmox_start_vm(webhook_json_data)
                elif webhook_json_data['event'] == 'deleted':
                    results = tc.proxmox_delete_vm(webhook_json_data)

            # disk stuff
            if webhook_json_data['model'] == 'virtualdisk':
                if webhook_json_data['event'] == 'created':
                    results = tc.proxmox_add_disk(webhook_json_data)
                elif webhook_json_data['event'] == 'updated':
                    results = tc.proxmox_resize_disk(webhook_json_data)
                elif webhook_json_data['event'] == 'deleted':
                    results = tc.proxmox_delete_disk(webhook_json_data)
            elif webhook_json_data['data']['custom_fields']['proxmox_vm_type'] == 'lxc':
                print(f"AFFFFF LXC {webhook_json_data['data']}", webhook_json_data['event'])

                if webhook_json_data['event'] == 'created':
                    results = tc.proxmox_create_lxc(webhook_json_data)
                elif webhook_json_data['event'] == 'updated':
                    results = tc.proxmox_resize_disk(webhook_json_data)
                elif webhook_json_data['event'] == 'deleted':
                    results = tc.proxmox_delete_lxc(webhook_json_data)
            else:
                results = (500, {f"result": f"Unknown VM type {webhook_json_data['data']['custom_fields']['proxmox_vm_type']}"})

            response = Response(
                json.dumps(results[1]),
                status = results[0],
                mimetype = 'application/json'
            )

            #print(f"RESPONSE {response} | {response.status_code} | {response.response} | {response.json} | {response.status} | {response.get_data()}")
            return response.status_code, {'result': response.json['result']}


if __name__ == "__main__":
    app.run(host="0.0.0.0")
