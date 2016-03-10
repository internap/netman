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
from unittest import TestCase

from hamcrest import assert_that, is_

from netman.core.objects.switch_descriptor import SwitchDescriptor
from tests import ignore_deprecation_warnings


class SwitchDescriptorTest(TestCase):

    @ignore_deprecation_warnings
    def test_backward_compatibility_on_members_given_to_ctor(self):
        s = SwitchDescriptor("model", "name",
                             default_vrf="String",
                             default_lan_acl_in="String",
                             default_lan_acl_out="String",
                             trunked_interfaces=["list"],
                             parking_vlan=123,
                             default_port_speed="String",
                             vrrp_tracking_object="String")

        assert_that(s.default_vrf, is_("String"))
        assert_that(s.default_lan_acl_in, is_("String"))
        assert_that(s.default_lan_acl_out, is_("String"))
        assert_that(s.trunked_interfaces, is_(["list"]))
        assert_that(s.parking_vlan, is_(123))
        assert_that(s.default_port_speed, is_("String"))
        assert_that(s.vrrp_tracking_object, is_("String"))

    @ignore_deprecation_warnings
    def test_backward_compatibility_on_get_and_Set(self):
        s = SwitchDescriptor("model", "name")

        assert_that(s.default_vrf, is_(None))
        assert_that(s.default_lan_acl_in, is_(None))
        assert_that(s.default_lan_acl_out, is_(None))
        assert_that(s.trunked_interfaces, is_(None))
        assert_that(s.parking_vlan, is_(None))
        assert_that(s.default_port_speed, is_(None))
        assert_that(s.vrrp_tracking_object, is_(None))

        s.default_vrf = "String"
        assert_that(s.default_vrf, is_("String"))

        s.default_lan_acl_in="String"
        assert_that(s.default_lan_acl_in, is_("String"))

        s.default_lan_acl_out="String"
        assert_that(s.default_lan_acl_out, is_("String"))

        s.trunked_interfaces=["list"]
        assert_that(s.trunked_interfaces, is_(["list"]))

        s.parking_vlan=123
        assert_that(s.parking_vlan, is_(123))

        s.default_port_speed="String"
        assert_that(s.default_port_speed, is_("String"))

        s.vrrp_tracking_object="String"
        assert_that(s.vrrp_tracking_object, is_("String"))
