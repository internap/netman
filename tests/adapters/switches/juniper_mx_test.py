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
from hamcrest import assert_that, equal_to, instance_of, contains_string
from ncclient.operations import RPCError
from ncclient.xml_ import to_ele
from netaddr import IPNetwork

from netman.adapters.switches.juniper.base import Juniper
from netman.adapters.switches.juniper.mx import netconf
from netman.core.objects.exceptions import VlanAlreadyExist, BadVlanNumber, BadVlanName, UnknownVlan, IPAlreadySet, \
    IPNotAvailable
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

    def test_add_ip_to_vlan(self):
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
                            </address>
                          </inet>
                        </family>
                      </unit>
                  </interface>
                </interfaces>
              </configuration>
            </config>""")).and_return(an_ok_response())

        self.switch.add_ip_to_vlan(vlan_number=1234, ip_network=IPNetwork("3.3.3.2/27"))

    def test_add_ip_to_vlan_unknown_vlan_raises(self):
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
            self.switch.add_ip_to_vlan(vlan_number=1234, ip_network=IPNetwork("3.3.3.2/27"))

    def test_add_ip_to_vlan_ip_already_exists_in_vlan_raises(self):
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

        with self.assertRaises(IPAlreadySet):
            self.switch.add_ip_to_vlan(vlan_number=1234, ip_network=IPNetwork("3.3.3.2/27"))

    def test_add_ip_to_vlan_ip_already_exists_in_another_vlan_raises(self):
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

        self.netconf_mock.should_receive("edit_config").once().and_raise(RPCError(to_ele(textwrap.dedent("""
            <rpc-error xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:junos="http://xml.juniper.net/junos/11.4R1/junos" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
            <error-type>protocol</error-type>
            <error-tag>operation-failed</error-tag>
            <error-severity>error</error-severity>
            <source-daemon>
            dcd
            </source-daemon>
            <error-message>
            Overlapping subnet is configred under irb
            </error-message>
            </rpc-error>"""))))

        with self.assertRaises(IPNotAvailable):
            self.switch.add_ip_to_vlan(vlan_number=1234, ip_network=IPNetwork("2.2.3.2/27"))
