# Copyright 2018 Internap.
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
from ncclient.xml_ import to_ele, new_ele

from netman.adapters.switches.juniper.base import Juniper
from netman.adapters.switches.juniper.standard import JuniperCustomStrategies
from netman.core.objects.exceptions import VlanAlreadyExist, BadVlanNumber, BadVlanName, UnknownVlan


def netconf(switch_descriptor):
    return Juniper(switch_descriptor, custom_strategies=JuniperMXCustomStrategies())


class JuniperMXCustomStrategies(JuniperCustomStrategies):
    def add_update_vlans(self, update, number, name):
        update.add_vlan(self.vlan_update(number, name), "bridge-domains")

    def all_vlans(self):
        return new_ele("bridge-domains")

    def one_vlan_by_vlan_id(self, vlan_id):
        def m():
            return to_ele("""
                <bridge-domains>
                    <bridge>
                        <vlan-id>{}</vlan-id>
                    </bridge>
                </bridge-domains>
            """.format(vlan_id))

        return m

    def vlan_update(self, number, description):
        content = to_ele("""
            <domain>
                <name>VLAN{0}</name>
                <vlan-id>{0}</vlan-id>
            </domain>
        """.format(number))

        if description is not None:
            content.append(to_ele("<description>{}</description>".format(description)))
        return content

    def get_vlans(self, config):
        return config.xpath("data/configuration/bridge-domains/domain")

    def get_vlan_config(self, number, config):
        vlan_node = config.xpath("data/configuration/bridge-domains/domain/vlan-id[text()=\"{}\"]/..".format(number))

        try:
            return vlan_node[0]
        except IndexError:
            raise UnknownVlan(number)

    def manage_update_vlan_exception(self, message, number):
        if "being used by" in message:
            raise VlanAlreadyExist(number)
        elif "not within range" in message:
            if message.startswith("Value"):
                raise BadVlanNumber()
        elif "Must be a string" in message:
            raise BadVlanName()
        raise
