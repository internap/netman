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

import logging
import re
import textwrap
import unittest

import mock
from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, has_length, equal_to, contains_string, has_key, \
    is_, instance_of
from ncclient.devices.junos import JunosDeviceHandler
from ncclient.operations import RPCError, TimeoutExpiredError
from ncclient.xml_ import NCElement, to_ele, to_xml

from netman.adapters.switches import juniper
from netman.adapters.switches.juniper.base import Juniper
from netman.adapters.switches.juniper.standard import JuniperCustomStrategies
from netman.core.objects.access_groups import OUT, IN
from netman.core.objects.exceptions import LockedSwitch, VlanAlreadyExist, BadVlanNumber, BadVlanName, UnknownVlan, \
    InterfaceInWrongPortMode, UnknownInterface, AccessVlanNotSet, NativeVlanNotSet, TrunkVlanNotSet, VlanAlreadyInTrunk, \
    BadBondNumber, UnknownBond, InterfaceNotInBond, BondAlreadyExist, OperationNotCompleted, InvalidMtuSize
from netman.core.objects.interface_states import OFF, ON
from netman.core.objects.port_modes import ACCESS, TRUNK, BOND_MEMBER
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.objects.switch_transactional import FlowControlSwitch
from tests import ignore_deprecation_warnings


@ignore_deprecation_warnings
def test_factory():
    lock = mock.Mock()
    switch = juniper.standard_factory(SwitchDescriptor(hostname='hostname', model='juniper', username='username', password='password', port=22), lock)

    assert_that(switch, instance_of(FlowControlSwitch))
    assert_that(switch.wrapped_switch, instance_of(Juniper))
    assert_that(switch.lock, is_(lock))
    assert_that(switch.switch_descriptor.hostname, equal_to("hostname"))
    assert_that(switch.switch_descriptor.model, equal_to("juniper"))
    assert_that(switch.switch_descriptor.username, equal_to("username"))
    assert_that(switch.switch_descriptor.password, equal_to("password"))
    assert_that(switch.switch_descriptor.port, equal_to(22))


