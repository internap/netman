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

from contextlib import contextmanager
import unittest

from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, equal_to, is_, instance_of
import mock

from tests.adapters.switches.juniper_test import an_ok_response, is_xml, a_configuration
from netman.adapters.switches import juniper
from netman.core.objects.switch_transactional import SwitchTransactional
from netman.adapters.switches.juniper import Juniper
from netman.core.objects.port_modes import ACCESS, TRUNK, BOND_MEMBER
from netman.core.objects.switch_descriptor import SwitchDescriptor


def test_factory():
    lock = mock.Mock()
    switch = juniper.qfx_copper_factory(SwitchDescriptor(hostname='hostname', model='juniper_qfx_copper', username='username', password='password', port=22), lock)

    assert_that(switch, instance_of(SwitchTransactional))
    assert_that(switch.impl, instance_of(Juniper))
    assert_that(switch.lock, is_(lock))
    assert_that(switch.switch_descriptor.hostname, equal_to("hostname"))
    assert_that(switch.switch_descriptor.model, equal_to("juniper_qfx_copper"))
    assert_that(switch.switch_descriptor.username, equal_to("username"))
    assert_that(switch.switch_descriptor.password, equal_to("password"))
    assert_that(switch.switch_descriptor.port, equal_to(22))


class JuniperTest(unittest.TestCase):

    def setUp(self):
        self.lock = mock.Mock()
        self.switch = juniper.qfx_copper_factory(SwitchDescriptor(model='juniper', hostname="toto", username="tutu", password="titi"), self.lock)

        self.netconf_mock = flexmock()
        self.switch.impl.netconf = self.netconf_mock

    def tearDown(self):
        flexmock_teardown()

    def test_get_interfaces(self):
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
                <unit>
                  <name>0</name>
                  <family>
                    <ethernet-switching>
                      <interface-mode>trunk</interface-mode>
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

        assert_that(if5.name, equal_to("ge-0/0/5"))
        assert_that(if5.port_mode, equal_to(BOND_MEMBER))
        assert_that(if5.bond_master, equal_to(10))

    def test_port_mode_access_with_no_port_mode_or_vlan_set_just_sets_the_port_mode(self):
        with self.expecting_successful_transaction():
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
        with self.expecting_successful_transaction():

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
        with self.expecting_successful_transaction():

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
        with self.expecting_successful_transaction():

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

    @contextmanager
    def expecting_successful_transaction(self):
        self.netconf_mock.should_receive("lock").with_args(target="candidate").once().ordered()

        yield

        self.netconf_mock.should_receive("commit").with_args().once().ordered()
        self.netconf_mock.should_receive("unlock").with_args(target="candidate").once().ordered()
