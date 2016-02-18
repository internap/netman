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

import unittest
from functools import wraps
from unittest import SkipTest

from hamcrest import assert_that, is_
from netman.adapters.switches.cached import CachedSwitch
from netman.adapters.switches.remote import RemoteSwitch
from netman.core.objects.exceptions import NetmanException
from netman.main import app
from tests.adapters.flask_helper import FlaskRequest
from tests.adapters.model_list import available_models


def sub_dict(d, *keys):
    return dict((k, d[k]) for k in keys)


class ValidatingCachedSwitch(CachedSwitch):
    def get_bond(self, number):
        bond = super(ValidatingCachedSwitch, self).get_bond(number)
        assert_that(bond, is_(self.real_switch.get_bond(number)))
        return bond

    def get_bonds(self):
        bonds = super(ValidatingCachedSwitch, self).get_bonds()
        assert_that(bonds, is_(self.real_switch.get_bonds()))
        return bonds

    def get_interfaces(self):
        interfaces = super(ValidatingCachedSwitch, self).get_interfaces()
        assert_that(interfaces, is_(self.real_switch.get_interfaces()))
        return interfaces

    def get_interface(self, interface_id):
        interface = super(ValidatingCachedSwitch, self).get_interface(interface_id)
        assert_that(interface, is_(self.real_switch.get_interface(interface_id)))
        return interface

    def get_vlan(self, number):
        vlan = super(ValidatingCachedSwitch, self).get_vlan(number)
        assert_that(vlan, is_(self.real_switch.get_vlan(number)))
        return vlan

    def get_vlans(self):
        vlans = super(ValidatingCachedSwitch, self).get_vlans()
        assert_that(vlans, is_(self.real_switch.get_vlans()))
        return vlans

    def get_vlan_interfaces(self, number):
        vlan_interfaces = super(ValidatingCachedSwitch, self).get_vlan_interfaces(number)
        assert_that(vlan_interfaces, is_(self.real_switch.get_vlan_interfaces(number)))
        return vlan_interfaces


class ConfiguredTestCase(unittest.TestCase):
    _dev_sample = None
    switch_specs = None

    def setUp(self):
        if self.switch_specs is not None:
            specs = type(self).switch_specs
        else:
            specs = next(s for s in available_models if s["switch_descriptor"].model == self._dev_sample)

        self.switch_descriptor = specs["switch_descriptor"]
        self.test_port = specs["test_port_name"]
        self.test_ports = specs["ports"]
        self.test_vrrp_track_id = specs.get("test_vrrp_track_id")

        self.switch_descriptor.netman_server = ''
        self.remote_switch = RemoteSwitch(self.switch_descriptor)
        self.remote_switch.requests = FlaskRequest(app.test_client())

        self.client = ValidatingCachedSwitch(self.remote_switch)
        self.try_to = ExceptionIgnoringProxy(self.client, [NotImplementedError])
        self.janitor = ExceptionIgnoringProxy(self.client, [NotImplementedError, NetmanException])

        self.client.connect()
        self.client.start_transaction()

    def tearDown(self):
        self.client.end_transaction()
        self.client.disconnect()

    def get_vlan_from_list(self, number):
        try:
            return next((vlan for vlan in self.client.get_vlans()
                         if vlan.number == number))
        except StopIteration:
            raise AssertionError("Vlan #{} not found".format(number))


def skip_on_switches(*to_skip):

    def resource_decorator(fn):
        @wraps(fn)
        def wrapper(self, *args, **kwargs):
            if not self.switch_descriptor.model in to_skip:
                return fn(self, *args, **kwargs)

            else:
                raise SkipTest('Test not executed on Switch model %s' % self.switch_descriptor.model)

        return wrapper

    return resource_decorator


class ExceptionIgnoringProxy(object):
    def __init__(self, target, exceptions):
        self.target = target
        self.exceptions = tuple(exceptions)

    def __getattr__(self, item):
        def wrapper(*args, **kwargs):
            try:
                return getattr(self.target, item)(*args, **kwargs)
            except self.exceptions:
                return None

        return wrapper
