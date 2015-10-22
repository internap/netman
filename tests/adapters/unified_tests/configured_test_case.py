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
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.main import app
from .flask_helper import FlaskRequest


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

    def get_vlans(self):
        vlans = super(ValidatingCachedSwitch, self).get_vlans()
        assert_that(vlans, is_(self.real_switch.get_vlans()))
        return vlans


class ConfiguredTestCase(unittest.TestCase):
    switch_specs = None

    def setUp(self):
        specs = type(self).switch_specs
        self.switch_hostname = specs["hostname"]
        self.switch_port = specs["port"]
        self.switch_type = specs["model"]
        self.switch_username = specs["username"]
        self.switch_password = specs["password"]
        self.test_port = specs["test_port_name"]

        self.remote_switch = RemoteSwitch(SwitchDescriptor(
            netman_server='', **sub_dict(
                specs, 'hostname', 'port', 'model', 'username', 'password')))
        self.remote_switch.requests = FlaskRequest(app.test_client())

        self.client = ValidatingCachedSwitch(self.remote_switch)

    def get_vlan(self, number):
        try:
            return next((vlan for vlan in self.client.get_vlans()
                         if vlan.number == number))
        except StopIteration:
            raise AssertionError("Vlan #{} not found".format(number))


def skip_on_switches(*to_skip):

    def resource_decorator(fn):
        @wraps(fn)
        def wrapper(self, *args, **kwargs):
            if not self.switch_type in to_skip:
                return fn(self, *args, **kwargs)

            else:
                raise SkipTest('Test not executed on Switch model %s' % self.switch_type)

        return wrapper

    return resource_decorator
