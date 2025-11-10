import logging
import json
import yaml

from datetime import datetime

# adapted from: https://majornetwork.net/2019/10/webhook-listener-for-netbox/

from helpers.netbox_proxmox import NetBoxProxmoxHelper, NetBoxProxmoxHelperVM, NetBoxProxmoxHelperLXC, NetBoxProxmoxHelperMigrate

from flask import Flask, Response, request, jsonify
from flask_restx import Api, Resource, fields

VERSION = '2025.11.01'

app_config_file = 'app_config.yml'

with open(app_config_file) as yaml_cfg:
    try:
        app_config = yaml.safe_load(yaml_cfg)
    except yaml.YAMLError as exc:
        print(exc)

if not 'netbox_webhook_name' in app_config:
    raise ValueError(f"'netbox_webhook_name' missing in {app_config_file}")

app = Flask(__name__)
api = Api(app, version=VERSION, title="NetBox-Proxmox Webhook Listener",
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
  'name': "netbox-webhook-flask-app",
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
        sanitized_full_path = request.full_path.replace('\r\n', '').replace('\n', '')
        sanitized_remote_addr = request.remote_addr.replace('\r\n', '').replace('\n', '') if request.remote_addr else 'Unknown'
        sanitized_data = request.get_data(as_text=True).replace('\r\n', '').replace('\n', '') if request.get_data() else ''
        logger.info(f"{sanitized_full_path}, {sanitized_remote_addr}, Status request with data {sanitized_data}")
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

        sanitized_data = json.dumps(webhook_json_data).replace('\n', '').replace('\r', '')
        logger.info("User-provided data: {}".format(sanitized_data))

        if not webhook_json_data or "model" not in webhook_json_data or "event" not in webhook_json_data:
            return {"result":"invalid input"}, 400

        results = (500, {'result': 'Default error message (obviously something has gone wrong)'})

        if DEBUG:
            print(f"INCOMING DATA FOR WEBHOOK {webhook_json_data['event']} --> {webhook_json_data['model']}\n", json.dumps(webhook_json_data, indent=4))

        if webhook_json_data['model'] == 'virtualmachine':
            if not 'proxmox_node' in webhook_json_data['data']['custom_fields']:
                results = 500, {'result': 'Missing proxmox_node in custom_fields'}
            
            proxmox_node = webhook_json_data['data']['custom_fields']['proxmox_node']

            if webhook_json_data['data']['custom_fields']['proxmox_vm_type'] == 'vm':
                tc = NetBoxProxmoxHelperVM(app_config, proxmox_node, DEBUG)

                if webhook_json_data['data']['status']['value'] == 'staged':
                    if webhook_json_data['event'] == 'created':
                        results = tc.proxmox_clone_vm(webhook_json_data)
                    elif webhook_json_data['event'] == 'updated':
                        results = tc.proxmox_update_vm_vcpus_and_memory(webhook_json_data)

                        if webhook_json_data['data']['primary_ip'] and webhook_json_data['data']['primary_ip']['address']:
                            results = tc.proxmox_set_ipconfig0(webhook_json_data)

                        if 'proxmox_public_ssh_key' in webhook_json_data['data']['custom_fields'] and webhook_json_data['data']['custom_fields']['proxmox_public_ssh_key']:
                            results = tc.proxmox_set_ssh_public_key(webhook_json_data)
                    elif webhook_json_data['event'] == 'deleted':
                        results = tc.proxmox_delete_vm(webhook_json_data)
                elif webhook_json_data['event'] == 'updated':
                    if webhook_json_data['data']['status']['value'] == 'offline':

                        # if source node != target node -> migrate

                        results = tc.proxmox_stop_vm(webhook_json_data)
                    elif webhook_json_data['data']['status']['value'] == 'active':

                        # if source node != target node -> migrate

                        results = tc.proxmox_start_vm(webhook_json_data)
                    else:
                        results = (500, {'result': f"Unknown value {webhook_json_data['data']['status']['value']}"})
                elif webhook_json_data['event'] == 'deleted':
                    results = tc.proxmox_delete_vm(webhook_json_data)
            elif webhook_json_data['data']['custom_fields']['proxmox_vm_type'] == 'lxc':
                tc = NetBoxProxmoxHelperLXC(app_config, proxmox_node, DEBUG)

                if webhook_json_data['data']['status']['value'] == 'staged':
                    if DEBUG:
                        print(f"LXC STAGED INPUT {webhook_json_data['data']}", webhook_json_data['event'])

                    if webhook_json_data['event'] == 'created':
                        results = tc.proxmox_create_lxc(webhook_json_data)
                    elif webhook_json_data['event'] == 'updated':
                        if webhook_json_data['data']['primary_ip'] and webhook_json_data['data']['primary_ip']['address']:
                            results = tc.proxmox_lxc_set_net0(webhook_json_data)

                        if (webhook_json_data['snapshots']['prechange']['vcpus'] != webhook_json_data['snapshots']['postchange']['vcpus']) or (webhook_json_data['snapshots']['prechange']['memory'] != webhook_json_data['snapshots']['postchange']['memory']):
                            results = tc.proxmox_update_lxc_vpus_and_memory(webhook_json_data)
                        else:
                            results = (200, {'result': 'No resources to change'})
                    elif webhook_json_data['event'] == 'deleted':
                        results = tc.proxmox_delete_lxc(webhook_json_data)
                elif webhook_json_data['event'] == 'updated':
                    if webhook_json_data['data']['status']['value'] == 'offline':
                        results = tc.proxmox_stop_lxc(webhook_json_data)
                    elif webhook_json_data['data']['status']['value'] == 'active':
                        results = tc.proxmox_start_lxc(webhook_json_data)
                    else:
                        results = (500, {'result': f"Unknown value {webhook_json_data['data']['status']['value']}"})
                elif webhook_json_data['event'] == 'deleted':
                    results = tc.proxmox_delete_lxc(webhook_json_data)
                else:
                    results = (500, {'result': f"Unknown event: {webhook_json_data['event']}"})
        elif webhook_json_data['model'] == 'virtualdisk':
            results = 500, {'result': 'Something has gone wrong with virtualdisk management'}
            is_lxc = False

            if webhook_json_data['data']['name'] == 'rootfs':
                is_lxc = True

            if DEBUG:
                print("HERE VIRTUALDISK", is_lxc)

            tcall = NetBoxProxmoxHelper(app_config, None, DEBUG)
            proxmox_node = tcall.netbox_get_proxmox_node_from_vm_id(webhook_json_data['data']['virtual_machine']['id'])

            if is_lxc:
                if DEBUG:
                    print("change disk lxc")

                if webhook_json_data['event'] == 'updated':
                    if webhook_json_data['snapshots']['prechange']['size'] != webhook_json_data['snapshots']['postchange']['size']:
                        tc = NetBoxProxmoxHelperLXC(app_config, proxmox_node, DEBUG)
                        results = tc.proxmox_lxc_resize_disk(webhook_json_data)
                elif webhook_json_data['event'] == 'deleted':
                    results = 200, {'result': 'All good'}
            else:
                tc = NetBoxProxmoxHelperVM(app_config, proxmox_node, DEBUG)

                if webhook_json_data['event'] == 'created':
                    results = tc.proxmox_add_disk(webhook_json_data)
                elif webhook_json_data['event'] == 'updated':
                    results = tc.proxmox_resize_disk(webhook_json_data)
                elif webhook_json_data['event'] == 'deleted':
                    results = tc.proxmox_delete_disk(webhook_json_data)

        if DEBUG:
            print("RAW RESULTS", results)

        response = Response(
            json.dumps(results[1]),
            status = results[0],
            mimetype = 'application/json'
        )

        return response.status_code, {'result': response.json['result']}


if __name__ == "__main__":
    app.run(host="0.0.0.0")
