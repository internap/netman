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
from hamcrest import assert_that, equal_to, instance_of, contains_string, has_length
from ncclient.operations import RPCError
from ncclient.xml_ import to_ele

from netman.adapters.switches.juniper.base import Juniper
from netman.adapters.switches.juniper.mx import netconf
from netman.core.objects.access_groups import OUT, IN
from netman.core.objects.exceptions import VlanAlreadyExist, BadVlanNumber, BadVlanName
from netman.core.objects.switch_descriptor import SwitchDescriptor
from netman.core.switch_factory import RealSwitchFactory
from tests.adapters.switches.juniper_test import an_ok_response, is_xml, a_configuration


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
        longString = 'a' * 256
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
            """.format(longString))).and_raise(RPCError(to_ele(textwrap.dedent("""
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
            """.format(longString)))))

        with self.assertRaises(BadVlanName) as expect:
            self.switch.add_vlan(1000, longString)

        assert_that(str(expect.exception), equal_to("Vlan name is invalid"))

    def test_get_vlan_with_no_interfaces(self):
        self.switch.in_transaction = False
        self.netconf_mock.should_receive("get_config").with_args(source="running", filter=is_xml("""
                <filter>
                  <configuration>
                    <bridge-domains>
                      <bridge>
                        <vlan-id>10</vlan-id>
                      </bridge>
                    </bridge-domains>
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
        assert_that(vlan.ips, has_length(0))

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
                    <l3-interface>vlan.20</l3-interface>
                  </domain>
                  <domain>
                    <name>WITH-IF-MULTI-IP</name>
                    <vlan-id>40</vlan-id>
                    <l3-interface>vlan.70</l3-interface>
                  </domain>
                </bridge-domains>
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
