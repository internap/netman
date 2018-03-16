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

from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, equal_to, instance_of, contains_string, has_length, is_
from ncclient.operations import RPCError
from ncclient.xml_ import to_ele
from netaddr import IPAddress, IPNetwork
from netman.adapters.switches.juniper.base import Juniper
from netman.adapters.switches.juniper.mx import netconf
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import VlanAlreadyExist, BadVlanNumber, BadVlanName, UnknownVlan, \
    IPAlreadySet, UnknownIP, InterfaceInWrongPortMode, AccessVlanNotSet, UnknownInterface, TrunkVlanNotSet, \
    VrrpDoesNotExistForVlan
from netman.core.objects.port_modes import ACCESS
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.switch_factory import RealSwitchFactory
from tests.adapters.switches.juniper_test import an_ok_response, is_xml, a_configuration, an_rpc_response


def test_factory():
    switch = RealSwitchFactory().get_switch_by_descriptor(
                SwitchDescriptor(hostname='hostname', model='juniper_mx', username='username', password='password', port=22)
            )

    assert_that(switch, instance_of(Juniper))
    assert_that(switch.switch_descriptor.hostname, equal_to("hostname"))
    assert_that(switch.switch_descriptor.model, equal_to("juniper_mx"))
    assert_that(switch.switch_descriptor.username, equal_to("username"))
    assert_that(switch.switch_descriptor.password, equal_to("password"))
    assert_that(switch.switch_descriptor.port, equal_to(22))