class JuniperTest(unittest.TestCase):

    def setUp(self):
        self.switch = juniper.standard.netconf(SwitchDescriptor(model='juniper', hostname="toto"))

        self.netconf_mock = flexmock()
        self.switch.netconf = self.netconf_mock
        self.switch.in_transaction = True

    def tearDown(self):
        flexmock_teardown()

    def test_switch_has_a_logger_configured_with_the_switch_name(self):
        assert_that(self.switch.logger.name, is_(Juniper.__module__ + ".toto"))

    def test_get_vlans(self):
        self.switch.in_transaction = False

        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>STANDARD</name>
                <vlan-id>10</vlan-id>
                <description>my-description</description>
              </vlan>
              <vlan>
                <name>NO-VLAN-ID</name>
                <description>shizzle</description>
              </vlan>
              <vlan>
                <name>WITH-IF</name>
                <vlan-id>20</vlan-id>
                <l3-interface>vlan.20</l3-interface>
              </vlan>
              <vlan>
                <name>WITH-IF-MULTI-IP</name>
                <vlan-id>40</vlan-id>
                <l3-interface>vlan.70</l3-interface>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/1</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>vlan</name>
                <unit>
                  <name>20</name>
                  <family>
                    <inet>
                      <address>
                        <name>1.1.1.1/24</name>
                      </address>
                      <filter>
                        <input>
                          <filter-name>AC-IN</filter-name>
                        </input>
                        <output>
                          <filter-name>AC-OUT</filter-name>
                        </output>
                      </filter>
                    </inet>
                  </family>
                </unit>
                <unit>
                  <name>40</name>
                </unit>
                <unit>
                  <name>70</name>
                  <family>
                    <inet>
                      <address>
                        <name>2.1.1.1/24</name>
                      </address>
                      <address>
                        <name>4.1.1.1/24</name>
                      </address>
                      <address>
                        <name>3.1.1.1/24</name>
                      </address>
                    </inet>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        vlan10, vlan20, vlan40 = self.switch.get_vlans()

        assert_that(vlan10.number, equal_to(10))
        assert_that(vlan10.name, equal_to("my-description"))
        assert_that(vlan10.access_groups[IN], equal_to(None))
        assert_that(vlan10.access_groups[OUT], equal_to(None))
        assert_that(vlan10.ips, has_length(0))

        assert_that(vlan20.number, equal_to(20))
        assert_that(vlan20.name, equal_to(None))
        assert_that(vlan20.access_groups[IN], equal_to("AC-IN"))
        assert_that(vlan20.access_groups[OUT], equal_to("AC-OUT"))
        assert_that(vlan20.ips, has_length(1))
        vlan20ip1 = vlan20.ips[0]
        assert_that(str(vlan20ip1.ip), equal_to("1.1.1.1"))
        assert_that(vlan20ip1.prefixlen, equal_to(24))

        assert_that(vlan40.number, equal_to(40))
        assert_that(vlan40.name, equal_to(None))
        assert_that(vlan40.access_groups[IN], equal_to(None))
        assert_that(vlan40.access_groups[OUT], equal_to(None))
        vlan40ip1, vlan40ip2, vlan40ip3 = vlan40.ips
        assert_that(str(vlan40ip1.ip), equal_to("2.1.1.1"))
        assert_that(vlan40ip1.prefixlen, equal_to(24))
        assert_that(str(vlan40ip2.ip), equal_to("3.1.1.1"))
        assert_that(vlan40ip2.prefixlen, equal_to(24))
        assert_that(str(vlan40ip3.ip), equal_to("4.1.1.1"))
        assert_that(vlan40ip3.prefixlen, equal_to(24))

    def test_get_vlans_where_vlan_interfaces_can_also_be_called_irb(self):
        self.switch.in_transaction = True

        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>ON_VLAN</name>
                <vlan-id>10</vlan-id>
                <l3-interface>vlan.10</l3-interface>
              </vlan>
              <vlan>
                <name>ON_IRB</name>
                <vlan-id>20</vlan-id>
                <l3-interface>irb.20</l3-interface>
              </vlan>
              <vlan>
                <name>ON_WHATEVER</name>
                <vlan-id>30</vlan-id>
                <l3-interface>whatever.30</l3-interface>
              </vlan>
              <vlan>
                <name>ON_NOTFOUND</name>
                <vlan-id>40</vlan-id>
                <l3-interface>notfound.20</l3-interface>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/1</name>
              </interface>
              <interface>
                <name>vlan</name>
                <unit>
                  <name>10</name>
                  <family>
                    <inet>
                      <address>
                        <name>1.1.1.1/24</name>
                      </address>
                    </inet>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>irb</name>
                <unit>
                  <name>20</name>
                  <family>
                    <inet>
                      <address>
                        <name>2.1.1.1/24</name>
                      </address>
                    </inet>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>whatever</name>
                <unit>
                  <name>30</name>
                  <family>
                    <inet>
                      <address>
                        <name>3.1.1.1/24</name>
                      </address>
                    </inet>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        vlan10, vlan20, vlan30, vlan40 = self.switch.get_vlans()

        assert_that(str(vlan10.ips[0].ip), equal_to("1.1.1.1"))
        assert_that(str(vlan20.ips[0].ip), equal_to("2.1.1.1"))
        assert_that(str(vlan30.ips[0].ip), equal_to("3.1.1.1"))
        assert_that(vlan40.ips, has_length(0))

    def test_get_vlan_interfaces(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                    <filter>
                      <configuration>
                        <vlans>
                          <vlan>
                            <vlan-id>705</vlan-id>
                          </vlan>
                        </vlans>
                        <interfaces />
                      </configuration>
                    </filter>
                """)).and_return(a_configuration("""
                    <vlans>
                      <vlan>
                        <name>VLAN705</name>
                        <vlan-id>705</vlan-id>
                      </vlan>
                    </vlans>
                    <interfaces>
                        <interface>
                          <name>xe-0/0/6</name>
                          <unit>
                            <family>
                              <ethernet-switching>
                                <vlan>
                                  <members>687</members>
                                  <members>705</members>
                                  <members>708</members>
                                </vlan>
                              </ethernet-switching>
                            </family>
                          </unit>
                        </interface>
                        <interface>
                          <name>xe-0/0/7</name>
                          <unit>
                            <family>
                              <ethernet-switching>
                                <vlan>
                                  <members>705</members>
                                </vlan>
                              </ethernet-switching>
                            </family>
                          </unit>
                        </interface>
                        <interface>
                          <name>xe-0/0/8</name>
                          <unit>
                            <family>
                              <ethernet-switching>
                                <vlan>
                                  <members>456</members>
                                </vlan>
                              </ethernet-switching>
                            </family>
                          </unit>
                        </interface>
                        <interface>
                          <name>xe-0/0/9</name>
                          <unit>
                            <family>
                              <ethernet-switching>
                                <vlan>
                                  <members>700-800</members>
                                </vlan>
                              </ethernet-switching>
                            </family>
                          </unit>
                        </interface>
                    </interfaces>
                """))

        vlan_interfaces = self.switch.get_vlan_interfaces(705)

        assert_that(vlan_interfaces, equal_to(["xe-0/0/6", "xe-0/0/7", "xe-0/0/9"]))

    def test_get_vlan_interfaces_with_name_as_member(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                        <filter>
                          <configuration>
                            <vlans>
                              <vlan>
                                <vlan-id>705</vlan-id>
                              </vlan>
                            </vlans>
                            <interfaces />
                          </configuration>
                        </filter>
                    """)).and_return(a_configuration("""
                        <vlans>
                          <vlan>
                            <name>bleu</name>
                            <vlan-id>705</vlan-id>
                          </vlan>
                        </vlans>
                        <interfaces>
                            <interface>
                              <name>xe-0/0/9</name>
                              <unit>
                                <family>
                                  <ethernet-switching>
                                    <vlan>
                                      <members>bleu</members>
                                    </vlan>
                                  </ethernet-switching>
                                </family>
                              </unit>
                            </interface>
                        </interfaces>
                    """))

        vlan_interfaces = self.switch.get_vlan_interfaces(705)

        assert_that(vlan_interfaces, equal_to(["xe-0/0/9"]))

    def test_get_vlan_interfaces_nonexisting_vlan(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                    <filter>
                      <configuration>
                        <vlans>
                          <vlan>
                            <vlan-id>9999999</vlan-id>
                          </vlan>
                        </vlans>
                        <interfaces />
                      </configuration>
                    </filter>
                """)).and_return(a_configuration("""
                    <vlans />
                    <interfaces>
                        <interface>
                          <name>xe-0/0/9</name>
                          <unit>
                            <family>
                              <ethernet-switching>
                                <vlan>
                                  <members>705</members>
                                </vlan>
                              </ethernet-switching>
                            </family>
                          </unit>
                        </interface>
                    </interfaces>
                """))
        with self.assertRaises(UnknownVlan):
            self.switch.get_vlan_interfaces("9999999")

    def test_get_vlan_with_no_interface(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                <filter>
                  <configuration>
                    <vlans />
                    <interfaces />
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <vlans>
                  <vlan>
                    <name>STANDARD</name>
                    <vlan-id>10</vlan-id>
                    <description>my-description</description>
                  </vlan>
                </vlans>
            """))

        vlan = self.switch.get_vlan(10)

        assert_that(vlan.number, equal_to(10))
        assert_that(vlan.name, equal_to("my-description"))
        assert_that(vlan.access_groups[IN], equal_to(None))
        assert_that(vlan.access_groups[OUT], equal_to(None))
        assert_that(vlan.ips, has_length(0))

    def test_get_vlan_with_unknown_vlan(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                <filter>
                  <configuration>
                    <vlans />
                    <interfaces />
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
            """))

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.get_vlan(10)

        assert_that(str(expect.exception), equal_to("Vlan 10 not found"))

    def test_get_vlan_with_interface(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                <filter>
                  <configuration>
                    <vlans />
                    <interfaces />
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <vlans>
                  <vlan>
                    <name>WITH-IF</name>
                    <vlan-id>20</vlan-id>
                    <l3-interface>vlan.20</l3-interface>
                  </vlan>
                </vlans>
                <interfaces>
              <interface>
                <name>ge-0/0/1</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
                  <interface>
                    <name>ge-0/0/1</name>
                  </interface>
                  <interface>
                    <name>vlan</name>
                    <unit>
                      <name>20</name>
                      <family>
                        <inet>
                          <address>
                            <name>1.1.1.1/24</name>
                          </address>
                          <filter>
                            <input>
                              <filter-name>AC-IN</filter-name>
                            </input>
                            <output>
                              <filter-name>AC-OUT</filter-name>
                            </output>
                          </filter>
                        </inet>
                      </family>
                    </unit>
                    <unit>
                      <name>40</name>
                    </unit>
                    <unit>
                      <name>70</name>
                      <family>
                        <inet>
                          <address>
                            <name>2.1.1.1/24</name>
                          </address>
                          <address>
                            <name>4.1.1.1/24</name>
                          </address>
                          <address>
                            <name>3.1.1.1/24</name>
                          </address>
                        </inet>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
            """))

        vlan = self.switch.get_vlan(20)

        assert_that(vlan.number, equal_to(20))
        assert_that(vlan.name, equal_to(None))
        assert_that(vlan.access_groups[IN], equal_to("AC-IN"))
        assert_that(vlan.access_groups[OUT], equal_to("AC-OUT"))
        assert_that(vlan.ips, has_length(1))
        vlan20ip1 = vlan.ips[0]
        assert_that(str(vlan20ip1.ip), equal_to("1.1.1.1"))
        assert_that(vlan20ip1.prefixlen, equal_to(24))

    def test_get_vlan_with_interface_multi_ip(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                <filter>
                  <configuration>
                    <vlans />
                    <interfaces />
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <vlans>
                  <vlan>
                    <name>WITH-IF-MULTI-IP</name>
                    <vlan-id>40</vlan-id>
                    <l3-interface>vlan.70</l3-interface>
                  </vlan>
                </vlans>
                <interfaces>
                  <interface>
                    <name>ge-0/0/1</name>
                  </interface>
                  <interface>
                    <name>vlan</name>
                    <unit>
                      <name>20</name>
                      <family>
                        <inet>
                          <address>
                            <name>1.1.1.1/24</name>
                          </address>
                          <filter>
                            <input>
                              <filter-name>AC-IN</filter-name>
                            </input>
                            <output>
                              <filter-name>AC-OUT</filter-name>
                            </output>
                          </filter>
                        </inet>
                      </family>
                    </unit>
                    <unit>
                      <name>40</name>
                    </unit>
                    <unit>
                      <name>70</name>
                      <family>
                        <inet>
                          <address>
                            <name>2.1.1.1/24</name>
                          </address>
                          <address>
                            <name>4.1.1.1/24</name>
                          </address>
                          <address>
                            <name>3.1.1.1/24</name>
                          </address>
                        </inet>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
            """))

        vlan = self.switch.get_vlan(40)

        assert_that(vlan.number, equal_to(40))
        assert_that(vlan.name, equal_to(None))
        assert_that(vlan.access_groups[IN], equal_to(None))
        assert_that(vlan.access_groups[OUT], equal_to(None))
        vlanip1, vlanip2, vlanip3 = vlan.ips
        assert_that(str(vlanip1.ip), equal_to("2.1.1.1"))
        assert_that(vlanip1.prefixlen, equal_to(24))
        assert_that(str(vlanip2.ip), equal_to("3.1.1.1"))
        assert_that(vlanip2.prefixlen, equal_to(24))
        assert_that(str(vlanip3.ip), equal_to("4.1.1.1"))
        assert_that(vlanip3.prefixlen, equal_to(24))

    def test_get_vlan_where_vlan_interfaces_can_also_be_called_irb(self):
        self.switch.in_transaction = True
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>NOT_GOOD_ONE</name>
                <vlan-id>19</vlan-id>
              </vlan>
              <vlan>
                <name>ON_IRB</name>
                <vlan-id>20</vlan-id>
                <l3-interface>irb.20</l3-interface>
              </vlan>
              <vlan>
                <name>NOT_GOOD_TWO</name>
                <vlan-id>21</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/1</name>
              </interface>
              <interface>
                <name>vlan</name>
                <unit>
                  <name>10</name>
                  <family>
                    <inet>
                      <address>
                        <name>1.1.1.1/24</name>
                      </address>
                    </inet>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>irb</name>
                <unit>
                  <name>20</name>
                  <family>
                    <inet>
                      <address>
                        <name>2.1.1.1/24</name>
                      </address>
                    </inet>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>whatever</name>
                <unit>
                  <name>30</name>
                  <family>
                    <inet>
                      <address>
                        <name>3.1.1.1/24</name>
                      </address>
                    </inet>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        vlan = self.switch.get_vlan(20)

        assert_that(str(vlan.ips[0].ip), equal_to("2.1.1.1"))

    def test_get_vlan_where_vlan_interfaces_not_found(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>NOT_FOUND</name>
                <vlan-id>40</vlan-id>
                <l3-interface>notfound.20</l3-interface>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/1</name>
              </interface>
              <interface>
                <name>vlan</name>
                <unit>
                  <name>10</name>
                  <family>
                    <inet>
                      <address>
                        <name>1.1.1.1/24</name>
                      </address>
                    </inet>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>irb</name>
                <unit>
                  <name>20</name>
                  <family>
                    <inet>
                      <address>
                        <name>2.1.1.1/24</name>
                      </address>
                    </inet>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>whatever</name>
                <unit>
                  <name>30</name>
                  <family>
                    <inet>
                      <address>
                        <name>3.1.1.1/24</name>
                      </address>
                    </inet>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        vlan = self.switch.get_vlan(40)

        assert_that(vlan.ips, has_length(0))

    def test_get_interface(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                    <interface>
                        <name>ge-0/0/1</name>
                    </interface>
                </interfaces>
                <vlans />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/1</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        interface = self.switch.get_interface('ge-0/0/1')

        assert_that(interface.name, equal_to("ge-0/0/1"))
        assert_that(interface.shutdown, equal_to(False))
        assert_that(interface.port_mode, equal_to(ACCESS))
        assert_that(interface.access_vlan, equal_to(None))
        assert_that(interface.trunk_native_vlan, equal_to(None))
        assert_that(interface.trunk_vlans, equal_to([]))
        assert_that(interface.auto_negotiation, equal_to(None))
        assert_that(interface.mtu, equal_to(None))

    def test_get_unconfigured_but_existing_interface_returns_an_empty_interface(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                    <filter>
                      <configuration>
                          <interfaces>
                            <interface>
                              <name>ge-0/0/27</name>
                            </interface>
                          </interfaces>
                        <vlans />
                      </configuration>
                    </filter>
                """)).and_return(a_configuration("""
                    <interfaces/>
                    <vlans/>
                """))
        self.netconf_mock.should_receive("rpc").with_args(is_xml("""
                    <get-interface-information>
                      <terse/>
                    </get-interface-information>
                """)).and_return(an_rpc_response(textwrap.dedent("""
                    <interface-information style="terse">
                      <physical-interface>
                        <name>
                    ge-0/0/27
                    </name>
                        <admin-status>
                    up
                    </admin-status>
                        <oper-status>
                    down
                    </oper-status>
                      </physical-interface>
                    </interface-information>
                """)))

        interface = self.switch.get_interface('ge-0/0/27')

        assert_that(interface.name, equal_to("ge-0/0/27"))
        assert_that(interface.shutdown, equal_to(False))
        assert_that(interface.port_mode, equal_to(ACCESS))
        assert_that(interface.access_vlan, equal_to(None))
        assert_that(interface.trunk_native_vlan, equal_to(None))
        assert_that(interface.trunk_vlans, equal_to([]))

    def test_get_unconfigured_interface_could_be_disabled(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                    <filter>
                      <configuration>
                          <interfaces>
                            <interface>
                              <name>ge-0/0/27</name>
                            </interface>
                          </interfaces>
                        <vlans />
                      </configuration>
                    </filter>
                """)).and_return(a_configuration("""
                    <interfaces/>
                    <vlans/>
                """))
        self.netconf_mock.should_receive("rpc").with_args(is_xml("""
                    <get-interface-information>
                      <terse/>
                    </get-interface-information>
                """)).and_return(an_rpc_response(textwrap.dedent("""
                    <interface-information style="terse">
                      <physical-interface>
                        <name>
                    ge-0/0/27
                    </name>
                        <admin-status>
                    down
                    </admin-status>
                        <oper-status>
                    down
                    </oper-status>
                      </physical-interface>
                    </interface-information>
                """)))

        assert_that(self.switch.get_interface('ge-0/0/27').shutdown, equal_to(True))

    def test_get_nonexistent_interface_raises(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                    <filter>
                      <configuration>
                          <interfaces>
                            <interface>
                              <name>ge-0/0/INEXISTENT</name>
                            </interface>
                          </interfaces>
                        <vlans />
                      </configuration>
                    </filter>
                """)).and_return(a_configuration("""
                    <interfaces/>
                    <vlans/>
                """))
        self.netconf_mock.should_receive("rpc").with_args(is_xml("""
                    <get-interface-information>
                      <terse/>
                    </get-interface-information>
                """)).and_return(an_rpc_response(textwrap.dedent("""
                    <interface-information style="terse">
                      <physical-interface>
                        <name>
                    ge-0/0/1
                    </name>
                        <admin-status>
                    down
                    </admin-status>
                        <oper-status>
                    down
                    </oper-status>
                      </physical-interface>
                    </interface-information>
                """)))

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.get_interface('ge-0/0/INEXISTENT')

        assert_that(str(expect.exception), equal_to("Unknown interface ge-0/0/INEXISTENT"))

    def test_get_interfaces(self):
        self.switch.in_transaction = False

        self.netconf_mock.should_receive("rpc").with_args(is_xml("""
                    <get-interface-information>
                      <terse/>
                    </get-interface-information>
                """)).and_return(an_rpc_response(textwrap.dedent("""
                    <interface-information style="terse">
                      <physical-interface>
                        <name>
                    ge-0/0/1
                    </name>
                        <admin-status>
                    up
                    </admin-status>
                        <oper-status>
                    down
                    </oper-status>
                        <logical-interface>
                          <name>
                    ge-0/0/1.0
                    </name>
                          <admin-status>
                    up
                    </admin-status>
                          <oper-status>
                    down
                    </oper-status>
                          <filter-information>
                          </filter-information>
                          <address-family>
                            <address-family-name>
                    eth-switch
                    </address-family-name>
                          </address-family>
                        </logical-interface>
                      </physical-interface>
                      <physical-interface>
                        <name>
                    ge-0/0/2
                    </name>
                        <admin-status>
                    down
                    </admin-status>
                        <oper-status>
                    down
                    </oper-status>
                        <logical-interface>
                          <name>
                    ge-0/0/2.0
                    </name>
                          <admin-status>
                    up
                    </admin-status>
                          <oper-status>
                    down
                    </oper-status>
                          <filter-information>
                          </filter-information>
                          <address-family>
                            <address-family-name>
                    eth-switch
                    </address-family-name>
                          </address-family>
                        </logical-interface>
                      </physical-interface>
                      <physical-interface>
                        <name>
                    ge-0/0/3
                    </name>
                        <admin-status>
                    up
                    </admin-status>
                        <oper-status>
                    down
                    </oper-status>
                        <logical-interface>
                          <name>
                    ge-0/0/3.0
                    </name>
                          <admin-status>
                    up
                    </admin-status>
                          <oper-status>
                    down
                    </oper-status>
                          <filter-information>
                          </filter-information>
                          <address-family>
                            <address-family-name>
                    eth-switch
                    </address-family-name>
                          </address-family>
                        </logical-interface>
                      </physical-interface>
                      <physical-interface>
                        <name>
                    ge-0/0/4
                    </name>
                        <admin-status>up</admin-status>
                        <oper-status>down</oper-status>
                        <logical-interface>
                          <name>
                    ge-0/0/4.0
                    </name>
                          <admin-status>
                    up
                    </admin-status>
                          <oper-status>
                    down
                    </oper-status>
                          <filter-information>
                          </filter-information>
                          <address-family>
                            <address-family-name>
                    eth-switch
                    </address-family-name>
                          </address-family>
                        </logical-interface>
                      </physical-interface>
                      <physical-interface>
                        <name>
                    ge-0/0/5
                    </name>
                        <admin-status>
                    up
                    </admin-status>
                        <oper-status>
                    down
                    </oper-status>
                      </physical-interface>
                    </interface-information>
                """)))

        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces />
                <vlans />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/1</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-0/0/2</name>
                <disable />
                <description>Howdy</description>
                <mtu>5000</mtu>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <vlan>
                        <members>1000</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-0/0/3</name>
                <ether-options>
                  <no-auto-negotiation/>
                </ether-options>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>999-1001</members>
                        <members>1000</members>
                      </vlan>
                      <native-vlan-id>2000</native-vlan-id>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-0/0/4</name>
                <ether-options>
                  <auto-negotiation/>
                </ether-options>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-0/0/5</name>
                <ether-options>
                  <speed>
                    <ethernet-100m/>
                  </speed>
                  <ieee-802.3ad>
                    <bundle>ae10</bundle>
                  </ieee-802.3ad>
                </ether-options>
              </interface>
              <interface>
                <name>vlan</name>
                <unit>
                  <name>40</name>
                </unit>
              </interface>
              <interface>
                <name>ae10</name>
                <aggregated-ether-options>
                  <lacp>
                    <active/>
                    <periodic>slow</periodic>
                  </lacp>
                </aggregated-ether-options>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching />
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        if1, if2, if3, if4, if5 = self.switch.get_interfaces()

        assert_that(if1.name, equal_to("ge-0/0/1"))
        assert_that(if1.shutdown, equal_to(False))
        assert_that(if1.port_mode, equal_to(ACCESS))
        assert_that(if1.access_vlan, equal_to(None))
        assert_that(if1.trunk_native_vlan, equal_to(None))
        assert_that(if1.trunk_vlans, equal_to([]))
        assert_that(if1.auto_negotiation, equal_to(None))
        assert_that(if1.mtu, equal_to(None))

        assert_that(if2.name, equal_to("ge-0/0/2"))
        assert_that(if2.shutdown, equal_to(True))
        assert_that(if2.port_mode, equal_to(ACCESS))
        assert_that(if2.access_vlan, equal_to(1000))
        assert_that(if2.trunk_native_vlan, equal_to(None))
        assert_that(if2.trunk_vlans, equal_to([]))
        assert_that(if2.mtu, equal_to(5000))

        assert_that(if3.name, equal_to("ge-0/0/3"))
        assert_that(if3.port_mode, equal_to(TRUNK))
        assert_that(if3.access_vlan, equal_to(None))
        assert_that(if3.trunk_native_vlan, equal_to(2000))
        assert_that(if3.trunk_vlans, equal_to([999, 1000, 1001]))
        assert_that(if3.auto_negotiation, equal_to(False))

        assert_that(if4.name, equal_to("ge-0/0/4"))
        assert_that(if4.trunk_native_vlan, equal_to(None))
        assert_that(if4.trunk_vlans, equal_to([]))
        assert_that(if4.auto_negotiation, equal_to(True))

        assert_that(if5.name, equal_to("ge-0/0/5"))
        assert_that(if5.port_mode, equal_to(BOND_MEMBER))
        assert_that(if5.bond_master, equal_to(10))

    def test_get_interfaces_lists_configuration_less_interfaces(self):
        self.switch.in_transaction = False

        self.netconf_mock.should_receive("rpc").with_args(is_xml("""
                    <get-interface-information>
                      <terse/>
                    </get-interface-information>
                """)).and_return(an_rpc_response(textwrap.dedent("""
                    <interface-information style="terse">
                      <physical-interface>
                        <name>
                    ge-0/0/1
                    </name>
                        <admin-status>
                    up
                    </admin-status>
                        <oper-status>
                    down
                    </oper-status>
                      </physical-interface>
                      <physical-interface>
                        <name>
                    ge-0/0/2
                    </name>
                        <admin-status>
                    down
                    </admin-status>
                        <oper-status>
                    down
                    </oper-status>
                      </physical-interface>
                    </interface-information>
                """)))

        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces />
                <vlans />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces />
            <vlans/>
        """))

        if1, if2 = self.switch.get_interfaces()

        assert_that(if1.name, equal_to("ge-0/0/1"))
        assert_that(if1.shutdown, equal_to(False))
        assert_that(if1.port_mode, equal_to(ACCESS))
        assert_that(if1.access_vlan, equal_to(None))
        assert_that(if1.trunk_native_vlan, equal_to(None))
        assert_that(if1.trunk_vlans, equal_to([]))

        assert_that(if2.name, equal_to("ge-0/0/2"))
        assert_that(if2.shutdown, equal_to(True))

    def test_get_interfaces_supports_named_vlans(self):
        self.switch.in_transaction = True

        self.netconf_mock.should_receive("rpc").with_args(is_xml("""
                    <get-interface-information>
                      <terse/>
                    </get-interface-information>
                """)).and_return(an_rpc_response(textwrap.dedent("""
                    <interface-information style="terse">
                      <physical-interface>
                        <name>
                    ge-0/0/1
                    </name>
                        <admin-status>
                    up
                    </admin-status>
                        <oper-status>
                    down
                    </oper-status>
                        <logical-interface>
                          <name>
                    ge-0/0/1.0
                    </name>
                          <admin-status>
                    up
                    </admin-status>
                          <oper-status>
                    down
                    </oper-status>
                          <filter-information>
                          </filter-information>
                          <address-family>
                            <address-family-name>
                    eth-switch
                    </address-family-name>
                          </address-family>
                        </logical-interface>
                      </physical-interface>
                    </interface-information>
                """)))

        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces />
                <vlans />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>MON_VLAN_PREFERE</name>
                <vlan-id>1234</vlan-id>
                <description>Oh yeah</description>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/1</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <vlan>
                        <members>MON_VLAN_PREFERE</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))
        if1, = self.switch.get_interfaces()

        assert_that(if1.name, equal_to("ge-0/0/1"))
        assert_that(if1.access_vlan, equal_to(1234))

    def test_add_vlan(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>900</vlan-id>
              </vlan>
            </vlans>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <vlans>
                  <vlan>
                    <name>VLAN1000</name>
                    <vlan-id>1000</vlan-id>
                    <description>Shizzle</description>
                  </vlan>
                </vlans>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.add_vlan(1000, name="Shizzle")

    def test_add_vlan_already_in_use_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(VlanAlreadyExist) as expect:
            self.switch.add_vlan(1000)

        assert_that(str(expect.exception), contains_string("Vlan 1000 already exist"))

    def test_add_existing_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>VLAN1000</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(VlanAlreadyExist) as expect:
            self.switch.add_vlan(1000)

        assert_that(str(expect.exception), contains_string("Vlan 1000 already exist"))

    def test_add_vlan_bad_vlan_id(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
              </configuration>
            </filter>
        """)).and_return(a_configuration(""))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <vlans>
                  <vlan>
                    <name>VLAN9000</name>
                    <vlan-id>9000</vlan-id>
                  </vlan>
                </vlans>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-info>
            <bad-element>9000</bad-element>
            </error-info>
            <error-message>Value 9000 is not within range (1..4094)</error-message>
            </rpc-error>
        """))))

        with self.assertRaises(BadVlanNumber) as expect:
            self.switch.add_vlan(9000)

        assert_that(str(expect.exception), equal_to("Vlan number is invalid"))

    def test_add_vlan_bad_vlan_name(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
              </configuration>
            </filter>
        """)).and_return(a_configuration(""))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <vlans>
                  <vlan>
                    <name>VLAN1000</name>
                    <vlan-id>1000</vlan-id>
                    <description>a</description>
                  </vlan>
                </vlans>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-info>
            <bad-element>a</bad-element>
            </error-info>
            <error-message>Length 1 is not within range (2..255)</error-message>
            </rpc-error>
        """))))

        with self.assertRaises(BadVlanName) as expect:
            self.switch.add_vlan(1000, "a")

        assert_that(str(expect.exception), equal_to("Vlan name is invalid"))

    def test_remove_vlan_also_removes_associated_vlan_interface(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>MEH</name>
                <vlan-id>5</vlan-id>
              </vlan>
              <vlan>
                <name>STANDARD</name>
                <vlan-id>10</vlan-id>
                <l3-interface>vlan.25</l3-interface>
              </vlan>
              <vlan>
                <name>MEH2</name>
                <vlan-id>15</vlan-id>
              </vlan>
            </vlans>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <vlans>
                  <vlan operation="delete">
                    <name>STANDARD</name>
                  </vlan>
                </vlans>
                <interfaces>
                  <interface>
                    <name>vlan</name>
                    <unit operation="delete">
                      <name>25</name>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.remove_vlan(10)

    def test_remove_vlan_also_removes_associated_vlan_interface_even_if_non_standard_name(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>MEH</name>
                <vlan-id>5</vlan-id>
              </vlan>
              <vlan>
                <name>STANDARD</name>
                <vlan-id>10</vlan-id>
                <l3-interface>irb.25</l3-interface>
              </vlan>
              <vlan>
                <name>MEH2</name>
                <vlan-id>15</vlan-id>
              </vlan>
            </vlans>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <vlans>
                  <vlan operation="delete">
                    <name>STANDARD</name>
                  </vlan>
                </vlans>
                <interfaces>
                  <interface>
                    <name>irb</name>
                    <unit operation="delete">
                      <name>25</name>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.remove_vlan(10)

    def test_remove_vlan_ignores_removing_interface_not_created(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>STANDARD</name>
                <vlan-id>10</vlan-id>
              </vlan>
            </vlans>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <vlans>
                  <vlan operation="delete">
                    <name>STANDARD</name>
                  </vlan>
                </vlans>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.remove_vlan(10)

    def test_remove_vlan_invalid_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>ANOTHER</name>
                <vlan-id>10</vlan-id>
              </vlan>
            </vlans>
        """))

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vlan(20)

        assert_that(str(expect.exception), equal_to("Vlan 20 not found"))

    def test_remove_vlan_in_use_deletes_all_usages(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>STANDARD</name>
                <vlan-id>10</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/1</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>9</members>
                        <members>10</members>
                        <members>11</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-0/0/2</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>9-15</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-0/0/3</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>access</port-mode>
                      <vlan>
                        <members>12</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-0/0/4</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>access</port-mode>
                      <vlan>
                        <members>STANDARD</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-0/0/5</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>access</port-mode>
                      <vlan>
                        <members>ANOTHER_NAME</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <vlans>
                  <vlan operation="delete">
                    <name>STANDARD</name>
                  </vlan>
                </vlans>
                <interfaces>
                  <interface>
                    <name>ge-0/0/1</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <vlan>
                            <members operation="delete">10</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                  <interface>
                    <name>ge-0/0/2</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <vlan>
                            <members operation="delete">9-15</members>
                            <members>9</members>
                            <members>11-15</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                  <interface>
                    <name>ge-0/0/4</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <vlan>
                            <members operation="delete">STANDARD</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.remove_vlan(10)

    def test_remove_vlan_delete_usage_and_interface_at_same_time(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <vlans />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>STANDARD</name>
                <vlan-id>10</vlan-id>
                <l3-interface>vlan.10</l3-interface>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>name</name>
                <unit>
                  <name>10</name>
                  <family>
                    <inet>
                      <address>
                        <name>1.1.1.1/24</name>
                      </address>
                    </inet>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-0/0/1</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>10</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <vlans>
                  <vlan operation="delete">
                    <name>STANDARD</name>
                  </vlan>
                </vlans>
                <interfaces>
                  <interface>
                    <name>vlan</name>
                    <unit operation="delete">
                      <name>10</name>
                    </unit>
                  </interface>
                  <interface>
                    <name>ge-0/0/1</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <vlan>
                            <members operation="delete">10</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.remove_vlan(10)

    def test_port_mode_access_with_no_port_mode_or_vlan_set_just_sets_the_port_mode(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>access</port-mode>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_mode("ge-0/0/6")

    def test_port_mode_access_with_no_mode_and_1_vlan_does_not_remove_it(self):

        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <vlan>
                        <members>2998</members>
                        <members>2998</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>access</port-mode>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_mode("ge-0/0/6")

    def test_port_mode_access_with_trunk_mode_and_1_vlan_does_remove_it(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>2998</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>access</port-mode>
                          <vlan operation="delete" />
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_mode("ge-0/0/6")

    def test_port_mode_access_with_trunk_mode_and_no_attributes_just_sets_mode(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>access</port-mode>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_mode("ge-0/0/6")

    def test_port_mode_access_already_in_access_mode_does_nothing(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>access</port-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        self.switch.set_access_mode("ge-0/0/6")

    def test_port_mode_access_on_unknown_interface_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces/>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>access</port-mode>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            port value outside range 0..63 for '99' in 'ge-0/0/99'
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_mode("ge-0/0/99")

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/99"))

    def test_port_mode_access_on_default_interface_works(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces/>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>access</port-mode>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_mode("ge-0/0/6")

    def test_port_mode_access_with_trunk_mode_wipes_all_trunk_stuff(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>123</members>
                        <members>456</members>
                      </vlan>
                      <native-vlan-id>999</native-vlan-id>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>access</port-mode>
                          <vlan operation="delete" />
                          <native-vlan-id operation="delete" />
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_mode("ge-0/0/6")

    def test_port_mode_trunk_with_no_port_mode_or_vlan_set_just_sets_the_port_mode(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>trunk</port-mode>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_trunk_mode("ge-0/0/6")

    def test_port_mode_trunk_with_no_port_mode_and_1_vlan_removes_it(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <vlan>
                        <members>1000</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>trunk</port-mode>
                          <vlan operation="delete" />
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_trunk_mode("ge-0/0/6")

    def test_port_mode_trunk_with_access_port_mode_and_1_vlan_removes_it(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>access</port-mode>
                      <vlan>
                        <members>1000</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>trunk</port-mode>
                          <vlan operation="delete" />
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_trunk_mode("ge-0/0/6")

    def test_port_mode_trunk_already_in_trunk_mode_does_nothing(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>1000</members>
                        <members>1001</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        self.switch.set_trunk_mode("ge-0/0/6")

    def test_port_mode_trunk_on_unknown_interface_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                  </interface>
                </interfaces>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration())

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>trunk</port-mode>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(a_port_value_outside_range_rpc_error())

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_trunk_mode("ge-0/0/99")

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/99"))

    def test_port_mode_trunk_on_default_interface_works(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration())

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>trunk</port-mode>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_trunk_mode("ge-0/0/6")

    def test_set_access_vlan_on_interface_with_access_mode_and_no_vlan_succeeds_easily(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>access</port-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <vlan>
                            <members>1000</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_vlan("ge-0/0/6", 1000)

    def test_set_access_vlan_on_interface_that_already_has_it_does_nothing(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>access</port-mode>
                        <vlan>
                          <members>1000</members>
                        </vlan>
                      </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        self.switch.set_access_vlan("ge-0/0/6", 1000)

    def test_set_access_vlan_on_interface_that_has_no_port_mode_sets_it(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>access</port-mode>
                          <vlan>
                            <members>1000</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_vlan("ge-0/0/6", 1000)

    def test_set_access_vlan_on_interface_replaces_the_actual_ones(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
              <vlan>
                <name>PATATE2</name>
                <vlan-id>2000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <vlan>
                        <members>2000</members>
                        <members>2000-2000</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>access</port-mode>
                          <vlan>
                            <members operation="delete">2000</members>
                            <members operation="delete">2000-2000</members>
                            <members>1000</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_vlan("ge-0/0/6", 1000)

    def test_set_access_vlan_on_interface_in_trunk_mode_should_raise(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.set_access_vlan("ge-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Operation cannot be performed on a trunk mode interface"))

    def test_set_access_vlan_on_unknown_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>3333</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>access</port-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_access_vlan("ge-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Vlan 1000 not found"))

    def test_set_access_vlan_on_default_interface_works(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>access</port-mode>
                          <vlan>
                            <members>1000</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_vlan("ge-0/0/6", 1000)

    def test_set_access_vlan_on_unknown_interface_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>access</port-mode>
                          <vlan>
                            <members>1000</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(a_port_value_outside_range_rpc_error())

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_access_vlan("ge-0/0/99", 1000)

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/99"))

    def test_reset_interface_works(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface operation="delete">
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.reset_interface('ge-0/0/6')

    def test_reset_port_value_outside_range_interface_raises_unknown_interface(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface operation="delete">
                    <name>ge-0/0/99</name>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            port value outside range 0..63 for '99' in 'ge-0/0/99'
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.reset_interface("ge-0/0/99")

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/99"))

    def test_reset_interface_with_invalid_interface_raises(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface operation="delete">
                    <name>ne-0/0/9</name>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            invalid interface type in 'ne-0/0/9'
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(UnknownInterface):
            self.switch.reset_interface("ne-0/0/9")

    def test_reset_interface_with_unknown_rpcerror_raises(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface operation="delete">
                    <name>ne-0/0/9</name>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            Unknown error
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(RPCError) as expect:
            self.switch.reset_interface("ne-0/0/9")

        assert_that(str(expect.exception), contains_string("Unknown error"))

    def test_unset_interface_access_vlan_removes_the_vlan_members(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <vlan>
                        <members>1000</members>
                        <members>1000-1000</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <vlan operation="delete" />
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.unset_interface_access_vlan("ge-0/0/6")

    def test_unset_interface_access_vlan_with_no_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(AccessVlanNotSet) as expect:
            self.switch.unset_interface_access_vlan("ge-0/0/6")

        assert_that(str(expect.exception), contains_string("Access Vlan is not set on interface ge-0/0/6"))

    def test_unset_interface_access_vlan_on_trunk_mode_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>123</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.unset_interface_access_vlan("ge-0/0/6")

        assert_that(str(expect.exception), contains_string("Operation cannot be performed on a trunk mode interface"))

    def test_unset_interface_access_vlan_on_default_interface_works(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration(""))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(AccessVlanNotSet):
            self.switch.unset_interface_access_vlan("ge-0/0/6")

    def test_set_interface_native_vlan_on_interface_with_trunk_mode_and_no_native_vlan_succeeds_easily(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <native-vlan-id>1000</native-vlan-id>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_interface_native_vlan("ge-0/0/6", 1000)

    def test_set_interface_native_vlan_on_interface_that_already_has_it_does_nothing(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <native-vlan-id>1000</native-vlan-id>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        self.switch.set_interface_native_vlan("ge-0/0/6", 1000)

    def test_set_interface_native_vlan_on_interface_that_has_no_port_mode_sets_it(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>trunk</port-mode>
                          <native-vlan-id>1000</native-vlan-id>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_interface_native_vlan("ge-0/0/6", 1000)

    def test_set_interface_native_vlan_on_interface_replaces_the_actual_ones(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
              <vlan>
                <name>PATATE2</name>
                <vlan-id>2000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <native-vlan-id>2000</native-vlan-id>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <native-vlan-id>1000</native-vlan-id>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_interface_native_vlan("ge-0/0/6", 1000)

    def test_set_interface_native_vlan_on_interface_in_access_mode_should_raise(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>access</port-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.set_interface_native_vlan("ge-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Operation cannot be performed on a access mode interface"))

    def test_set_interface_native_vlan_on_interface_that_is_already_a_member_of_the_trunk_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE0</name>
                <vlan-id>999</vlan-id>
              </vlan>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
              <vlan>
                <name>PATATE2</name>
                <vlan-id>1001</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>999-1001</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(VlanAlreadyInTrunk) as expect:
            self.switch.set_interface_native_vlan("ge-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Vlan 1000 cannot be set as native vlan because it is already a member of the trunk"))

    def test_set_interface_native_vlan_on_unknown_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>3333</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_interface_native_vlan("ge-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Vlan 1000 not found"))

    def test_set_interface_native_vlan_on_unknown_interface_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
                <filter>
                  <configuration>
                    <interfaces/>
                    <vlans/>
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <vlans>
                  <vlan>
                    <name>PATATE</name>
                    <vlan-id>1000</vlan-id>
                  </vlan>
                </vlans>
            """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>trunk</port-mode>
                          <native-vlan-id>1000</native-vlan-id>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(a_port_value_outside_range_rpc_error())

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_interface_native_vlan("ge-0/0/99", 1000)

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/99"))

    def test_set_interface_native_vlan_on_default_interface_works(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
                <filter>
                  <configuration>
                    <interfaces/>
                    <vlans/>
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <vlans>
                  <vlan>
                    <name>PATATE</name>
                    <vlan-id>1000</vlan-id>
                  </vlan>
                </vlans>
            """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>trunk</port-mode>
                          <native-vlan-id>1000</native-vlan-id>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_interface_native_vlan("ge-0/0/6", 1000)

    def test_unset_interface_native_vlan_succeeds(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <native-vlan-id>1000</native-vlan-id>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <native-vlan-id operation="delete" />
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.unset_interface_native_vlan("ge-0/0/6")

    def test_unset_interface_native_vlan_when_none_is_set_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(NativeVlanNotSet) as expect:
            self.switch.unset_interface_native_vlan("ge-0/0/6")

        assert_that(str(expect.exception), contains_string("Trunk native Vlan is not set on interface ge-0/0/6"))

    def test_unset_interface_native_vlan_on_default_interface_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration(""))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(NativeVlanNotSet):
            self.switch.unset_interface_native_vlan("ge-0/0/6")

    def test_set_interface_auto_negotiation_state_ON_works(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
                <config>
                  <configuration>
                    <interfaces>
                      <interface>
                        <name>ge-0/0/6</name>
                        <ether-options>
                          <auto-negotiation/>
                        </ether-options>
                      </interface>
                    </interfaces>
                  </configuration>
                </config>
            """)).and_return(an_ok_response())

        self.switch.set_interface_auto_negotiation_state("ge-0/0/6", ON)

    def test_set_interface_auto_negotiation_state_OFF_works(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
                <config>
                  <configuration>
                    <interfaces>
                      <interface>
                        <name>ge-0/0/6</name>
                        <ether-options>
                          <no-auto-negotiation/>
                        </ether-options>
                      </interface>
                    </interfaces>
                  </configuration>
                </config>
            """)).and_return(an_ok_response())

        self.switch.set_interface_auto_negotiation_state("ge-0/0/6", OFF)

    def test_set_interface_auto_negotiation_raises_on_unknown_interface(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
                <config>
                  <configuration>
                    <interfaces>
                      <interface>
                        <name>ge-0/0/128</name>
                        <ether-options>
                          <no-auto-negotiation/>
                        </ether-options>
                      </interface>
                    </interfaces>
                  </configuration>
                </config>
            """)).and_raise(a_port_value_outside_range_rpc_error())

        with self.assertRaises(UnknownInterface):
            self.switch.set_interface_auto_negotiation_state("ge-0/0/128", OFF)

    def test_unset_interface_auto_negotiation_state_works_when_enabled(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
                <filter>
                  <configuration>
                    <interfaces>
                      <interface>
                        <name>ge-0/0/6</name>
                      </interface>
                    </interfaces>
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <ether-options>
                      <auto-negotiation/>
                    </ether-options>
                  </interface>
                </interfaces>
            """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
                <config>
                  <configuration>
                    <interfaces>
                      <interface>
                        <name>ge-0/0/6</name>
                        <ether-options>
                          <auto-negotiation operation=\"delete\" />
                        </ether-options>
                      </interface>
                    </interfaces>
                  </configuration>
                </config>
            """)).and_return(an_ok_response())

        self.switch.unset_interface_auto_negotiation_state("ge-0/0/6")

    def test_unset_interface_auto_negotiation_state_does_nothing_on_default_interface(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
                <filter>
                  <configuration>
                    <interfaces>
                      <interface>
                        <name>ge-0/0/6</name>
                      </interface>
                    </interfaces>
                  </configuration>
                </filter>
            """)).and_return(a_configuration(""))

        self.netconf_mock.should_receive("rpc").with_args(is_xml("""
            <get-interface-information>
              <terse/>
            </get-interface-information>
        """)).and_return(an_rpc_response(textwrap.dedent("""
            <interface-information style="terse">
              <physical-interface>
                <name>
            ge-0/0/6
            </name>
                <admin-status>
            up
            </admin-status>
                <oper-status>
            down
            </oper-status>
              </physical-interface>
            </interface-information>
        """)))

        self.switch.unset_interface_auto_negotiation_state("ge-0/0/6")

    def test_unset_interface_auto_negotiation_state_works_when_disabled(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
                <filter>
                  <configuration>
                    <interfaces>
                      <interface>
                        <name>ge-0/0/6</name>
                      </interface>
                    </interfaces>
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <ether-options>
                      <no-auto-negotiation/>
                    </ether-options>
                  </interface>
                </interfaces>
            """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
                <config>
                  <configuration>
                    <interfaces>
                      <interface>
                        <name>ge-0/0/6</name>
                        <ether-options>
                          <no-auto-negotiation operation=\"delete\" />
                        </ether-options>
                      </interface>
                    </interfaces>
                  </configuration>
                </config>
            """)).and_return(an_ok_response())

        self.switch.unset_interface_auto_negotiation_state("ge-0/0/6")

    def test_unset_interface_auto_negotiation_state_raises_on_unknown_interface(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
                <filter>
                  <configuration>
                    <interfaces>
                      <interface>
                        <name>ge-0/0/99</name>
                      </interface>
                    </interfaces>
                  </configuration>
                </filter>
            """)).and_return(a_configuration(""))

        self.netconf_mock.should_receive("rpc").with_args(is_xml("""
            <get-interface-information>
              <terse/>
            </get-interface-information>
        """)).and_return(an_rpc_response(textwrap.dedent("""
            <interface-information style="terse">
              <physical-interface>
                <name>
            ge-0/0/6
            </name>
                <admin-status>
            up
            </admin-status>
                <oper-status>
            down
            </oper-status>
              </physical-interface>
            </interface-information>
        """)))

        with self.assertRaises(UnknownInterface):
            self.switch.unset_interface_auto_negotiation_state("ge-0/0/99")

    def test_add_trunk_vlan_on_interface_with_trunk_mode_and_no_vlan_succeeds_easily(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <vlan>
                            <members>1000</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.add_trunk_vlan("ge-0/0/6", 1000)

    def test_add_trunk_vlan_on_interface_that_already_has_it_does_nothing(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                        <vlan>
                          <members>900-1100</members>
                        </vlan>
                      </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        self.switch.add_trunk_vlan("ge-0/0/6", 1000)

    def test_add_trunk_vlan_on_interface_that_has_no_port_mode_and_no_vlan_sets_it(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>trunk</port-mode>
                          <vlan>
                            <members>1000</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.add_trunk_vlan("ge-0/0/6", 1000)

    def test_add_trunk_vlan_on_interface_adds_to_the_list(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>2000</members>
                        <members>2100-2200</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <vlan>
                            <members>1000</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.add_trunk_vlan("ge-0/0/6", 1000)

    def test_add_trunk_vlan_on_interface_that_has_no_port_mode_with_a_vlan_assumes_access_mode_and_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <vlan>
                        <members>500</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.add_trunk_vlan("ge-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Operation cannot be performed on a access mode interface"))

    def test_add_trunk_vlan_on_interface_in_access_mode_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>access</port-mode>
                      <vlan>
                        <members>500</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.add_trunk_vlan("ge-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Operation cannot be performed on a access mode interface"))

    def test_add_trunk_vlan_on_unknown_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_trunk_vlan("ge-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Vlan 1000 not found"))

    def test_add_trunk_vlan_on_unknown_interface_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
             <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <port-mode>trunk</port-mode>
                          <vlan>
                            <members>1000</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(a_port_value_outside_range_rpc_error())

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.add_trunk_vlan("ge-0/0/99", 1000)

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/99"))

    def test_remove_trunk_vlan_removes_the_vlan_members_in_every_possible_way(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>VLAN_NAME</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>1000</members>
                        <members>1000-1001</members>
                        <members>999-1000</members>
                        <members>999-1001</members>
                        <members>998-1002</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <vlan>
                            <members operation="delete">1000</members>
                            <members operation="delete">1000-1001</members>
                            <members>1001</members>
                            <members operation="delete">999-1000</members>
                            <members>999</members>
                            <members operation="delete">999-1001</members>
                            <members>999</members>
                            <members>1001</members>
                            <members operation="delete">998-1002</members>
                            <members>998-999</members>
                            <members>1001-1002</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.remove_trunk_vlan("ge-0/0/6", 1000)

    def test_remove_trunk_vlan_removes_the_vlan_even_if_referenced_by_name(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>VLAN_NAME</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>1000</members>
                        <members>VLAN_NAME</members>
                        <members>SOEMTHING</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <ethernet-switching>
                          <vlan>
                            <members operation="delete">1000</members>
                            <members operation="delete">VLAN_NAME</members>
                          </vlan>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.remove_trunk_vlan("ge-0/0/6", 1000)

    def test_remove_trunk_vlan_not_in_members_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>VLAN_NAME</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>500-999</members>
                        <members>1001-4000</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(TrunkVlanNotSet) as expect:
            self.switch.remove_trunk_vlan("ge-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Trunk Vlan is not set on interface ge-0/0/6"))

    def test_remove_trunk_vlan_on_access_with_the_correct_vlan_interface_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>VLAN_NAME</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>access</port-mode>
                      <vlan>
                        <members>1000</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.remove_trunk_vlan("ge-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Operation cannot be performed on a access mode interface"))

    def test_remove_trunk_vlan_on_no_port_mode_interface_with_the_correct_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>VLAN_NAME</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <vlan>
                        <members>1000</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.remove_trunk_vlan("ge-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Operation cannot be performed on a access mode interface"))

    def test_remove_trunk_vlan_on_unknown_interface_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <vlans>
              <vlan>
                <name>VLAN_NAME</name>
                <vlan-id>1000</vlan-id>
              </vlan>
            </vlans>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_trunk_vlan("ge-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/6"))

    def test_set_interface_description_succeeds(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <description>Resistance is futile</description>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_interface_description("ge-0/0/6", "Resistance is futile")

    def test_set_interface_description_on_unkown_interface_raises(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                    <description>Resistance is futile</description>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            port value outside range 0..47 for '99' in 'ge-0/0/99'
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_interface_description("ge-0/0/99", "Resistance is futile")

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/99"))

    def test_unset_interface_description_succeeds(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <description operation="delete" />
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.unset_interface_description("ge-0/0/6")

    def test_unset_interface_description_on_unkown_interface_raises(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                    <description operation="delete" />
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            port value outside range 0..47 for '99' in 'ge-0/0/99'
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.unset_interface_description("ge-0/0/99")

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/99"))

    def test_unset_interface_description_on_interface_with_no_description_just_ignores_it(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                    <description operation="delete" />
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>warning</error-severity>
            <error-path>[edit interfaces ge-0/0/6]</error-path>
            <error-message>statement not found: description</error-message>
            </rpc-error>"""))))

        self.switch.unset_interface_description("ge-0/0/99")

    def test_edit_interface_spanning_tree_enable_edge_from_nothing(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6.0</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
              </interface>
            </interfaces>
            <protocols>
              <rstp>
                <interface>
                  <name>ge-0/0/6.0</name>
                </interface>
              </rstp>
            </protocols>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6</name>
                      <edge />
                      <no-root-port />
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.edit_interface_spanning_tree('ge-0/0/6', edge=True)

    def test_edit_interface_spanning_tree_enable_edge_when_all_is_already_set(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6.0</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
              </interface>
            </interfaces>
            <protocols>
              <rstp>
                <interface>
                  <name>ge-0/0/6.0</name>
                  <edge/>
                  <no-root-port/>
                </interface>
              </rstp>
            </protocols>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        self.switch.edit_interface_spanning_tree('ge-0/0/6', edge=True)

    def test_edit_interface_spanning_tree_enable_edge_when_only_edge_is_already_set(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6.0</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
              </interface>
            </interfaces>
            <protocols>
              <rstp>
                <interface>
                  <name>ge-0/0/6.0</name>
                  <edge/>
                </interface>
              </rstp>
            </protocols>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6</name>
                      <no-root-port />
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.edit_interface_spanning_tree('ge-0/0/6', edge=True)

    def test_edit_interface_spanning_tree_enable_edge_when_only_no_root_port_is_already_set(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6.0</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
              </interface>
            </interfaces>
            <protocols>
              <rstp>
                <interface>
                  <name>ge-0/0/6.0</name>
                  <no-root-port />
                </interface>
              </rstp>
            </protocols>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6</name>
                      <edge />
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.edit_interface_spanning_tree('ge-0/0/6', edge=True)

    def test_edit_interface_spanning_tree_disable_edge_when_all_is_set(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6.0</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
              </interface>
            </interfaces>
            <protocols>
              <rstp>
                <interface>
                  <name>ge-0/0/6.0</name>
                  <edge/>
                  <no-root-port/>
                </interface>
              </rstp>
            </protocols>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6</name>
                      <edge operation="delete" />
                      <no-root-port operation="delete" />
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.edit_interface_spanning_tree('ge-0/0/6', edge=False)

    def test_edit_interface_spanning_tree_disable_edge_when_all_is_only_edge_is_set(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6.0</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
              </interface>
            </interfaces>
            <protocols>
              <rstp>
                <interface>
                  <name>ge-0/0/6.0</name>
                  <edge/>
                </interface>
              </rstp>
            </protocols>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6</name>
                      <edge operation="delete" />
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.edit_interface_spanning_tree('ge-0/0/6', edge=False)

    def test_edit_interface_spanning_tree_disable_edge_when_all_is_only_no_root_port_is_set(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6.0</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
              </interface>
            </interfaces>
            <protocols>
              <rstp>
                <interface>
                  <name>ge-0/0/6.0</name>
                  <no-root-port />
                </interface>
              </rstp>
            </protocols>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6</name>
                      <no-root-port operation="delete" />
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.edit_interface_spanning_tree('ge-0/0/6', edge=False)

    def test_edit_interface_spanning_tree_disable_edge_when_nothing_is_set(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/6.0</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
              </interface>
            </interfaces>
            <protocols>
              <rstp>
                <interface>
                  <name>ge-0/0/6.0</name>
                </interface>
              </rstp>
            </protocols>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        self.switch.edit_interface_spanning_tree('ge-0/0/6', edge=False)

    def test_edit_interface_spanning_tree_unknown_interface(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                  </interface>
                </interfaces>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/99.0</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration(""))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ge-0/0/99</name>
                      <edge />
                      <no-root-port />
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </config>
            """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            port value outside range 0..47 for '99' in 'ge-0/0/99'
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.edit_interface_spanning_tree('ge-0/0/99', edge=True)

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/99"))

    def test_set_interface_state_to_on_succeeds(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <disable operation="delete" />
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_interface_state("ge-0/0/6", ON)

    def test_set_interface_state_to_off_succeeds(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <disable />
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_interface_state("ge-0/0/6", OFF)

    def test_unset_interface_state_succeeds(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <disable operation="delete" />
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.unset_interface_state("ge-0/0/6")

    def test_unset_interface_state_raises_on_unknown_interface(self):

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                    <disable operation="delete" />
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            port value outside range 0..47 for '99' in 'ge-0/0/99'
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.unset_interface_state("ge-0/0/99")

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/99"))

    def test_unset_interface_state_without_disabled(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <disable operation="delete" />
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>warning</error-severity>
            <error-path>[edit interfaces ge-0/0/6]</error-path>
            <error-message>statement not found: </error-message>
            </rpc-error>"""))))

        self.switch.unset_interface_state("ge-0/0/6")

    def test_set_interface_state_to_on_unknown_interface_raises(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                    <disable operation="delete"/>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            port value outside range 0..47 for '99' in 'ge-0/0/99'
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_interface_state("ge-0/0/99", ON)

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/99"))

    def test_set_interface_state_to_off_unknown_interface_raises(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                    <disable />
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            port value outside range 0..47 for '99' in 'ge-0/0/99'
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_interface_state("ge-0/0/99", OFF)

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/99"))

    def test_add_bond(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ae6</name>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration(""))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ae6</name>
                    <aggregated-ether-options>
                      <lacp>
                        <active/>
                        <periodic>slow</periodic>
                      </lacp>
                    </aggregated-ether-options>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.add_bond(6)

    def test_add_bond_already_created_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ae6</name>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ae6</name>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(BondAlreadyExist) as expect:
            self.switch.add_bond(6)

        assert_that(str(expect.exception), equal_to("Bond 6 already exists"))

    def test_add_bond_bad_bond_number(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ae9000</name>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration(""))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ae9000</name>
                    <aggregated-ether-options>
                      <lacp>
                        <active/>
                        <periodic>slow</periodic>
                      </lacp>
                    </aggregated-ether-options>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            device value outside range 0..31 for '9000' in 'ae9000'
            </error-message>
            </rpc-error>
        """))))

        with self.assertRaises(BadBondNumber) as expect:
            self.switch.add_bond(9000)

        assert_that(str(expect.exception), equal_to("Bond number is invalid"))

    def test_remove_bond(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ae10.0</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ae10</name>
              </interface>
              <interface>
                <name>ge-4/3/3</name>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface operation="delete">
                    <name>ae10</name>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.remove_bond(10)

    def test_remove_bond_also_removes_rstp_protocol(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ae10.0</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ae10</name>
              </interface>
              <interface>
                <name>ge-4/3/3</name>
              </interface>
            </interfaces>
            <protocols>
              <rstp>
                <interface>
                  <name>ae10.0</name>
                  <edge/>
                  <no-root-port/>
                </interface>
              </rstp>
            </protocols>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface operation="delete">
                    <name>ae10</name>
                  </interface>
                </interfaces>
                <protocols>
                  <rstp>
                    <interface operation="delete">
                      <name>ae10</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.remove_bond(10)

    def test_remove_bond_invalid_number_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <protocols>
                  <rstp>
                    <interface>
                      <name>ae7.0</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration())

        with self.assertRaises(UnknownBond) as expect:
            self.switch.remove_bond(007)

        assert_that(str(expect.exception), equal_to("Bond 7 not found"))

    def test_remove_bond_delete_slaves_and_interface_at_same_time(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces />
                <protocols>
                  <rstp>
                    <interface>
                      <name>ae10.0</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ae10</name>
              </interface>
              <interface>
                <name>ge-0/0/1</name>
                <ether-options>
                  <ieee-802.3ad>
                    <bundle>ae10</bundle>
                  </ieee-802.3ad>
                </ether-options>
              </interface>
              <interface>
                <name>ge-0/0/2</name>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface operation="delete">
                    <name>ae10</name>
                  </interface>
                  <interface>
                    <name>ge-0/0/1</name>
                    <ether-options>
                      <ieee-802.3ad operation="delete" />
                    </ether-options>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.remove_bond(10)

    def test_add_interface_to_bond(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
                <protocols>
                  <rstp>
                    <interface />
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ae10</name>
              </interface>
              <interface>
                <name>ge-0/0/1</name>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface operation="replace">
                    <name>ge-0/0/1</name>
                    <ether-options>
                      <ieee-802.3ad>
                        <bundle>ae10</bundle>
                      </ieee-802.3ad>
                    </ether-options>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.add_interface_to_bond('ge-0/0/1', 10)

    def test_add_interface_to_bond_gets_up_to_speed_and_removes_existing_rstp_protocol(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
                <protocols>
                  <rstp>
                    <interface />
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ae10</name>
                <aggregated-ether-options>
                  <link-speed>1g</link-speed>
                </aggregated-ether-options>
              </interface>
              <interface>
                <name>ge-0/0/1</name>
              </interface>
            </interfaces>
            <vlans/>
            <protocols>
              <rstp>
                <interface>
                  <name>ge-0/0/1.0</name>
                  <edge />
                </interface>
              </rstp>
            </protocols>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface operation="replace">
                    <name>ge-0/0/1</name>
                    <ether-options>
                      <ieee-802.3ad>
                        <bundle>ae10</bundle>
                      </ieee-802.3ad>
                      <speed>
                        <ethernet-1g/>
                      </speed>
                    </ether-options>
                  </interface>
                </interfaces>
                <protocols>
                  <rstp>
                    <interface operation="delete">
                      <name>ge-0/0/1</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.add_interface_to_bond('ge-0/0/1', 10)

    def test_add_interface_to_bond_without_bond(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
                <protocols>
                  <rstp>
                    <interface />
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/1</name>
              </interface>
            </interfaces>
            <vlans/>
        """))

        with self.assertRaises(UnknownBond):
            self.switch.add_interface_to_bond('ge-0/0/1', 10)

    def test_add_interface_to_bond_without_interface(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
                <protocols>
                  <rstp>
                    <interface />
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ae10</name>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface operation="replace">
                    <name>ge-0/0/99</name>
                    <ether-options>
                      <ieee-802.3ad>
                        <bundle>ae10</bundle>
                      </ieee-802.3ad>
                    </ether-options>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_raise(
                RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            port value outside range 0..47 for '99' in 'ge-0/0/99'
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(UnknownInterface):
            self.switch.add_interface_to_bond('ge-0/0/99', 10)

    def test_add_interface_to_bond_removing_protocols_avoid_deleting_other_interfaces(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
                <protocols>
                  <rstp>
                    <interface />
                  </rstp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ae10</name>
                <aggregated-ether-options>
                  <link-speed>1g</link-speed>
                </aggregated-ether-options>
              </interface>
              <interface>
                <name>ge-0/0/1</name>
              </interface>
            </interfaces>
            <vlans/>
            <protocols>
              <rstp>
                <interface>
                  <name>ge-0/0/1.0</name>
                  <edge />
                </interface>
                <interface>
                  <name>ge-0/0/10.0</name>
                  <edge />
                </interface>
              </rstp>
            </protocols>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface operation="replace">
                    <name>ge-0/0/1</name>
                    <ether-options>
                      <ieee-802.3ad>
                        <bundle>ae10</bundle>
                      </ieee-802.3ad>
                      <speed>
                        <ethernet-1g/>
                      </speed>
                    </ether-options>
                  </interface>
                </interfaces>
                <protocols>
                  <rstp>
                    <interface operation="delete">
                      <name>ge-0/0/1</name>
                    </interface>
                  </rstp>
                </protocols>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.add_interface_to_bond('ge-0/0/1', 10)

    def test_remove_interface_from_bond(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/1</name>
                    <ether-options>
                      <ieee-802.3ad operation="delete" />
                    </ether-options>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.remove_interface_from_bond('ge-0/0/1')

    def test_remove_interface_from_bond_not_in_bond(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/1</name>
                    <ether-options>
                      <ieee-802.3ad operation="delete" />
                    </ether-options>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_raise(
                RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            statement not found: 802.3ad
            </error-message>
            </rpc-error>"""))))

        self.netconf_mock.should_receive("rpc").with_args(is_xml("""
            <get-interface-information>
              <terse/>
            </get-interface-information>
        """)).and_return(an_rpc_response(textwrap.dedent("""
            <interface-information style="terse">
              <physical-interface>
                <name>
            ge-0/0/1
            </name>
                <admin-status>
            up
            </admin-status>
                <oper-status>
            down
            </oper-status>
              </physical-interface>
            </interface-information>
        """)))

        with self.assertRaises(InterfaceNotInBond):
            self.switch.remove_interface_from_bond('ge-0/0/1')

    def test_remove_interface_from_bond_unknown_interface_raises(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/27</name>
                    <ether-options>
                      <ieee-802.3ad operation="delete" />
                    </ether-options>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_raise(
                RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            statement not found: 802.3ad
            </error-message>
            </rpc-error>"""))))

        self.netconf_mock.should_receive("rpc").with_args(is_xml("""
            <get-interface-information>
              <terse/>
            </get-interface-information>
        """)).and_return(an_rpc_response(textwrap.dedent("""
            <interface-information style="terse">
              <physical-interface>
                <name>
            ge-0/0/1
            </name>
                <admin-status>
            up
            </admin-status>
                <oper-status>
            down
            </oper-status>
              </physical-interface>
            </interface-information>
        """)))

        with self.assertRaises(UnknownInterface):
            self.switch.remove_interface_from_bond('ge-0/0/27')

    def test_change_bond_speed_update_slaves_and_interface_at_same_time(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ae10</name>
              </interface>
              <interface>
                <name>ge-0/0/1</name>
                <ether-options>
                  <ieee-802.3ad>
                    <bundle>ae10</bundle>
                  </ieee-802.3ad>
                </ether-options>
              </interface>
              <interface>
                <name>ge-0/0/2</name>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ae10</name>
                    <aggregated-ether-options>
                      <link-speed>1g</link-speed>
                    </aggregated-ether-options>
                  </interface>
                  <interface>
                    <name>ge-0/0/1</name>
                    <ether-options>
                      <speed>
                        <ethernet-1g/>
                      </speed>
                    </ether-options>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.set_bond_link_speed(10, '1g')

    def test_change_bond_speed_on_unknown_bond(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ae10</name>
              </interface>
              <interface>
                <name>ge-0/0/1</name>
                <ether-options>
                  <ieee-802.3ad>
                    <bundle>ae10</bundle>
                  </ieee-802.3ad>
                </ether-options>
              </interface>
              <interface>
                <name>ge-0/0/2</name>
              </interface>
            </interfaces>
        """))

        with self.assertRaises(UnknownBond):
            self.switch.set_bond_link_speed(20, '1g')

    def test_get_bond(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ae3</name>
                <aggregated-ether-options>
                  <link-speed>1g</link-speed>
                  <lacp>
                    <active/>
                    <periodic>slow</periodic>
                  </lacp>
                </aggregated-ether-options>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>999-1001</members>
                        <members>1000</members>
                      </vlan>
                      <native-vlan-id>2000</native-vlan-id>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-1/0/1</name>
                <ether-options>
                  <speed>
                    <ethernet-100m/>
                  </speed>
                  <ieee-802.3ad>
                    <bundle>ae3</bundle>
                  </ieee-802.3ad>
                </ether-options>
              </interface>
            </interfaces>
        """))

        if3 = self.switch.get_bond(3)

        assert_that(if3.number, equal_to(3))
        assert_that(if3.link_speed, equal_to('1g'))
        assert_that(if3.port_mode, equal_to(TRUNK))
        assert_that(if3.access_vlan, equal_to(None))
        assert_that(if3.trunk_native_vlan, equal_to(2000))
        assert_that(if3.trunk_vlans, equal_to([999, 1000, 1001]))
        assert_that(if3.members, equal_to(['ge-1/0/1']))

    def test_get_unknown_bond(self):
        self.switch.in_transaction = True
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration(""))

        with self.assertRaises(UnknownBond):
            self.switch.get_bond(3)

    def test_get_bonds(self):
        self.switch.in_transaction = False

        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <vlans/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ae1</name>
                <aggregated-ether-options>
                  <lacp>
                    <active/>
                    <periodic>slow</periodic>
                  </lacp>
                </aggregated-ether-options>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ae2</name>
                <disable />
                <description>Howdy</description>
                <mtu>5000</mtu>
                <aggregated-ether-options>
                  <link-speed>10g</link-speed>
                  <lacp>
                    <active/>
                    <periodic>slow</periodic>
                  </lacp>
                </aggregated-ether-options>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <vlan>
                        <members>1000</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ae3</name>
                <aggregated-ether-options>
                  <link-speed>1g</link-speed>
                  <lacp>
                    <active/>
                    <periodic>slow</periodic>
                  </lacp>
                </aggregated-ether-options>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                      <vlan>
                        <members>999-1001</members>
                        <members>1000</members>
                      </vlan>
                      <native-vlan-id>2000</native-vlan-id>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-0/0/4</name>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <port-mode>trunk</port-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-1/0/1</name>
                <ether-options>
                  <speed>
                    <ethernet-100m/>
                  </speed>
                  <ieee-802.3ad>
                    <bundle>ae3</bundle>
                  </ieee-802.3ad>
                </ether-options>
              </interface>
              <interface>
                <name>vlan</name>
                <unit>
                  <name>40</name>
                </unit>
              </interface>
            </interfaces>
        """))

        if1, if2, if3 = self.switch.get_bonds()

        assert_that(if1.number, equal_to(1))
        assert_that(if1.link_speed, equal_to(None))
        assert_that(if1.shutdown, equal_to(False))
        assert_that(if1.port_mode, equal_to(ACCESS))
        assert_that(if1.access_vlan, equal_to(None))
        assert_that(if1.trunk_native_vlan, equal_to(None))
        assert_that(if1.trunk_vlans, equal_to([]))
        assert_that(if1.mtu, equal_to(None))
        assert_that(if1.members, equal_to([]))

        assert_that(if2.number, equal_to(2))
        assert_that(if2.link_speed, equal_to('10g'))
        assert_that(if2.shutdown, equal_to(True))
        assert_that(if2.port_mode, equal_to(ACCESS))
        assert_that(if2.access_vlan, equal_to(1000))
        assert_that(if2.trunk_native_vlan, equal_to(None))
        assert_that(if2.trunk_vlans, equal_to([]))
        assert_that(if2.mtu, equal_to(5000))
        assert_that(if2.members, equal_to([]))

        assert_that(if3.number, equal_to(3))
        assert_that(if3.link_speed, equal_to('1g'))
        assert_that(if3.port_mode, equal_to(TRUNK))
        assert_that(if3.access_vlan, equal_to(None))
        assert_that(if3.trunk_native_vlan, equal_to(2000))
        assert_that(if3.trunk_vlans, equal_to([999, 1000, 1001]))
        assert_that(if3.members, equal_to(['ge-1/0/1']))

    def test_set_interface_lldp_state_from_nothing(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <protocols>
                  <lldp>
                    <interface>
                      <name>ge-0/0/6.0</name>
                    </interface>
                  </lldp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <protocols>
                  <lldp>
                    <interface>
                      <name>ge-0/0/6</name>
                    </interface>
                  </lldp>
                </protocols>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_interface_lldp_state('ge-0/0/6', True)

    def test_set_interface_lldp_state_from_default_interface(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <protocols>
                  <lldp>
                    <interface>
                      <name>ge-0/0/6.0</name>
                    </interface>
                  </lldp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <protocols>
                  <lldp>
                    <interface>
                      <name>ge-0/0/6</name>
                    </interface>
                  </lldp>
                </protocols>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_interface_lldp_state('ge-0/0/6', True)

    def test_set_interface_lldp_state_from_unknown_interface_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
                <filter>
                  <configuration>
                    <interfaces>
                      <interface>
                        <name>ge-0/0/99</name>
                      </interface>
                    </interfaces>
                    <protocols>
                      <lldp>
                        <interface>
                          <name>ge-0/0/99.0</name>
                        </interface>
                      </lldp>
                    </protocols>
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <interfaces/>
            """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
                <config>
                  <configuration>
                    <protocols>
                      <lldp>
                        <interface>
                          <name>ge-0/0/99</name>
                        </interface>
                      </lldp>
                    </protocols>
                  </configuration>
                </config>
            """)).and_raise(a_port_value_outside_range_rpc_error())

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.set_interface_lldp_state('ge-0/0/99', True)

        assert_that(str(expect.exception), contains_string("Unknown interface ge-0/0/99"))

    def test_set_interface_lldp_state_when_disabled(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <protocols>
                  <lldp>
                    <interface>
                      <name>ge-0/0/6.0</name>
                    </interface>
                  </lldp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
              </interface>
            </interfaces>
            <protocols>
              <lldp>
                <interface>
                  <name>ge-0/0/6.0</name>
                  <disable/>
                </interface>
              </lldp>
            </protocols>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <protocols>
                  <lldp>
                    <interface>
                      <name>ge-0/0/6</name>
                      <disable operation="delete" />
                    </interface>
                  </lldp>
                </protocols>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_interface_lldp_state('ge-0/0/6', True)

    def test_disable_lldp_when_disabled(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <protocols>
                  <lldp>
                    <interface>
                      <name>ge-0/0/6.0</name>
                    </interface>
                  </lldp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
              </interface>
            </interfaces>
            <protocols>
              <lldp>
                <interface>
                  <name>ge-0/0/6.0</name>
                  <disable/>
                </interface>
              </lldp>
            </protocols>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        self.switch.set_interface_lldp_state('ge-0/0/6', False)

    def test_disable_lldp_when_enabled(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                  </interface>
                </interfaces>
                <protocols>
                  <lldp>
                    <interface>
                      <name>ge-0/0/6.0</name>
                    </interface>
                  </lldp>
                </protocols>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>ge-0/0/6</name>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <protocols>
                  <lldp>
                    <interface>
                      <name>ge-0/0/6</name>
                      <disable />
                    </interface>
                  </lldp>
                </protocols>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_interface_lldp_state('ge-0/0/6', False)

    def test_set_interface_mtu_success(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <mtu>5000</mtu>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_interface_mtu('ge-0/0/6', 5000)

    def test_set_interface_mtu_wrong_value_raises(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <mtu>100</mtu>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            Value 100 is not within range (256..9216)
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(InvalidMtuSize) as expect:
            self.switch.set_interface_mtu('ge-0/0/6', 100)

        assert_that(str(expect.exception), contains_string("Value 100 is not within range (256..9216)"))

    def test_set_interface_mtu_unknown_interface_raises(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                    <mtu>5000</mtu>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            port value outside range 0..63 for '99' in 'ge-0/0/99'
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(UnknownInterface):
            self.switch.set_interface_mtu('ge-0/0/99', 5000)

    def test_unset_interface_mtu_success(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/6</name>
                    <mtu operation="delete" />
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.unset_interface_mtu('ge-0/0/6')

    def test_unset_interface_mtu_unknown_intercace_raises(self):
        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>ge-0/0/99</name>
                    <mtu operation="delete" />
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            port value outside range 0..63 for '99' in 'ge-0/0/99'
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(UnknownInterface):
            self.switch.unset_interface_mtu('ge-0/0/99')

    def test_bond_port_mode_access(self):
        switch = juniper.standard.netconf(SwitchDescriptor(model='', hostname=''))
        switch.set_access_mode = mock.Mock()
        switch.set_bond_access_mode(6)
        switch.set_access_mode.assert_called_with('ae6')

    def test_bond_port_mode_trunk(self):
        switch = juniper.standard.netconf(SwitchDescriptor(model='', hostname=''))
        switch.set_trunk_mode = mock.Mock()
        switch.set_bond_trunk_mode(6)
        switch.set_trunk_mode.assert_called_with('ae6')

    def test_set_bond_description_succeeds(self):
        switch = juniper.standard.netconf(SwitchDescriptor(model='', hostname=''))
        switch.set_interface_description = mock.Mock()
        switch.set_bond_description(6, "Resistance is futile")
        switch.set_interface_description.assert_called_with('ae6', "Resistance is futile")

    def test_unset_bond_description_succeeds(self):
        switch = juniper.standard.netconf(SwitchDescriptor(model='', hostname=''))
        switch.unset_interface_description = mock.Mock()
        switch.unset_bond_description(6)
        switch.unset_interface_description.assert_called_with('ae6')

    def test_set_bond_mtu_succeeds(self):
        switch = juniper.standard.netconf(SwitchDescriptor(model='', hostname=''))
        switch.set_interface_mtu = mock.Mock()
        switch.set_bond_mtu(6, 5000)
        switch.set_interface_mtu.assert_called_with('ae6', 5000)

    def test_unset_bond_mtu_succeeds(self):
        switch = juniper.standard.netconf(SwitchDescriptor(model='', hostname=''))
        switch.unset_interface_mtu = mock.Mock()
        switch.unset_bond_mtu(6)
        switch.unset_interface_mtu.assert_called_with('ae6')

    def test_add_bond_trunk_vlan(self):
        switch = juniper.standard.netconf(SwitchDescriptor(model='', hostname=''))
        switch.add_trunk_vlan = mock.Mock()
        switch.add_bond_trunk_vlan(6, 1000)
        switch.add_trunk_vlan.assert_called_with('ae6', 1000)

    def test_remove_bond_trunk_vlan(self):
        switch = juniper.standard.netconf(SwitchDescriptor(model='', hostname=''))
        switch.remove_trunk_vlan = mock.Mock()
        switch.remove_bond_trunk_vlan(6, 1000)
        switch.remove_trunk_vlan.assert_called_with('ae6', 1000)

    def test_set_bond_native_vlan(self):
        switch = juniper.standard.netconf(SwitchDescriptor(model='', hostname=''))
        switch.set_interface_native_vlan = mock.Mock()
        switch.set_bond_native_vlan(6, 1000)
        switch.set_interface_native_vlan.assert_called_with('ae6', 1000)

    def test_unset_bond_native_vlan(self):
        switch = juniper.standard.netconf(SwitchDescriptor(model='', hostname=''))
        switch.unset_interface_native_vlan = mock.Mock()
        switch.unset_bond_native_vlan(6)
        switch.unset_interface_native_vlan.assert_called_with('ae6')

    def test_edit_bond_spanning_tree(self):
        switch = juniper.standard.netconf(SwitchDescriptor(model='', hostname=''))
        switch.edit_interface_spanning_tree = mock.Mock()
        switch.edit_bond_spanning_tree(6, edge=False)
        switch.edit_interface_spanning_tree.assert_called_with('ae6', edge=False)

    @mock.patch("ncclient.manager.connect")
    def test_connect(self, connect_mock):
        connect_mock.return_value = self.netconf_mock
        self.netconf_mock._session = mock.Mock()

        self.switch = Juniper(
            SwitchDescriptor(model='juniper', hostname="toto", username="tutu", password="titi", port=8000),
            custom_strategies=JuniperCustomStrategies(), timeout=120)

        self.switch.connect()

        connect_mock.assert_called_with(
            host="toto",
            username="tutu",
            password="titi",
            hostkey_verify=False,
            device_params={'name': 'junos'},
            port=8000,
            timeout=120
        )

    @mock.patch("ncclient.manager.connect")
    def test_connect_without_port_uses_default(self, connect_mock):
        connect_mock.return_value = self.netconf_mock
        self.netconf_mock._session = mock.Mock()

        self.switch = Juniper(
            SwitchDescriptor(model='juniper', hostname="toto", username="tutu", password="titi"),
            custom_strategies=JuniperCustomStrategies(), timeout=120)

        self.switch.connect()

        connect_mock.assert_called_with(
            host="toto",
            username="tutu",
            password="titi",
            hostkey_verify=False,
            device_params={'name': 'junos'},
            timeout=120
        )

    def test_disconnect(self):
        self.netconf_mock.should_receive("close_session").once().ordered()

        self.switch.disconnect()

    def test_disconnect_doesnt_fail_if_close_session_does(self):
        self.netconf_mock.should_receive("close_session").once().ordered().and_raise(TimeoutExpiredError)

        self.switch.disconnect()

    def test_start_transaction_locks_the_candidate(self):
        self.netconf_mock.should_receive("lock").with_args(target="candidate").once().ordered()

        self.switch.start_transaction()

    def test_start_transaction_fails_discard_changes_and_retries(self):

        self.netconf_mock.should_receive("lock").with_args(target="candidate").twice()\
            .and_raise(RPCError(to_ele(textwrap.dedent("""
                <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
                <error-severity>error</error-severity>
                <error-message>
                configuration database modified
                </error-message>
                <database-status-information>
                <database-status>
                <user>admin</user>
                <terminal>p0</terminal>
                <pid>9511</pid>
                <start-time junos:seconds="1416432176">2014-11-19 16:22:56 EST</start-time>
                <idle-time junos:seconds="197">00:03:17</idle-time>
                <edit-path>[edit]</edit-path>
                </database-status>
                </database-status-information>
                </rpc-error>"""))))\
            .and_return()

        self.netconf_mock.should_receive("discard_changes").with_args().once().and_return(an_ok_response())

        self.switch.start_transaction()

    def test_start_transaction_locking_fails_already_in_use_raises(self):

        self.netconf_mock.should_receive("lock").with_args(target="candidate").once().ordered().and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            Configuration database is already open
            </error-message>
            </rpc-error>
            """))))

        with self.assertRaises(LockedSwitch) as expect:
            self.switch.start_transaction()

        assert_that(str(expect.exception), equal_to("Switch is locked and can't be modified"))

    def test_start_transaction_locking_fails_of_unknown_reason_raises(self):

        self.netconf_mock.should_receive("lock").with_args(target="candidate").once().ordered().and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            Whatever right?
            </error-message>
            </rpc-error>
            """))))

        with self.assertRaises(RPCError) as expect:
            self.switch.start_transaction()

        assert_that(str(expect.exception), contains_string("Whatever right?"))

    def test_end_transaction(self):
        self.netconf_mock.should_receive("unlock").with_args(target="candidate").once().ordered()

        self.switch.end_transaction()

    def test_commit_succeeds(self):
        self.netconf_mock.should_receive("commit").with_args().once().ordered()

        self.switch.commit_transaction()

    def test_commit_transaction_failing_to_commit_discard_changes_and_raises(self):
        self.netconf_mock.should_receive("commit").with_args().once().ordered().and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <source-daemon>
            eswd
            </source-daemon>
            <error-message>
            tag value 1000 is being used by more than one vlan &lt;VLAN1000&gt; and &lt;SOMETHINGELSE&gt;
            </error-message>
            </rpc-error>
        """))))

        with self.assertRaises(OperationNotCompleted) as expect:
            self.switch.commit_transaction()

        assert_that(str(expect.exception), equal_to("An error occured while completing operation, no modifications have been applied : tag value 1000 is being used by more than one vlan <VLAN1000> and <SOMETHINGELSE>"))

    def test_rollback_succeeds(self):
        self.netconf_mock.should_receive("discard_changes").with_args().once().ordered()

        self.switch.rollback_transaction()


def a_configuration(inner_data=""):
    return an_rpc_response("""
        <data>
          <configuration>{}</configuration>
        </data>
        """.format(inner_data))


def an_ok_response():
    return an_rpc_response(textwrap.dedent("""
        <ok/>
        """))


def an_rpc_response(data):
    return NCElement(textwrap.dedent("""
        <rpc-reply message-id="urn:uuid:34c41736-bed3-11e4-8c40-7c05070fe456">
        {}
        </rpc-reply>""".format(data)), JunosDeviceHandler(None).transform_reply())


def a_port_value_outside_range_rpc_error():
    return RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-severity>error</error-severity>
            <error-message>
            port value outside range 0..63 for '99' in 'ge-0/0/99'
            </error-message>
            </rpc-error>""")))


def is_xml(string):
    return IsXmlFlexmockArgMatcher(string)


class IsXmlFlexmockArgMatcher(object):
    def __init__(self, expected):
        self.expected = to_ele(expected)

    def __eq__(self, other):
        otherxml = other if not isinstance(other, basestring) else to_ele(other)
        try:
            self.compare(self.expected, otherxml)
            return True
        except AssertionError as e:
            logging.warning("Given XML : \n" + to_xml(otherxml, pretty_print=True) +
                            "\n\ndiffers from expected : \n" + to_xml(self.expected, pretty_print=True) +
                            "Because : " + str(e))
            return False

    def compare(self, expected, actual):
        for i, node in enumerate(expected):
            assert_that(node.tag, equal_to(unqualify(actual[i].tag)))
            assert_that(node, has_length(len(actual[i])))
            assert_that(actual[i].attrib, has_length(len(node.attrib)))
            if node.text is not None:
                if node.text.strip() == "":
                    assert_that(actual[i].text is None or actual[i].text.strip() == "")
                else:
                    assert_that(actual[i].text is not None, "Node is " + node.tag)
                    assert_that(node.text.strip(), equal_to(actual[i].text.strip()))
            for name, value in node.attrib.items():
                assert_that(actual[i].attrib, has_key(name))
                assert_that(actual[i].attrib[name], equal_to(value))
            self.compare(node, actual[i])


def unqualify(tag):
    return re.sub("\{[^\}]*\}", "", tag)
