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
import textwrap
import unittest

import mock
from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, equal_to, is_, instance_of

from netman.adapters.switches import juniper
from netman.adapters.switches.juniper import Juniper
from netman.core.objects.exceptions import UnknownInterface
from netman.core.objects.port_modes import ACCESS, TRUNK, BOND_MEMBER
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.objects.switch_transactional import FlowControlSwitch
from tests import ignore_deprecation_warnings
from tests.adapters.switches.juniper_test import an_ok_response, is_xml, a_configuration, an_rpc_response


@ignore_deprecation_warnings
def test_factory():
    lock = mock.Mock()
    switch = juniper.qfx_copper_factory(SwitchDescriptor(hostname='hostname', model='juniper_qfx_copper', username='username', password='password', port=22), lock)

    assert_that(switch, instance_of(FlowControlSwitch))
    assert_that(switch.wrapped_switch, instance_of(Juniper))
    assert_that(switch.lock, is_(lock))
    assert_that(switch.switch_descriptor.hostname, equal_to("hostname"))
    assert_that(switch.switch_descriptor.model, equal_to("juniper_qfx_copper"))
    assert_that(switch.switch_descriptor.username, equal_to("username"))
    assert_that(switch.switch_descriptor.password, equal_to("password"))
    assert_that(switch.switch_descriptor.port, equal_to(22))


class JuniperTest(unittest.TestCase):

    def setUp(self):
        self.switch = juniper.qfx_copper.netconf(SwitchDescriptor(model='juniper', hostname="toto"))

        self.netconf_mock = flexmock()
        self.switch.netconf = self.netconf_mock
        self.switch.in_transaction = True

    def tearDown(self):
        flexmock_teardown()

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
                  <interface>
                    <name>ge-0/0/2</name>
                    <disable />
                    <description>Howdy</description>
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

        if1 = self.switch.get_interface('ge-0/0/1')

        assert_that(if1.name, equal_to("ge-0/0/1"))
        assert_that(if1.shutdown, equal_to(False))
        assert_that(if1.port_mode, equal_to(ACCESS))
        assert_that(if1.access_vlan, equal_to(None))
        assert_that(if1.trunk_native_vlan, equal_to(None))
        assert_that(if1.trunk_vlans, equal_to([]))
        assert_that(if1.auto_negotiation, equal_to(None))

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
                        <admin-status>
                    up
                    </admin-status>
                        <oper-status>
                    down
                    </oper-status>
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
                <native-vlan-id>2000</native-vlan-id>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <interface-mode>trunk</interface-mode>
                      <vlan>
                        <members>999-1001</members>
                        <members>1000</members>
                      </vlan>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-0/0/4</name>
                <ether-options>
                  <no-auto-negotiation/>
                </ether-options>
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <interface-mode>trunk</interface-mode>
                    </ethernet-switching>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>ge-0/0/5</name>
                <ether-options>
                  <auto-negotiation/>
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

        assert_that(if2.name, equal_to("ge-0/0/2"))
        assert_that(if2.shutdown, equal_to(True))
        assert_that(if2.port_mode, equal_to(ACCESS))
        assert_that(if2.access_vlan, equal_to(1000))
        assert_that(if2.trunk_native_vlan, equal_to(None))
        assert_that(if2.trunk_vlans, equal_to([]))

        assert_that(if3.name, equal_to("ge-0/0/3"))
        assert_that(if3.port_mode, equal_to(TRUNK))
        assert_that(if3.access_vlan, equal_to(None))
        assert_that(if3.trunk_native_vlan, equal_to(2000))
        assert_that(if3.trunk_vlans, equal_to([999, 1000, 1001]))

        assert_that(if4.name, equal_to("ge-0/0/4"))
        assert_that(if4.trunk_native_vlan, equal_to(None))
        assert_that(if4.trunk_vlans, equal_to([]))
        assert_that(if4.auto_negotiation, equal_to(False))

        assert_that(if5.name, equal_to("ge-0/0/5"))
        assert_that(if5.port_mode, equal_to(BOND_MEMBER))
        assert_that(if5.bond_master, equal_to(10))
        assert_that(if5.auto_negotiation, equal_to(True))

    def test_get_interface_with_trunk_native_vlan_at_root(self):
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
                    <native-vlan-id>1000</native-vlan-id>
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

        if1 = self.switch.get_interface('ge-0/0/1')

        assert_that(if1.name, equal_to("ge-0/0/1"))
        assert_that(if1.trunk_native_vlan, equal_to(1000))

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
                          <interface-mode>access</interface-mode>
                        </ethernet-switching>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_mode("ge-0/0/6")

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
                      <auto-negotiation/>
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
                  <name>ge-0/0/1</name>
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
                      <auto-negotiation/>
                      <ieee-802.3ad>
                        <bundle>ae10</bundle>
                      </ieee-802.3ad>
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
                    </ether-options>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.set_bond_link_speed(10, '1g')