class JuniperMXTest(unittest.TestCase):
    def setUp(self):
        self.switch = netconf(SwitchDescriptor(model='juniper_mx', hostname="toto"))

        self.netconf_mock = flexmock()
        self.switch.netconf = self.netconf_mock
        self.switch.in_transaction = True

    def tearDown(self):
        flexmock_teardown()

    def test_add_vlan(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>900</vlan-id>
              </domain>
            </bridge-domains>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <bridge-domains>
                  <domain>
                    <name>VLAN1000</name>
                    <vlan-id>1000</vlan-id>
                    <description>Shizzle</description>
                  </domain>
                </bridge-domains>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.add_vlan(1000, name="Shizzle")

    def test_add_vlan_already_in_use_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(VlanAlreadyExist) as expect:
            self.switch.add_vlan(1000)

        assert_that(str(expect.exception), contains_string("Vlan 1000 already exist"))

    def test_add_existing_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>VLAN1000</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(VlanAlreadyExist) as expect:
            self.switch.add_vlan(1000)

        assert_that(str(expect.exception), contains_string("Vlan 1000 already exist"))

    def test_add_vlan_bad_vlan_id(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
                <filter>
                  <configuration>
                    <bridge-domains />
                  </configuration>
                </filter>
            """)).and_return(a_configuration(""))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
                <config>
                  <configuration>
                    <bridge-domains>
                      <domain>
                        <name>VLAN9000</name>
                        <vlan-id>9000</vlan-id>
                      </domain>
                    </bridge-domains>
                  </configuration>
                </config>
            """)).and_raise(RPCError(to_ele(textwrap.dedent("""
                <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/15.1R4/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">>
                <error-severity>error</error-severity>
                <error-info>
                  <bad-element>domain</bad-element>
                </error-info>
                <error-message>Value 9000 is not within range (1..4094)</error-message>
                </rpc-error>
            """))))

        with self.assertRaises(BadVlanNumber) as expect:
            self.switch.add_vlan(9000)

        assert_that(str(expect.exception), equal_to("Vlan number is invalid"))

    def test_add_vlan_empty_vlan_name(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
                <filter>
                  <configuration>
                    <bridge-domains />
                  </configuration>
                </filter>
            """)).and_return(a_configuration(""))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
                <config>
                  <configuration>
                    <bridge-domains>
                      <domain>
                        <name>VLAN1000</name>
                        <vlan-id>1000</vlan-id>
                        <description></description>
                      </domain>
                    </bridge-domains>
                  </configuration>
                </config>
            """)).and_raise(RPCError(to_ele(textwrap.dedent("""
                 <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                 xmlns:junos="http://xml.juniper.net/junos/15.1R4/junos"
                 xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
                    <error-type>protocol</error-type>
                    <error-tag>operation-failed</error-tag>
                    <error-severity>error</error-severity>
                    <error-message>description: '': Must be a string of 255 characters or less</error-message>
                    <error-info>
                      <bad-element>domain</bad-element>
                    </error-info>
                  </rpc-error>
            """))))

        with self.assertRaises(BadVlanName) as expect:
            self.switch.add_vlan(1000, "")

        assert_that(str(expect.exception), equal_to("Vlan name is invalid"))

    def test_add_vlan_too_long_vlan_name(self):
        long_string = 'a' * 256
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
                <filter>
                  <configuration>
                    <bridge-domains />
                  </configuration>
                </filter>
            """)).and_return(a_configuration(""))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
                <config>
                  <configuration>
                    <bridge-domains>
                      <domain>
                        <name>VLAN1000</name>
                        <vlan-id>1000</vlan-id>
                        <description>{}</description>
                      </domain>
                    </bridge-domains>
                  </configuration>
                </config>
            """.format(long_string))).and_raise(RPCError(to_ele(textwrap.dedent("""
                 <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                 xmlns:junos="http://xml.juniper.net/junos/15.1R4/junos"
                 xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
                    <error-type>protocol</error-type>
                    <error-tag>operation-failed</error-tag>
                    <error-severity>error</error-severity>
                    <error-message>description: '{}': Must be a string of 255 characters or less</error-message>
                    <error-info>
                      <bad-element>domain</bad-element>
                    </error-info>
                  </rpc-error>
            """.format(long_string)))))

        with self.assertRaises(BadVlanName) as expect:
            self.switch.add_vlan(1000, long_string)

        assert_that(str(expect.exception), equal_to("Vlan name is invalid"))

    def test_add_vlan_raises_RPCError(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
                <filter>
                  <configuration>
                    <bridge-domains />
                  </configuration>
                </filter>
            """)).and_return(a_configuration(""))

        self.netconf_mock.should_receive("edit_config").once().and_raise(RPCError(to_ele(textwrap.dedent("""
                 <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                 xmlns:junos="http://xml.juniper.net/junos/15.1R4/junos"
                 xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
                    <error-type>protocol</error-type>
                    <error-tag>operation-failed</error-tag>
                    <error-severity>error</error-severity>
                    <error-message>There's another problem</error-message>
                    <error-info>
                      <bad-element>domain</bad-element>
                    </error-info>
                  </rpc-error>
            """))))

        with self.assertRaises(RPCError):
            self.switch.add_vlan(1000, 'a' * 256)

    def test_remove_vlan_ignores_removing_interface_not_created(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>STANDARD</name>
                <vlan-id>10</vlan-id>
              </domain>
            </bridge-domains>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <bridge-domains>
                  <domain operation="delete">
                    <name>STANDARD</name>
                  </domain>
                </bridge-domains>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.remove_vlan(10)

    def test_remove_vlan_invalid_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>ANOTHER</name>
                <vlan-id>10</vlan-id>
              </domain>
            </bridge-domains>
        """))

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vlan(20)

        assert_that(str(expect.exception), equal_to("Vlan 20 not found"))

    def test_remove_vlan_also_removes_associated_interface(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains/>
                <interfaces/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>MEH</name>
                <vlan-id>5</vlan-id>
              </domain>
              <domain>
                <name>STANDARD</name>
                <vlan-id>10</vlan-id>
                <routing-interface>irb.25</routing-interface>
              </domain>
              <domain>
                <name>MEH2</name>
                <vlan-id>15</vlan-id>
              </domain>
            </bridge-domains>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <bridge-domains>
                  <domain operation="delete">
                    <name>STANDARD</name>
                  </domain>
                </bridge-domains>
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

    def test_remove_vlan_in_use_deletes_all_usages(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>STANDARD</name>
                <vlan-id>10</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/1</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>trunk</interface-mode>
                        <vlan-id-list>9</vlan-id-list>
                        <vlan-id-list>10</vlan-id-list>
                        <vlan-id-list>11</vlan-id-list>
                    </bridge>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>xe-0/0/2</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>trunk</interface-mode>
                        <vlan-id-list>9-15</vlan-id-list>
                    </bridge>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>xe-0/0/3</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                        <interface-mode>access</interface-mode>
                        <vlan-id-list>12</vlan-id-list>
                    </bridge>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>xe-0/0/4</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>access</interface-mode>
                        <vlan-id>STANDARD</vlan-id>
                    </bridge>
                  </family>
                </unit>
              </interface>
              <interface>
                <name>xe-0/0/5</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>access</interface-mode>
                        <vlan-id>ANOTHER_NAME</vlan-id>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <bridge-domains>
                  <domain operation="delete">
                    <name>STANDARD</name>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>xe-0/0/1</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                          <vlan-id-list operation="delete">10</vlan-id-list>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                  <interface>
                    <name>xe-0/0/2</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                            <vlan-id-list operation="delete">9-15</vlan-id-list>
                            <vlan-id-list>9</vlan-id-list>
                            <vlan-id-list>11-15</vlan-id-list>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                  <interface>
                    <name>xe-0/0/4</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                            <vlan-id operation="delete">STANDARD</vlan-id>
                        </bridge>
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
                <bridge-domains />
                <interfaces />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>STANDARD</name>
                <vlan-id>10</vlan-id>
                <routing-interface>irb.10</routing-interface>
              </domain>
            </bridge-domains>
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
                <name>xe-0/0/1</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <port-mode>trunk</port-mode>
                        <vlan-id-list>10</vlan-id-list>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <bridge-domains>
                  <domain operation="delete">
                    <name>STANDARD</name>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>irb</name>
                    <unit operation="delete">
                      <name>10</name>
                    </unit>
                  </interface>
                  <interface>
                    <name>xe-0/0/1</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                            <vlan-id-list operation="delete">10</vlan-id-list>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.remove_vlan(10)

    def test_get_vlans(self):
        self.switch.in_transaction = False

        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                <filter>
                  <configuration>
                    <bridge-domains />
                    <interfaces />
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <bridge-domains>
                  <domain>
                    <name>STANDARD</name>
                    <vlan-id>10</vlan-id>
                    <description>my-description</description>
                  </domain>
                  <domain>
                    <name>NO-VLAN-ID</name>
                    <description>shizzle</description>
                  </domain>
                  <domain>
                    <name>WITH-IF</name>
                    <vlan-id>20</vlan-id>
                    <routing-interface>irb.20</routing-interface>
                  </domain>
                  <domain>
                    <name>WITH-IF-MULTI-IP</name>
                    <vlan-id>40</vlan-id>
                    <routing-interface>irb.70</routing-interface>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>xe-0/0/1</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                        </bridge>
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

    def test_get_vlan_with_interface_multi_ip(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                <filter>
                  <configuration>
                    <bridge-domains />
                    <interfaces />
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <bridge-domains>
                  <domain>
                    <name>This-another-clam</name>
                    <vlan-id>39</vlan-id>
                    <routing-interface>irb.20</routing-interface>
                  </domain>
                  <domain>
                    <name>WITH-IF-MULTI-IP</name>
                    <vlan-id>40</vlan-id>
                    <routing-interface>irb.70</routing-interface>
                  </domain>
                  <domain>
                    <name>This-yet-another-clam</name>
                    <vlan-id>41</vlan-id>
                    <routing-interface>irb.40</routing-interface>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>xe-0/0/1</name>
                  </interface>
                  <interface>
                    <name>irb</name>
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
        assert_that(vlan.icmp_redirects, equal_to(True))
        vlanip1, vlanip2, vlanip3 = vlan.ips
        assert_that(str(vlanip1.ip), equal_to("2.1.1.1"))
        assert_that(vlanip1.prefixlen, equal_to(24))
        assert_that(str(vlanip2.ip), equal_to("3.1.1.1"))
        assert_that(vlanip2.prefixlen, equal_to(24))
        assert_that(str(vlanip3.ip), equal_to("4.1.1.1"))
        assert_that(vlanip3.prefixlen, equal_to(24))

    def test_get_vlan_with_no_interface(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                <filter>
                  <configuration>
                    <bridge-domains />
                    <interfaces />
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <bridge-domains>
                  <domain>
                    <name>STANDARD</name>
                    <vlan-id>10</vlan-id>
                    <description>my-description</description>
                  </domain>
                </bridge-domains>
            """))

        vlan = self.switch.get_vlan(10)

        assert_that(vlan.number, equal_to(10))
        assert_that(vlan.name, equal_to("my-description"))
        assert_that(vlan.access_groups[IN], equal_to(None))
        assert_that(vlan.access_groups[OUT], equal_to(None))
        assert_that(vlan.icmp_redirects, equal_to(True))
        assert_that(vlan.ips, has_length(0))

    def test_get_vlan_with_unknown_vlan(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                <filter>
                  <configuration>
                    <bridge-domains />
                    <interfaces />
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <bridge-domains>
                  <domain>
                    <name>This-another-clam</name>
                    <vlan-id>39</vlan-id>
                  </domain>
                </bridge-domains>
            """))

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.get_vlan(10)

        assert_that(str(expect.exception), equal_to("Vlan 10 not found"))

    def test_get_vlan_with_interface(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                <filter>
                  <configuration>
                    <bridge-domains />
                    <interfaces />
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <bridge-domains>
                  <domain>
                    <name>WITH-IF</name>
                    <vlan-id>20</vlan-id>
                    <routing-interface>irb.20</routing-interface>
                  </domain>
                </bridge-domains>
                <interfaces>
              <interface>
                <name>xe-0/0/1</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                    </bridge>
                  </family>
                </unit>
              </interface>
                  <interface>
                    <name>xe-0/0/1</name>
                  </interface>
                  <interface>
                    <name>irb</name>
                    <unit>
                      <name>20</name>
                      <family>
                        <inet>
                          <no-redirects />
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
        assert_that(vlan.icmp_redirects, equal_to(False))
        assert_that(vlan.ips, has_length(1))
        vlan20ip1 = vlan.ips[0]
        assert_that(str(vlan20ip1.ip), equal_to("1.1.1.1"))
        assert_that(vlan20ip1.prefixlen, equal_to(24))

    def test_get_vlan_with_vrrp(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                <filter>
                  <configuration>
                    <bridge-domains />
                    <interfaces />
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <bridge-domains>
                  <domain>
                    <name>WITH-IF</name>
                    <vlan-id>20</vlan-id>
                    <routing-interface>irb.20</routing-interface>
                  </domain>
                </bridge-domains>
                <interfaces>
                <interface>
                  <name>irb</name>
                  <unit>
                    <name>20</name>
                    <family>
                      <inet>
                        <address>
                          <name>1.1.1.2/24</name>
                          <vrrp-group>
                            <name>1</name>
                            <virtual-address>1.1.1.1</virtual-address>
                            <priority>90</priority>
                            <preempt>
                              <hold-time>60</hold-time>
                            </preempt>
                            <accept-data/>
                            <authentication-type>simple</authentication-type>
                            <authentication-key>$9$1/aElvwsgoaGz3reKvLX.Pf5n/</authentication-key>
                            <track>
                              <route>
                                <route_address>0.0.0.0/0</route_address>
                                <routing-instance>default</routing-instance>
                                <priority-cost>50</priority-cost>
                              </route>
                            </track>
                        </vrrp-group>
                        </address>
                      </inet>
                    </family>
                  </unit>
                </interface>
                </interfaces>
            """))

        vlan = self.switch.get_vlan(20)

        vrrp = vlan.vrrp_groups[0]
        assert_that(vrrp.id, is_(1))
        assert_that(vrrp.ips, has_length(1))
        assert_that(vrrp.ips[0], is_(IPAddress('1.1.1.1')))
        assert_that(vrrp.priority, is_(90))
        assert_that(vrrp.hello_interval, is_(None))
        assert_that(vrrp.dead_interval, is_(None))
        assert_that(vrrp.track_id, is_("0.0.0.0/0"))
        assert_that(vrrp.track_decrement, is_(50))

    def test_get_vlan_with_vrrp_without_optional_fields_and_multiple_vips(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                <filter>
                  <configuration>
                    <bridge-domains />
                    <interfaces />
                  </configuration>
                </filter>
            """)).and_return(a_configuration("""
                <bridge-domains>
                  <domain>
                    <name>WITH-IF</name>
                    <vlan-id>20</vlan-id>
                    <routing-interface>irb.20</routing-interface>
                  </domain>
                </bridge-domains>
                <interfaces>
                <interface>
                  <name>irb</name>
                  <unit>
                    <name>20</name>
                    <family>
                      <inet>
                        <address>
                          <name>1.1.1.2/24</name>
                          <vrrp-group>
                            <name>1</name>
                            <virtual-address>1.1.1.1</virtual-address>
                            <virtual-address>1.1.1.3</virtual-address>
                          </vrrp-group>
                        </address>
                      </inet>
                    </family>
                  </unit>
                </interface>
                </interfaces>
            """))

        vlan = self.switch.get_vlan(20)

        vrrp = vlan.vrrp_groups[0]
        assert_that(vrrp.id, is_(1))
        assert_that(vrrp.ips, has_length(2))
        assert_that(vrrp.ips[0], is_(IPAddress('1.1.1.1')))
        assert_that(vrrp.ips[1], is_(IPAddress('1.1.1.3')))
        assert_that(vrrp.priority, is_(None))
        assert_that(vrrp.hello_interval, is_(None))
        assert_that(vrrp.dead_interval, is_(None))
        assert_that(vrrp.track_id, is_(None))
        assert_that(vrrp.track_decrement, is_(None))

    def test_add_vrrp_success(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>irb</name>
                  <unit>
                    <name>1234</name>
                    <family>
                      <inet>
                        <address>
                            <name>3.3.3.2/27</name>
                        </address>
                      </inet>
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
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                        <family>
                          <inet>
                            <address>
                              <name>3.3.3.2/27</name>
                              <vrrp-group>
                                <name>1</name>
                                <priority>110</priority>
                                <preempt>
                                  <hold-time>60</hold-time>
                                </preempt>
                                <accept-data/>
                                <authentication-type>simple</authentication-type>
                                <authentication-key>VLAN1234</authentication-key>
                                <track>
                                  <route>
                                    <route_address>0.0.0.0/0</route_address>
                                    <routing-instance>default</routing-instance>
                                    <priority-cost>50</priority-cost>
                                  </route>
                                </track>
                                <virtual-address>3.3.3.1</virtual-address>
                              </vrrp-group>
                            </address>
                          </inet>
                        </family>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("3.3.3.1")], priority=110, track_id="0.0.0.0/0",
                                   track_decrement=50)

    def test_add_vrrp_multiple_ips(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>irb</name>
                  <unit>
                    <name>1234</name>
                    <family>
                      <inet>
                        <address>
                            <name>3.3.3.2/27</name>
                        </address>
                      </inet>
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
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                        <family>
                          <inet>
                            <address>
                              <name>3.3.3.2/27</name>
                              <vrrp-group>
                                <name>1</name>
                                <priority>110</priority>
                                <preempt>
                                  <hold-time>60</hold-time>
                                </preempt>
                                <accept-data/>
                                <authentication-type>simple</authentication-type>
                                <authentication-key>VLAN1234</authentication-key>
                                <track>
                                  <route>
                                    <route_address>0.0.0.0/0</route_address>
                                    <routing-instance>default</routing-instance>
                                    <priority-cost>50</priority-cost>
                                  </route>
                                </track>
                                <virtual-address>3.3.3.1</virtual-address>
                                <virtual-address>3.3.3.3</virtual-address>
                              </vrrp-group>
                            </address>
                          </inet>
                        </family>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("3.3.3.1"), IPAddress("3.3.3.3")], priority=110,
                                   track_id="0.0.0.0/0", track_decrement=50)

    def test_add_vrrp_fails_when_vlan_not_found(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration())

        with self.assertRaises(UnknownVlan):
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("3.3.3.1")], priority=110, track_id="0.0.0.0/0",
                                       track_decrement=50)

    def test_add_vrrp_adds_it_to_the_good_address(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>irb</name>
                  <unit>
                    <name>1234</name>
                    <family>
                      <inet>
                        <address>
                            <name>3.3.3.2/27</name>
                        </address>
                        <address>
                            <name>4.4.4.2/27</name>
                        </address>
                        <address>
                            <name>5.5.5.2/27</name>
                        </address>
                      </inet>
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
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                        <family>
                          <inet>
                            <address>
                              <name>4.4.4.2/27</name>
                              <vrrp-group>
                                <name>1</name>
                                <priority>110</priority>
                                <preempt>
                                  <hold-time>60</hold-time>
                                </preempt>
                                <accept-data/>
                                <authentication-type>simple</authentication-type>
                                <authentication-key>VLAN1234</authentication-key>
                                <track>
                                  <route>
                                    <route_address>0.0.0.0/0</route_address>
                                    <routing-instance>default</routing-instance>
                                    <priority-cost>50</priority-cost>
                                  </route>
                                </track>
                                <virtual-address>4.4.4.1</virtual-address>
                              </vrrp-group>
                            </address>
                          </inet>
                        </family>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("4.4.4.1")], priority=110, track_id="0.0.0.0/0",
                                   track_decrement=50)

    def test_add_vrrp_adds_it_if_all_ips_are_within_a_single_address(self):
        self.netconf_mock.should_receive("get_config").and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>irb</name>
                  <unit>
                    <name>1234</name>
                    <family>
                      <inet>
                        <address>
                            <name>1.1.1.1/27</name>
                        </address>
                      </inet>
                    </family>
                  </unit>
              </interface>
            </interfaces>
        """))
        self.netconf_mock.should_receive("edit_config").once()
        self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.1.1.2"), IPAddress("1.1.1.3")],
                                   priority=110, track_id="0.0.0.0/0",
                                   track_decrement=50)

    def test_add_vrrp_fails_when_the_ips_doesnt_belong_to_an_existing_address(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>irb</name>
                  <unit>
                    <name>1234</name>
                    <family>
                      <inet>
                        <address>
                            <name>3.3.3.2/27</name>
                        </address>
                      </inet>
                    </family>
                  </unit>
              </interface>
            </interfaces>
        """))

        with self.assertRaises(UnknownIP):
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("4.4.4.1")], priority=110, track_id="0.0.0.0/0",
                                       track_decrement=50)

    def test_add_vrrp_fail_if_all_ips_are_not_in_the_same_address(self):
        self.netconf_mock.should_receive("get_config").and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>irb</name>
                  <unit>
                    <name>1234</name>
                    <family>
                      <inet>
                        <address>
                            <name>1.1.1.1/27</name>
                        </address>
                        <address>
                            <name>2.2.2.2/27</name>
                        </address>
                      </inet>
                    </family>
                  </unit>
              </interface>
            </interfaces>
        """))
        with self.assertRaises(UnknownIP):
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("1.1.1.2"), IPAddress("2.2.2.3")],
                                       priority=110, track_id="0.0.0.0/0",
                                       track_decrement=50)

    def test_add_vrrp_fails_when_any_of_the_ips_doesnt_belong_to_an_existing_address(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>irb</name>
                  <unit>
                    <name>1234</name>
                    <family>
                      <inet>
                        <address>
                            <name>3.3.3.2/27</name>
                        </address>
                      </inet>
                    </family>
                  </unit>
              </interface>
            </interfaces>
        """))

        with self.assertRaises(UnknownIP):
            self.switch.add_vrrp_group(1234, 1, ips=[IPAddress("3.3.3.1"), IPAddress("4.4.4.1")], priority=110, track_id="0.0.0.0/0",
                                       track_decrement=50)

    def test_remove_vrrp_success(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>irb</name>
                  <unit>
                    <name>1234</name>
                    <family>
                      <inet>
                        <address>
                          <name>192.0.1.1/27</name>
                          <vrrp-group>
                            <name>1</name>
                            <virtual-address>192.0.1.2</virtual-address>
                          </vrrp-group>
                        </address>
                      </inet>
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
                    <name>irb</name>
                    <unit>
                      <name>1234</name>
                      <family>
                        <inet>
                          <address>
                            <name>192.0.1.1/27</name>
                            <vrrp-group operation="delete">
                              <name>1</name>
                            </vrrp-group>
                          </address>
                        </inet>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.remove_vrrp_group(1234, 1)

    def test_remove_vrrp_with_invalid_group_id(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>irb</name>
                  <unit>
                    <name>1234</name>
                    <family>
                      <inet>
                        <address>
                          <name>192.0.1.1/27</name>
                          <vrrp-group>
                            <name>99</name>
                            <virtual-address>192.0.1.2</virtual-address>
                          </vrrp-group>
                        </address>
                      </inet>
                    </family>
                  </unit>
              </interface>
            </interfaces>"""))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(VrrpDoesNotExistForVlan) as expect:
            self.switch.remove_vrrp_group(1234, 1)

        assert_that(str(expect.exception), equal_to("Vrrp group 1 does not exist for vlan 1234"))

    def test_remove_vrrp_from_unknown_vlan(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration())

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.remove_vrrp_group(1234, 2)

        assert_that(str(expect.exception), equal_to("Vlan 1234 not found"))

    def test_add_ip_to_vlan(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains>
                  <domain>
                    <vlan-id>1234</vlan-id>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>irb</name>
                    <unit>
                      <name>1234</name>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>VLAN1234</name>
                <vlan-id>1234</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <bridge-domains>
                  <domain>
                    <name>VLAN1234</name>
                    <vlan-id>1234</vlan-id>
                    <routing-interface>irb.1234</routing-interface>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>irb</name>
                    <unit>
                      <name>1234</name>
                      <family>
                        <inet>
                          <address>
                            <name>3.3.3.2/27</name>
                          </address>
                        </inet>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.add_ip_to_vlan(vlan_number=1234, ip_network=IPNetwork("3.3.3.2/27"))

    def test_add_ip_to_vlan_unknown_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains>
                  <domain>
                    <vlan-id>1234</vlan-id>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>irb</name>
                    <unit>
                      <name>1234</name>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration())

        with self.assertRaises(UnknownVlan):
            self.switch.add_ip_to_vlan(vlan_number=1234, ip_network=IPNetwork("3.3.3.2/27"))

    def test_add_ip_to_vlan_ip_already_exists_in_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains>
                  <domain>
                    <vlan-id>1234</vlan-id>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>irb</name>
                    <unit>
                      <name>1234</name>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>VLAN1234</name>
                <vlan-id>1234</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>irb</name>
                  <unit>
                    <name>1234</name>
                    <family>
                      <inet>
                        <address>
                            <name>3.3.3.2/27</name>
                        </address>
                      </inet>
                    </family>
                  </unit>
              </interface>
            </interfaces>
        """))

        with self.assertRaises(IPAlreadySet):
            self.switch.add_ip_to_vlan(vlan_number=1234, ip_network=IPNetwork("3.3.3.2/27"))

    def test_set_icmp_redirect_state_false_not_set_adds_statement(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains>
                  <domain>
                    <vlan-id>1234</vlan-id>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>irb</name>
                    <unit>
                      <name>1234</name>
                      <family>
                        <inet>
                          <no-redirects />
                        </inet>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>VLAN1234</name>
                <vlan-id>1234</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <bridge-domains>
                  <domain>
                    <name>VLAN1234</name>
                    <vlan-id>1234</vlan-id>
                    <routing-interface>irb.1234</routing-interface>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>irb</name>
                    <unit>
                      <name>1234</name>
                      <family>
                        <inet>
                          <no-redirects />
                        </inet>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_vlan_icmp_redirects_state(vlan_number=1234, state=False)

    def test_set_icmp_redirect_state_false_already_set_dont_do_anything(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains>
                  <domain>
                    <vlan-id>1234</vlan-id>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>irb</name>
                    <unit>
                      <name>1234</name>
                      <family>
                        <inet>
                          <no-redirects />
                        </inet>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>VLAN1234</name>
                <vlan-id>1234</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>irb</name>
                <unit>
                  <name>4094</name>
                  <family>
                    <inet>
                      <no-redirects/>
                    </inet>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        self.switch.set_vlan_icmp_redirects_state(vlan_number=1234, state=False)

    def test_set_icmp_redirect_state_true_not_set_dont_do_anything(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains>
                  <domain>
                    <vlan-id>1234</vlan-id>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>irb</name>
                    <unit>
                      <name>1234</name>
                      <family>
                        <inet>
                          <no-redirects />
                        </inet>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>VLAN1234</name>
                <vlan-id>1234</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces/>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        self.switch.set_vlan_icmp_redirects_state(vlan_number=1234, state=True)

    def test_set_icmp_redirect_state_true_already_set_remove_statement(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains>
                  <domain>
                    <vlan-id>1234</vlan-id>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>irb</name>
                    <unit>
                      <name>1234</name>
                      <family>
                        <inet>
                          <no-redirects />
                        </inet>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>VLAN1234</name>
                <vlan-id>1234</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>irb</name>
                <unit>
                  <name>4094</name>
                  <family>
                    <inet>
                      <no-redirects/>
                    </inet>
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
                    <name>irb</name>
                    <unit>
                      <name>1234</name>
                      <family>
                        <inet>
                          <no-redirects operation="delete" />
                        </inet>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """))

        self.switch.set_vlan_icmp_redirects_state(vlan_number=1234, state=True)

    def test_set_icmp_redirect_unknow_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <bridge-domains>
                  <domain>
                    <vlan-id>1234</vlan-id>
                  </domain>
                </bridge-domains>
                <interfaces>
                  <interface>
                    <name>irb</name>
                    <unit>
                      <name>1234</name>
                      <family>
                        <inet>
                          <no-redirects />
                        </inet>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration())

        with self.assertRaises(UnknownVlan):
            self.switch.set_vlan_icmp_redirects_state(vlan_number=1234, state=False)

    def test_port_mode_access(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <bridge-domains/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>xe-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                          <interface-mode>access</interface-mode>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_mode("xe-0/0/6")

    def test_port_mode_access_with_no_mode_and_1_vlan_does_not_remove_it(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <vlan-id>2998</vlan-id>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <bridge-domains/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>xe-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                          <interface-mode>access</interface-mode>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_mode("xe-0/0/6")

    def test_set_access_vlan_on_interface_with_access_mode_and_no_vlan_succeeds_easily(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>access</interface-mode>
                    </bridge>
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
                    <name>xe-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                          <vlan-id>1000</vlan-id>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_vlan("xe-0/0/6", 1000)

    def test_set_access_vlan_on_interface_that_already_has_it_does_nothing(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>access</interface-mode>
                      <vlan-id>1000</vlan-id>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        self.switch.set_access_vlan("xe-0/0/6", 1000)

    def test_set_access_vlan_on_interface_that_has_no_port_mode_sets_it(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                    </bridge>
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
                    <name>xe-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                          <interface-mode>access</interface-mode>
                            <vlan-id>1000</vlan-id>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_vlan("xe-0/0/6", 1000)

    def test_set_access_vlan_on_interface_replaces_vlan_id(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </domain>
              <domain>
                <name>PATATE2</name>
                <vlan-id>2000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>access</interface-mode>
                      <vlan-id>2000</vlan-id>
                    </bridge>
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
                    <name>xe-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                          <vlan-id>1000</vlan-id>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_vlan("xe-0/0/6", 1000)

    def test_set_access_vlan_on_interface_in_trunk_mode_should_raise(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>trunk</interface-mode>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.set_access_vlan("xe-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Operation cannot be performed on a trunk mode interface"))

    def test_set_access_vlan_on_unknown_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>3333</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>access</interface-mode>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.set_access_vlan("xe-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Vlan 1000 not found"))

    def test_set_access_vlan_on_default_interface_works(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>xe-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                          <interface-mode>access</interface-mode>
                            <vlan-id>1000</vlan-id>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_vlan("xe-0/0/6", 1000)

    def test_set_access_mode_on_interface_replaces_trunk_info(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </domain>
              <domain>
                <name>PATATE2</name>
                <vlan-id>2000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>trunk</interface-mode>
                      <vlan-id-list>2000</vlan-id-list>
                      <vlan-id-list>2000-2000</vlan-id-list>
                    </bridge>
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
                    <name>xe-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                          <interface-mode>access</interface-mode>
                          <vlan-id-list operation="delete"/>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_access_mode("xe-0/0/6")

    def test_port_mode_trunk_with_no_port_mode_or_vlan_set_just_sets_the_port_mode(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>xe-0/0/6</name>
                  </interface>
                </interfaces>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <bridge-domains/>
        """))

        self.netconf_mock.should_receive("edit_config").once().with_args(target="candidate", config=is_xml("""
            <config>
              <configuration>
                <interfaces>
                  <interface>
                    <name>xe-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                          <interface-mode>trunk</interface-mode>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_trunk_mode("xe-0/0/6")

    def test_set_port_mode_trunk_from_access_removes_vlan_info(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>xe-0/0/6</name>
                  </interface>
                </interfaces>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>access</interface-mode>
                      <vlan-id>1000</vlan-id>
                    </bridge>
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
                    <name>xe-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                          <interface-mode>trunk</interface-mode>
                          <vlan-id operation="delete"/>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.set_trunk_mode("xe-0/0/6")

    def test_port_mode_trunk_already_in_trunk_mode_does_nothing(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>xe-0/0/6</name>
                  </interface>
                </interfaces>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>trunk</interface-mode>
                      <vlan-id-list>1000</vlan-id-list>
                      <vlan-id-list>1001</vlan-id-list>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <vlans/>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        self.switch.set_trunk_mode("xe-0/0/6")

    def test_add_trunk_vlan_on_interface_adds_to_the_list(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>trunk</interface-mode>
                      <vlan-id-list>2000</vlan-id-list>
                      <vlan-id-list>2100-2200</vlan-id-list>
                    </bridge>
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
                    <name>xe-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                          <vlan-id-list>1000</vlan-id-list>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.add_trunk_vlan("xe-0/0/6", 1000)

    def test_add_trunk_vlan_on_interface_that_has_no_port_mode_and_no_vlan_sets_it(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                    </bridge>
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
                    <name>xe-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                          <interface-mode>trunk</interface-mode>
                          <vlan-id-list>1000</vlan-id-list>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.add_trunk_vlan("xe-0/0/6", 1000)

    def test_add_trunk_vlan_on_interface_in_access_mode_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <vlan-id-list>500</vlan-id-list>
                      <interface-mode>access</interface-mode>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.add_trunk_vlan("xe-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Operation cannot be performed on a access mode interface"))

    def test_add_trunk_vlan_on_unknown_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>trunk</interface-mode>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(UnknownVlan) as expect:
            self.switch.add_trunk_vlan("xe-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Vlan 1000 not found"))

    def test_add_trunk_vlan_on_interface_that_already_has_it_does_nothing(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>PATATE</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>trunk</interface-mode>
                      <vlan-id-list>900-1100</vlan-id-list>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        self.switch.add_trunk_vlan("xe-0/0/6", 1000)

    def test_remove_ip_from_vlan(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>irb</name>
                  <unit>
                    <name>1234</name>
                    <family>
                      <inet>
                        <address>
                            <name>3.3.3.2/27</name>
                        </address>
                      </inet>
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
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                        <family>
                          <inet>
                            <address operation="delete">
                              <name>3.3.3.2/27</name>
                            </address>
                          </inet>
                        </family>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.remove_ip_from_vlan(vlan_number=1234, ip_network=IPNetwork("3.3.3.2/27"))

    def test_remove_ip_from_vlan_ip_not_found(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>irb</name>
                  <unit>
                    <name>1234</name>
                    <family>
                      <inet>
                        <address>
                            <name>4.4.4.2/27</name>
                        </address>
                      </inet>
                    </family>
                  </unit>
              </interface>
            </interfaces>
        """))

        with self.assertRaises(UnknownIP):
            self.switch.remove_ip_from_vlan(vlan_number=1234, ip_network=IPNetwork("3.3.3.2/27"))

    def test_remove_ip_from_vlan_unknown_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>irb</name>
                      <unit>
                        <name>1234</name>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration())

        with self.assertRaises(UnknownVlan):
            self.switch.remove_ip_from_vlan(vlan_number=1234, ip_network=IPNetwork("3.3.3.2/27"))

    def test_unset_interface_access_vlan_removes_the_vlan_id(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>xe-0/0/1</name>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
                <interfaces>
                  <interface>
                    <name>xe-0/0/1</name>
                      <unit>
                        <name>0</name>
                        <family>
                          <bridge>
                            <interface-mode>access</interface-mode>
                            <vlan-id>999</vlan-id>
                          </bridge>
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
                    <name>xe-0/0/1</name>
                      <unit>
                        <name>0</name>
                        <family>
                          <bridge>
                            <vlan-id operation="delete" />
                          </bridge>
                        </family>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.unset_interface_access_vlan("xe-0/0/1")

    def test_unset_interface_access_vlan_fails_when_not_set(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>xe-0/0/1</name>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
                <interfaces>
                  <interface>
                    <name>xe-0/0/1</name>
                      <unit>
                        <name>0</name>
                        <family>
                          <bridge>
                            <interface-mode>access</interface-mode>
                          </bridge>
                        </family>
                      </unit>
                  </interface>
                </interfaces>
            """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(AccessVlanNotSet) as expect:
            self.switch.unset_interface_access_vlan("xe-0/0/1")

        assert_that(str(expect.exception), equal_to("Access Vlan is not set on interface xe-0/0/1"))

    def test_unset_interface_access_vlan_unknown_interface_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                  <interface>
                    <name>xe-0/0/1</name>
                  </interface>
                </interfaces>
              </configuration>
            </filter>
        """))   .and_return(a_configuration())

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.unset_interface_access_vlan("xe-0/0/1")

        assert_that(str(expect.exception), equal_to("Unknown interface xe-0/0/1"))

    def test_get_interface(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces>
                    <interface>
                        <name>xe-0/0/1</name>
                    </interface>
                </interfaces>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces>
              <interface>
                <name>xe-0/0/1</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
            <bridge-domains/>
        """))

        interface = self.switch.get_interface('xe-0/0/1')

        assert_that(interface.name, equal_to("xe-0/0/1"))
        assert_that(interface.shutdown, equal_to(False))
        assert_that(interface.port_mode, equal_to(ACCESS))
        assert_that(interface.access_vlan, equal_to(None))
        assert_that(interface.trunk_native_vlan, equal_to(None))
        assert_that(interface.trunk_vlans, equal_to([]))
        assert_that(interface.auto_negotiation, equal_to(None))
        assert_that(interface.mtu, equal_to(None))

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
                          xe-0/0/1
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
                          xe-0/0/2
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
                <bridge-domains />
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <interfaces />
            <bridge-domains/>
        """))

        if1, if2 = self.switch.get_interfaces()

        assert_that(if1.name, equal_to("xe-0/0/1"))
        assert_that(if1.shutdown, equal_to(False))
        assert_that(if1.port_mode, equal_to(ACCESS))
        assert_that(if1.access_vlan, equal_to(None))
        assert_that(if1.trunk_native_vlan, equal_to(None))
        assert_that(if1.trunk_vlans, equal_to([]))

        assert_that(if2.name, equal_to("xe-0/0/2"))
        assert_that(if2.shutdown, equal_to(True))

    def test_get_nonexistent_interface_raises(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                    <filter>
                      <configuration>
                          <interfaces>
                            <interface>
                              <name>xe-0/0/INEXISTENT</name>
                            </interface>
                          </interfaces>
                        <bridge-domains/>
                      </configuration>
                    </filter>
                """)).and_return(a_configuration("""
                    <interfaces/>
                    <bridge-domains/>
                """))
        self.netconf_mock.should_receive("rpc").with_args(is_xml("""
                    <get-interface-information>
                      <terse/>
                    </get-interface-information>
                """)).and_return(an_rpc_response(textwrap.dedent("""
                    <interface-information style="terse">
                      <physical-interface>
                        <name>
                          xe-0/0/1
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
            self.switch.get_interface('xe-0/0/INEXISTENT')

        assert_that(str(expect.exception), equal_to("Unknown interface xe-0/0/INEXISTENT"))

    def test_get_unconfigured_interface_could_be_disabled(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                        <filter>
                          <configuration>
                              <interfaces>
                                <interface>
                                  <name>xe-0/0/27</name>
                                </interface>
                              </interfaces>
                            <bridge-domains/>
                          </configuration>
                        </filter>
                    """)).and_return(a_configuration("""
                        <interfaces/>
                        <bridge-domains/>
                    """))
        self.netconf_mock.should_receive("rpc").with_args(is_xml("""
                        <get-interface-information>
                          <terse/>
                        </get-interface-information>
                    """)).and_return(an_rpc_response(textwrap.dedent("""
                        <interface-information style="terse">
                          <physical-interface>
                            <name>
                              xe-0/0/27
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

        assert_that(self.switch.get_interface('xe-0/0/27').shutdown, equal_to(True))

    def test_remove_trunk_vlan_removes_the_vlan_lists_in_every_possible_way(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>VLAN_NAME</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>trunk</interface-mode>
                        <vlan-id-list>1000</vlan-id-list>
                        <vlan-id-list>1000-1001</vlan-id-list>
                        <vlan-id-list>999-1000</vlan-id-list>
                        <vlan-id-list>999-1001</vlan-id-list>
                        <vlan-id-list>998-1002</vlan-id-list>
                    </bridge>
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
                    <name>xe-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                            <vlan-id-list operation="delete">1000</vlan-id-list>
                            <vlan-id-list operation="delete">1000-1001</vlan-id-list>
                            <vlan-id-list>1001</vlan-id-list>
                            <vlan-id-list operation="delete">999-1000</vlan-id-list>
                            <vlan-id-list>999</vlan-id-list>
                            <vlan-id-list operation="delete">999-1001</vlan-id-list>
                            <vlan-id-list>999</vlan-id-list>
                            <vlan-id-list>1001</vlan-id-list>
                            <vlan-id-list operation="delete">998-1002</vlan-id-list>
                            <vlan-id-list>998-999</vlan-id-list>
                            <vlan-id-list>1001-1002</vlan-id-list>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.remove_trunk_vlan("xe-0/0/6", 1000)

    def test_remove_trunk_vlan_removes_the_vlan_even_if_referenced_by_name(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>VLAN_NAME</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>trunk</interface-mode>
                        <vlan-id-list>1000</vlan-id-list>
                        <vlan-id-list>VLAN_NAME</vlan-id-list>
                        <vlan-id-list>SOEMTHING</vlan-id-list>
                    </bridge>
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
                    <name>xe-0/0/6</name>
                    <unit>
                      <name>0</name>
                      <family>
                        <bridge>
                            <vlan-id-list operation="delete">1000</vlan-id-list>
                            <vlan-id-list operation="delete">VLAN_NAME</vlan-id-list>
                        </bridge>
                      </family>
                    </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>
        """)).and_return(an_ok_response())

        self.switch.remove_trunk_vlan("xe-0/0/6", 1000)

    def test_remove_trunk_vlan_not_in_lists_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>VLAN_NAME</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>trunk</interface-mode>
                        <vlan-id-list>500-999</vlan-id-list>
                        <vlan-id-list>1001-4000</vlan-id-list>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(TrunkVlanNotSet) as expect:
            self.switch.remove_trunk_vlan("xe-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Trunk Vlan is not set on interface xe-0/0/6"))

    def test_remove_trunk_vlan_on_access_with_the_correct_vlan_interface_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>VLAN_NAME</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <interface-mode>access</interface-mode>
                      <vlan-id-list>1000</vlan-id-list>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.remove_trunk_vlan("xe-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Operation cannot be performed on a access mode interface"))

    def test_remove_trunk_vlan_on_no_port_mode_interface_with_the_correct_vlan_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>VLAN_NAME</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
            <interfaces>
              <interface>
                <name>xe-0/0/6</name>
                <unit>
                  <name>0</name>
                  <family>
                    <bridge>
                      <vlan-id>1000</vlan-id>
                    </bridge>
                  </family>
                </unit>
              </interface>
            </interfaces>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(InterfaceInWrongPortMode) as expect:
            self.switch.remove_trunk_vlan("xe-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Operation cannot be performed on a access mode interface"))

    def test_remove_trunk_vlan_on_unknown_interface_raises(self):
        self.netconf_mock.should_receive("get_config").with_args(source="candidate", filter=is_xml("""
            <filter>
              <configuration>
                <interfaces/>
                <bridge-domains/>
              </configuration>
            </filter>
        """)).and_return(a_configuration("""
            <bridge-domains>
              <domain>
                <name>VLAN_NAME</name>
                <vlan-id>1000</vlan-id>
              </domain>
            </bridge-domains>
        """))

        self.netconf_mock.should_receive("edit_config").never()

        with self.assertRaises(UnknownInterface) as expect:
            self.switch.remove_trunk_vlan("xe-0/0/6", 1000)

        assert_that(str(expect.exception), contains_string("Unknown interface xe-0/0/6"))
