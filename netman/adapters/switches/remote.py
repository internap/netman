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
import warnings

import requests
from netman import raw_or_json
from netman.api import NETMAN_API_VERSION

from netman.core.objects.exceptions import NetmanException, UnknownSession
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.interface_states import OFF, ON
from netman.core.objects.switch_base import SwitchBase
from netman.api.objects import vlan
from netman.api.objects import interface
from netman.api.objects import bond


def factory(switch_descriptor):
    warnings.warn("Use SwitchFactory.get_switch_by_descriptor directly to instanciate a switch", DeprecationWarning)
    return RemoteSwitch(switch_descriptor)


class RemoteSwitch(SwitchBase):
    max_version = NETMAN_API_VERSION

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

    def _connect(self):
        self.session_id = str(uuid.uuid4())
        self.logger.info("Requesting session {}".format(self.session_id))
        url = "{netman}/switches-sessions/{session_id}".format(netman=self._proxy, session_id=self.session_id)
        details = self.request()
        details['headers']['Netman-Session-Id'] = self.session_id
        self.validated(self.requests.post(
            url=url,
            data=json.dumps({'hostname': self.switch_descriptor.hostname}),
            headers=details['headers'])
        )
        self.logger.info("Obtained session {}".format(self.session_id))

    def _disconnect(self):
        self.logger.info("Ending session {}".format(self.session_id))
        url = "{netman}/switches-sessions/{session_id}".format(netman=self._proxy, session_id=self.session_id)
        session_id = self.session_id
        self.session_id = None
        self.validated(self.requests.delete(url=url, headers={'Netman-Verbose-Errors': "yes",
                                                              'Netman-Max-Version': str(self.max_version),
                                                              'Netman-Session-Id': session_id}))
        self.logger.info("Ended session {}".format(self.session_id))

    def _start_transaction(self):
        self.logger.info("Starting Transaction for session_id: {}".format(self.session_id))
        url = "{netman}/switches-sessions/{session_id}/actions".format(netman=self._proxy, session_id=self.session_id)
        self.validated(self.requests.post(url=url, headers={'Netman-Verbose-Errors': "yes",
                                                            'Netman-Max-Version': str(self.max_version),
                                                            'Netman-Session-Id': self.session_id}, data='start_transaction'))
        self.logger.info("Started Transaction for session_id: {}".format(self.session_id))

    def commit_transaction(self):
        self.logger.info("Commiting {}".format(self.session_id))
        url = "{netman}/switches-sessions/{session_id}/actions".format(netman=self._proxy, session_id=self.session_id)
        self.validated(self.requests.post(url=url, headers={'Netman-Verbose-Errors': "yes",
                                                            'Netman-Max-Version': str(self.max_version),
                                                            'Netman-Session-Id': self.session_id}, data='commit'))
        self.logger.info("Commited {}".format(self.session_id))

    def rollback_transaction(self):
        self.logger.info("Rollbacking {}".format(self.session_id))
        url = "{netman}/switches-sessions/{session_id}/actions".format(netman=self._proxy, session_id=self.session_id)
        self.validated(self.requests.post(url=url, headers={'Netman-Verbose-Errors': "yes",
                                                            'Netman-Max-Version': str(self.max_version),
                                                            'Netman-Session-Id': self.session_id}, data='rollback'))
        self.logger.info("Rollbacked {}".format(self.session_id))

    def _end_transaction(self):
        self.logger.info("Ending Transaction for session_id: {}".format(self.session_id))
        url = "{netman}/switches-sessions/{session_id}/actions".format(netman=self._proxy, session_id=self.session_id)
        self.validated(self.requests.post(url=url, headers={'Netman-Verbose-Errors': "yes",
                                                            'Netman-Max-Version': str(self.max_version),
                                                            'Netman-Session-Id': self.session_id}, data='end_transaction'))
        self.logger.info("Transaction ended for session_id: {}".format(self.session_id))

    def get_vlan(self, number):
        return vlan.to_core(self.get("/vlans/{}".format(number)).json())

    def get_vlans(self):
        return [vlan.to_core(row) for row in self.get("/vlans").json()]

    def get_interface(self, interface_id):
        return interface.to_core(self.get("/interfaces/{}".format(interface_id)).json())

    def get_interfaces(self):
        return [interface.to_core(row) for row in self.get("/interfaces").json()]

    def get_bond(self, number):
        reply = self.get('/bonds/{}'.format(number))
        return bond.to_core(reply.json(), version=reply.headers.get('Netman-Version'))

    def get_bonds(self):
        reply = self.get("/bonds")
        return [bond.to_core(row, version=reply.headers.get('Netman-Version')) for row in reply.json()]

    def add_vlan(self, number, name=None):
        data = {'number': number}
        if name is not None:
            data['name'] = name
        self.post("/vlans", data=data)

    def remove_vlan(self, number):
        self.delete("/vlans/{0}".format(str(number)))

    def get_vlan_interfaces(self, vlan_number):
        return self.get("/vlans/{}/interfaces".format(vlan_number)).json()

    def set_vlan_access_group(self, vlan_number, direction, name):
        self.put('/vlans/{vlan_number}/access-groups/{direction}'.format(
            vlan_number=vlan_number,
            direction={IN: 'in', OUT: 'out'}[direction]
        ), raw_data=name)

    def unset_vlan_access_group(self, vlan_number, direction):
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

    def unset_vlan_vrf(self, vlan_number):
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

    def reset_interface(self, interface_id):
        self.put("/interfaces/" + interface_id)

    def unset_interface_access_vlan(self, interface_id):
        self.delete("/interfaces/" + interface_id + '/access-vlan')

    def set_interface_native_vlan(self, interface_id, vlan):
        self.put("/interfaces/" + interface_id + '/trunk-native-vlan', raw_data=str(vlan))

    def unset_interface_native_vlan(self, interface_id):
        self.delete("/interfaces/" + interface_id + '/trunk-native-vlan')

    def set_bond_native_vlan(self, bond_number, vlan):
        self.put("/bonds/" + str(bond_number) + '/trunk-native-vlan', raw_data=str(vlan))

    def unset_bond_native_vlan(self, bond_number):
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

    def unset_interface_description(self, interface_id):
        self.delete("/interfaces/" + interface_id + '/description')

    def set_bond_description(self, bond_number, description):
        self.put("/bonds/" + str(bond_number) + '/description', raw_data=description)

    def unset_bond_description(self, bond_number):
        self.delete("/bonds/" + str(bond_number) + '/description')

    def set_interface_mtu(self, interface_id, size):
        self.put("/interfaces/" + interface_id + '/mtu', raw_data=str(size))

    def unset_interface_mtu(self, interface_id):
        self.delete("/interfaces/" + interface_id + '/mtu')

    def set_bond_mtu(self, bond_number, size):
        self.put("/bonds/" + str(bond_number) + '/mtu', raw_data=str(size))

    def unset_bond_mtu(self, bond_number):
        self.delete("/bonds/" + str(bond_number) + '/mtu')

    def edit_interface_spanning_tree(self, interface_id, edge=None):
        data = {}
        if edge is not None:
            data["edge"] = edge

        self.put("/interfaces/" + interface_id + '/spanning-tree', data=data)

    def set_interface_state(self, interface_id, state):
        self.put("/interfaces/" + interface_id + '/shutdown', raw_data='true' if state is OFF else 'false')

    def unset_interface_state(self, interface_id):
        self.delete("/interfaces/" + interface_id + '/shutdown')

    def set_interface_auto_negotiation_state(self, interface_id, state):
        self.put("/interfaces/" + interface_id + '/auto-negotiation', raw_data='true' if state is ON else 'false')

    def unset_interface_auto_negotiation_state(self, interface_id):
        self.delete("/interfaces/" + interface_id + '/auto-negotiation')

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

    def set_interface_lldp_state(self, interface_id, enabled):
        self.put("/interfaces/{}/lldp".format(interface_id),
                 raw_data=_get_json_boolean(enabled))

    def set_vlan_icmp_redirects_state(self, vlan_number, state):
        self.put('/vlans/{}/icmp-redirects'.format(vlan_number),
                 raw_data=_get_json_boolean(state))

    def get_versions(self):
        return self.get("/versions").json()

    def get(self, relative_url):
        return self._retry_on_unknown_session(
            lambda: self.validated(
                self.requests.get(**self.request(relative_url))))

    def post(self, relative_url, data=None, raw_data=None):
        return self._retry_on_unknown_session(
            lambda: self.validated(
                self.requests.post(
                    data=raw_or_json(raw_data, data),
                    **self.request(relative_url))))

    def put(self, relative_url, data=None, raw_data=None):
        return self._retry_on_unknown_session(
            lambda: self.validated(
                self.requests.put(
                    data=raw_or_json(raw_data, data),
                    **self.request(relative_url))))

    def delete(self, relative_url):
        return self._retry_on_unknown_session(
            lambda: self.validated(
                self.requests.delete(**self.request(relative_url))))

    def request(self, relative_url=''):
        headers = {
            'Netman-Model': self.switch_descriptor.model,
            'Netman-Username': self.switch_descriptor.username,
            'Netman-Password': self.switch_descriptor.password,
            'Netman-Port': str(self.switch_descriptor.port),
            'Netman-Max-Version': str(self.max_version),
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

    def _retry_on_unknown_session(self, operation):
        try:
            return operation()
        except UnknownSession as e:
            self.logger.warning("Could not perform operation, {}...  "
                                "Requesting a new session".format(e))
            self._connect()
            return operation()


def _get_json_boolean(state):
    return {True: "true", False: "false"}[state]
