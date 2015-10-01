# Copyright 2015 Internap.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import importlib
import json
import __builtin__
import uuid

import requests
from netman import raw_or_json

from netman.core.objects.exceptions import NetmanException
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.switch_base import SwitchBase
from netman.api.objects.vlan import SerializableVlan
from netman.api.objects.interface import SerializableInterface
from netman.api.objects.bond import SerializableBond


def factory(switch_descriptor):
    return RemoteSwitch(switch_descriptor)


class RemoteSwitch(SwitchBase):

    def __init__(self, switch_descriptor):
        super(RemoteSwitch, self).__init__(switch_descriptor)
        self.requests = requests
        self.session_id = None

        if isinstance(self.switch_descriptor.netman_server, list):
            self._proxy = self.switch_descriptor.netman_server[0]
            self._next_proxies = self.switch_descriptor.netman_server[1:]
        else:
            self._proxy = self.switch_descriptor.netman_server
            self._next_proxies = []

    def connect(self):
        pass

    def disconnect(self):
        pass

    def start_transaction(self):
        self.session_id = str(uuid.uuid4())
        url = "{netman}/switches-sessions/{session_id}".format(netman=self._proxy, session_id=self.session_id)
        details = self.request()
        details['headers']['Netman-Session-Id'] = self.session_id
        self.validated(self.requests.post(
            url=url,
            data=json.dumps({'hostname': self.switch_descriptor.hostname}),
            headers=details['headers'])
        )

    def commit_transaction(self):
        url = "{netman}/switches-sessions/{session_id}/actions".format(netman=self._proxy, session_id=self.session_id)
        self.validated(self.requests.post(url=url, headers={'Netman-Verbose-Errors': "yes",
                                                            'Netman-Session-Id': self.session_id}, data='commit'))

    def rollback_transaction(self):
        url = "{netman}/switches-sessions/{session_id}/actions".format(netman=self._proxy, session_id=self.session_id)
        self.validated(self.requests.post(url=url, headers={'Netman-Verbose-Errors': "yes",
                                                            'Netman-Session-Id': self.session_id}, data='rollback'))

    def end_transaction(self):
        url = "{netman}/switches-sessions/{session_id}".format(netman=self._proxy, session_id=self.session_id)
        session_id = self.session_id
        self.session_id = None
        self.validated(self.requests.delete(url=url, headers={'Netman-Verbose-Errors': "yes",
                                                              'Netman-Session-Id': session_id}))

    def get_vlans(self):
        return [SerializableVlan.to_core(**row) for row in self.get("/vlans").json()]

    def get_interfaces(self):
        return [SerializableInterface.to_core(**row) for row in self.get("/interfaces").json()]

    def get_bond(self, number):
        return SerializableBond.to_core(**self.get('/bonds/%s' % number).json())

    def get_bonds(self):
        return [SerializableBond.to_core(**row) for row in self.get("/bonds").json()]

    def add_vlan(self, number, name=None):
        data = {'number': number}
        if name is not None:
            data['name'] = name
        self.post("/vlans", data=data)

    def remove_vlan(self, number):
        self.delete("/vlans/{0}".format(str(number)))

    def set_vlan_access_group(self, vlan_number, direction, name):
        self.put('/vlans/{vlan_number}/access-groups/{direction}'.format(
            vlan_number=vlan_number,
            direction={IN: 'in', OUT: 'out'}[direction]
        ), raw_data=name)

    def remove_vlan_access_group(self, vlan_number, direction):
        self.delete('/vlans/{vlan_number}/access-groups/{direction}'.format(
            vlan_number=vlan_number,
            direction={IN: 'in', OUT: 'out'}[direction]
        ))

    def add_ip_to_vlan(self, vlan_number, ip_network):
        self.post('/vlans/{vlan_number}/ips'.format(
            vlan_number=vlan_number
        ), raw_data=str(ip_network))

    def remove_ip_from_vlan(self, vlan_number, ip_network):
        self.delete('/vlans/{vlan_number}/ips/{ip_network}'.format(
            vlan_number=vlan_number,
            ip_network=ip_network
        ))

    def set_vlan_vrf(self, vlan_number, vrf_name):
        self.put('/vlans/{vlan_number}/vrf-forwarding'.format(
            vlan_number=vlan_number
        ), raw_data=str(vrf_name))

    def remove_vlan_vrf(self, vlan_number):
        self.delete('/vlans/{vlan_number}/vrf-forwarding'.format(vlan_number=vlan_number))

    def set_access_mode(self, interface_id):
        self.put("/interfaces/" + interface_id + '/port-mode', raw_data='access')

    def set_trunk_mode(self, interface_id):
        self.put("/interfaces/" + interface_id + '/port-mode', raw_data='trunk')

    def set_bond_access_mode(self, bond_number):
        self.put("/bonds/" + str(bond_number) + '/port-mode', raw_data='access')

    def set_bond_trunk_mode(self, bond_number):
        self.put("/bonds/" + str(bond_number) + '/port-mode', raw_data='trunk')

    def set_access_vlan(self, interface_id, vlan):
        self.put("/interfaces/" + interface_id + '/access-vlan', raw_data=str(vlan))

    def remove_access_vlan(self, interface_id):
        self.delete("/interfaces/" + interface_id + '/access-vlan')

    def configure_native_vlan(self, interface_id, vlan):
        self.put("/interfaces/" + interface_id + '/trunk-native-vlan', raw_data=str(vlan))

    def remove_native_vlan(self, interface_id):
        self.delete("/interfaces/" + interface_id + '/trunk-native-vlan')

    def configure_bond_native_vlan(self, bond_number, vlan):
        self.put("/bonds/" + str(bond_number) + '/trunk-native-vlan', raw_data=str(vlan))

    def remove_bond_native_vlan(self, bond_number):
        self.delete("/bonds/" + str(bond_number) + '/trunk-native-vlan')

    def add_trunk_vlan(self, interface_id, vlan):
        self.post("/interfaces/" + interface_id + '/trunk-vlans', raw_data=str(vlan))

    def remove_trunk_vlan(self, interface_id, vlan):
        self.delete("/interfaces/" + interface_id + '/trunk-vlans/' + str(vlan))

    def add_bond_trunk_vlan(self, bond_number, vlan):
        self.post("/bonds/" + str(bond_number) + '/trunk-vlans', raw_data=str(vlan))

    def remove_bond_trunk_vlan(self, bond_number, vlan):
        self.delete("/bonds/" + str(bond_number) + '/trunk-vlans/' + str(vlan))

    def set_interface_description(self, interface_id, description):
        self.put("/interfaces/" + interface_id + '/description', raw_data=description)

    def remove_interface_description(self, interface_id):
        self.delete("/interfaces/" + interface_id + '/description')

    def set_bond_description(self, bond_number, description):
        self.put("/bonds/" + str(bond_number) + '/description', raw_data=description)

    def remove_bond_description(self, bond_number):
        self.delete("/bonds/" + str(bond_number) + '/description')

    def edit_interface_spanning_tree(self, interface_id, edge=None):
        data = {}
        if edge is not None:
            data["edge"] = edge

        self.put("/interfaces/" + interface_id + '/spanning-tree', data=data)

    def openup_interface(self, interface_id):
        self.put("/interfaces/" + interface_id + '/shutdown', raw_data='false')

    def shutdown_interface(self, interface_id):
        self.put("/interfaces/" + interface_id + '/shutdown', raw_data='true')

    def add_bond(self, number):
        self.post("/bonds", data={'number': number})

    def remove_bond(self, number):
        self.delete("/bonds/" + str(number))

    def add_interface_to_bond(self, interface, bond_number):
        self.put("/interfaces/" + interface + '/bond-master', raw_data=str(bond_number))

    def remove_interface_from_bond(self, interface):
        self.delete("/interfaces/" + interface + '/bond-master')

    def set_bond_link_speed(self, number, speed):
        self.put("/bonds/{0}/link-speed".format(number), raw_data=speed)

    def edit_bond_spanning_tree(self, number, edge=None):
        data = {}
        if edge is not None:
            data["edge"] = edge

        self.put("/bonds/{0}/spanning-tree".format(number), data=data)

    def add_vrrp_group(self, vlan_number, group_id, ips=None, priority=None, hello_interval=None, dead_interval=None,
                       track_id=None, track_decrement=None):
        self.post("/vlans/{}/vrrp-groups".format(vlan_number),
                  data=dict(id=group_id, ips=[str(ip) for ip in ips], priority=priority,
                            hello_interval=hello_interval, dead_interval=dead_interval, track_id=track_id,
                            track_decrement=track_decrement))

    def remove_vrrp_group(self, vlan_number, group_id):
        self.delete("/vlans/{}/vrrp-groups/{}".format(vlan_number, group_id))

    def add_dhcp_relay_server(self, vlan_number, ip_address):
        self.post("/vlans/{}/dhcp-relay-server".format(
            vlan_number), raw_data=str(ip_address))

    def remove_dhcp_relay_server(self, vlan_number, ip_address):
        self.delete("/vlans/{}/dhcp-relay-server/{}".format(
            vlan_number, ip_address))

    def enable_lldp(self, interface_id, enabled):
        self.put("/interfaces/{}/lldp".format(interface_id),
                 raw_data={True: "true", False: "false"}[enabled])

    def get(self, relative_url):
        return self.validated(self.requests.get(**self.request(relative_url)))

    def post(self, relative_url, data=None, raw_data=None):
        return self.validated(self.requests.post(data=raw_or_json(raw_data, data), **self.request(relative_url)))

    def put(self, relative_url, data=None, raw_data=None):
        return self.validated(self.requests.put(data=raw_or_json(raw_data, data), **self.request(relative_url)))

    def delete(self, relative_url):
        return self.validated(self.requests.delete(**self.request(relative_url)))

    def request(self, relative_url=''):
        headers = {
            'Netman-Model': self.switch_descriptor.model,
            'Netman-Username': self.switch_descriptor.username,
            'Netman-Password': self.switch_descriptor.password,
            'Netman-Port': self.switch_descriptor.port,
            'Netman-Verbose-Errors': "yes"
        }

        if len(self._next_proxies) > 0:
            headers["Netman-Proxy-Server"] = ",".join(self._next_proxies)

        if self.session_id:
            url = "{netman_url}/switches-sessions/{session_id}{path}".format(
                netman_url=self._proxy,
                session_id=self.session_id,
                path=relative_url
            )
            headers['Netman-Session-Id'] = self.session_id
        else:
            url = "{netman_url}/switches/{switch}{path}".format(
                netman_url=self._proxy,
                switch=self.switch_descriptor.hostname,
                path=relative_url)
        self.logger.info("Querying " + url)
        return {
            "url": url,
            "headers": headers,
        }

    def validated(self, req):
        if req.status_code >= 400:
            try:
                error = req.json()
            except Exception as e:
                self.logger.exception(e)
                raise Exception("{0}: {1}".format(req.status_code, req.content))

            if "error-class" in error:
                if "error-module" in error:
                    try:
                        module = importlib.import_module(error["error-module"])
                        exception = getattr(module, error["error-class"])()
                        exception.args = (error["error"], )
                        exception.message = error["error"]
                    except:
                        exception = NetmanException('{error-module}.{error-class}: {error}'.format(**error))
                else:
                    exception = getattr(__builtin__, error["error-class"])(error["error"])
            else:
                exception = Exception(error["error"])

            raise exception
        return req
