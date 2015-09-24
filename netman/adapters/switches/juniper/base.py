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

from ncclient import manager
from ncclient.operations import RPCError, TimeoutExpiredError
from ncclient.xml_ import new_ele, sub_ele, to_ele, to_xml
from netaddr import IPNetwork

from netman import regex
from netman.core.objects.access_groups import IN, OUT
from netman.core.objects.exceptions import LockedSwitch, VlanAlreadyExist, BadVlanNumber, BadVlanName, UnknownVlan, \
    InterfaceInWrongPortMode, UnknownInterface, AccessVlanNotSet, NativeVlanNotSet, TrunkVlanNotSet, VlanAlreadyInTrunk, \
    InterfaceSpanningTreeNotEnabled, InterfaceDescriptionNotSet, \
    BadBondNumber, BondAlreadyExist, UnknownBond, InterfaceNotInBond, OperationNotCompleted
from netman.core.objects.interface import Interface
from netman.core.objects.port_modes import ACCESS, TRUNK, BOND_MEMBER
from netman.core.objects.switch_base import SwitchBase
from netman.core.objects.vlan import Vlan
from netman.core.objects.bond import Bond


class Juniper(SwitchBase):

    def __init__(self, switch_descriptor, custom_strategies,
                 timeout=60):
        super(Juniper, self).__init__(switch_descriptor)
        self.timeout = timeout
        self.custom_strategies = custom_strategies
        self.netconf = None

        self.in_transaction = False

    def connect(self):
        self.netconf = manager.connect(
            host=self.switch_descriptor.hostname,
            username=self.switch_descriptor.username,
            password=self.switch_descriptor.password,
            hostkey_verify=False,
            device_params={'name': 'junos'},
            port=self.switch_descriptor.port or 830,
            timeout=self.timeout
        )

    def disconnect(self):
        try:
            self.netconf.close_session()
        except TimeoutExpiredError:
            pass

    def start_transaction(self):
        try:
            self.netconf.lock(target="candidate")
        except RPCError as e:
            if "configuration database modified" in e.message:
                self.rollback_transaction()
                self.netconf.lock(target="candidate")
            elif "Configuration database is already open" in e.message:
                raise LockedSwitch()
            else:
                raise
        self.in_transaction = True

    def end_transaction(self):
        self.in_transaction = False
        self.netconf.unlock(target="candidate")

    def rollback_transaction(self):
        self.netconf.discard_changes()

    def commit_transaction(self):
        try:
            self.netconf.commit()
        except RPCError as e:
            self.logger.info("An RPCError was raised : %s" % e)
            raise OperationNotCompleted(str(e).strip())

    def get_vlans(self):
        config = self.query(all_vlans, all_interfaces)

        vlan_list = []
        for vlan_node in config.xpath("data/configuration/vlans/vlan"):
            number_node = first(vlan_node.xpath("vlan-id"))
            if number_node is not None:
                vlan = Vlan(number=int(number_node.text))
                vlan_list.append(vlan)

                description_node = first(vlan_node.xpath("description"))
                if description_node is not None:
                    vlan.name = description_node.text

                l3_if_type, l3_if_name = get_l3_interface(vlan_node)
                if l3_if_name is not None:
                    interface_node = first(config.xpath("data/configuration/interfaces/interface/name[text()=\"{}\"]/.."
                                                        "/unit/name[text()=\"{}\"]/..".format(l3_if_type, l3_if_name)))
                    if interface_node is not None:
                        vlan.ips = parse_ips(interface_node)
                        vlan.access_groups[IN] = parse_inet_filter(interface_node, "input")
                        vlan.access_groups[OUT] = parse_inet_filter(interface_node, "output")

        return vlan_list

    def get_interfaces(self):
        config = self.query(all_interfaces, all_vlans)

        interface_list = []
        for if_node in config.xpath("data/configuration/interfaces/interface"):
            if value_of(if_node.xpath("name")) != "vlan":
                interface_list.append(self.node_to_interface(if_node, config))

        return interface_list

    def add_vlan(self, number, name=None):
        config = self.query(all_vlans)

        try:
            self.get_vlan_config(number, config)
            raise VlanAlreadyExist(number)
        except UnknownVlan:
            pass

        update = Update()
        update.add_vlan(vlan_update(number, name))

        try:
            self._push(update)
        except RPCError as e:
            if "being used by" in e.message:
                raise VlanAlreadyExist(number)
            elif "not within range" in e.message:
                if e.message.startswith("Value"):
                    raise BadVlanNumber()
                elif e.message.startswith("Length"):
                    raise BadVlanName()

            raise

    def remove_vlan(self, number):
        config = self.query(all_vlans, all_interfaces)

        vlan_node = self.get_vlan_config(number, config)
        vlan_name = first(vlan_node.xpath("name")).text

        update = Update()
        update.add_vlan(vlan_removal(vlan_name))

        l3_if_type, l3_if_name = get_l3_interface(vlan_node)
        if l3_if_name is not None:
            update.add_interface(interface_unit_interface_removal(l3_if_type, l3_if_name))

        for interface_node in config.xpath("data/configuration/interfaces/interface"):
            members_modifications = craft_members_modification_to_remove_vlan(interface_node, vlan_name, number)

            if len(members_modifications) > 0:
                update.add_interface(interface_vlan_members_update(
                    first(interface_node.xpath("name")).text,
                    first(interface_node.xpath("unit/name")).text,
                    members_modifications)
                )

        self._push(update)

    def set_access_mode(self, interface_id):
        update_attributes = []

        config = self.query(all_interfaces, all_vlans)

        interface_node = self.get_interface_config(interface_id, config)

        interface = self.node_to_interface(interface_node, config)

        if self.get_port_mode(interface_node) in (TRUNK, None):
            update_attributes.append(self.custom_strategies.set_interface_port_mode_update_element("access"))

        if len(interface.trunk_vlans) > 0:
            update_attributes.append(to_ele('<vlan operation="delete" />'))

        if interface.trunk_native_vlan is not None:
            update_attributes.append(to_ele('<native-vlan-id operation="delete" />'))

        if len(update_attributes) > 0:
            update = Update()
            update.add_interface(interface_update(interface_id, "0", update_attributes))

            self._push(update)

    def set_trunk_mode(self, interface_id):
        update_attributes = []

        interface = self.get_interface(interface_id)

        if interface.port_mode is ACCESS:
            update_attributes.append(self.custom_strategies.set_interface_port_mode_update_element("trunk"))

        if interface.access_vlan is not None:
            update_attributes.append(to_ele('<vlan operation="delete" />'))

        if len(update_attributes) > 0:
            update = Update()
            update.add_interface(interface_update(interface_id, "0", update_attributes))

            self._push(update)

    def set_access_vlan(self, interface_id, vlan):
        update_attributes = []
        update_vlan_members = []

        config = self.query(all_interfaces, all_vlans)

        self.get_vlan_config(vlan, config)

        interface_node = self.get_interface_config(interface_id, config)
        interface = self.node_to_interface(interface_node, config)

        if interface.port_mode == TRUNK:
            raise InterfaceInWrongPortMode("trunk")
        elif self.get_port_mode(interface_node) is None:
            update_attributes.append(self.custom_strategies.set_interface_port_mode_update_element("access"))

        if interface.access_vlan != vlan:
            for members in interface_node.xpath("unit/family/ethernet-switching/vlan/members"):
                update_vlan_members.append(to_ele('<members operation="delete">%s</members>' % members.text))
            update_vlan_members.append(to_ele("<members>%s</members>" % vlan))

        if update_attributes or update_vlan_members:
            update = Update()
            update.add_interface(interface_update(interface_id, "0", update_attributes, update_vlan_members))

            try:
                self._push(update)
            except RPCError as e:
                if "No vlan matches vlan tag" in e.message:
                    raise UnknownVlan(vlan)
                raise

    def remove_access_vlan(self, interface_id):
        interface = self.get_interface(interface_id)

        if interface.port_mode == TRUNK:
            raise InterfaceInWrongPortMode("trunk")

        if interface.access_vlan is not None:
            update = Update()
            update.add_interface(interface_update(interface_id, "0", [to_ele('<vlan operation="delete" />')]))

            self._push(update)
        else:
            raise AccessVlanNotSet(interface_id)

    def configure_native_vlan(self, interface_id, vlan):
        update_attributes = []

        config = self.query(all_interfaces, all_vlans)

        self.get_vlan_config(vlan, config)

        interface_node = self.get_interface_config(interface_id, config)

        interface = self.node_to_interface(interface_node, config)

        actual_port_mode = self.get_port_mode(interface_node)
        if actual_port_mode is ACCESS:
            raise InterfaceInWrongPortMode("access")
        elif actual_port_mode is None:
            update_attributes.append(self.custom_strategies.set_interface_port_mode_update_element("trunk"))

        if vlan in interface.trunk_vlans:
            raise VlanAlreadyInTrunk(vlan)
        elif interface.trunk_native_vlan != vlan:
            update_attributes.append(to_ele("<native-vlan-id>%s</native-vlan-id>" % vlan))

        if update_attributes:

            update = Update()
            update.add_interface(interface_update(interface_id, "0", update_attributes))

            try:
                self._push(update)
            except RPCError as e:
                if "No vlan matches vlan tag" in e.message:
                    raise UnknownVlan(vlan)
                raise

    def remove_native_vlan(self, interface_id):
        interface = self.get_interface(interface_id)

        if interface.trunk_native_vlan is None:
            raise NativeVlanNotSet(interface_id)

        update = Update()
        update.add_interface(interface_update(interface_id, "0", [to_ele("<native-vlan-id operation=\"delete\" />")]))

        self._push(update)

    def add_trunk_vlan(self, interface_id, vlan):
        config = self.query(all_interfaces, all_vlans)

        self.get_vlan_config(vlan, config)

        interface_node = self.get_interface_config(interface_id, config)

        interface = self.node_to_interface(interface_node, config)

        actual_port_mode = self.get_port_mode(interface_node)

        if actual_port_mode is ACCESS or interface.access_vlan is not None:
            raise InterfaceInWrongPortMode("access")

        if vlan not in interface.trunk_vlans:
            update = Update()
            update.add_interface(interface_update(
                interface_id, "0",
                [self.custom_strategies.set_interface_port_mode_update_element("trunk")] if actual_port_mode is None else None,
                [to_ele("<members>%s</members>" % vlan)]
            ))

            self._push(update)

    def remove_trunk_vlan(self, interface_id, vlan):
        config = self.query(all_interfaces, all_vlans)
        interface_node = self.get_interface_config(interface_id, config)
        interface = self.node_to_interface(interface_node, config)

        if interface.port_mode is ACCESS:
            raise InterfaceInWrongPortMode("access")

        vlan_node = self.get_vlan_config(vlan, config)
        vlan_name = first(vlan_node.xpath("name")).text

        modifications = craft_members_modification_to_remove_vlan(interface_node, vlan_name, vlan)
        if len(modifications) == 0:
            raise TrunkVlanNotSet(interface_id)

        update = Update()
        update.add_interface(interface_update(interface_id, "0", vlan_members=modifications))

        self._push(update)

    def set_interface_description(self, interface_id, description):
        update = Update()
        update.add_interface(interface_main_update(interface_id, [
            to_ele("<description>%s</description>" % description)
        ]))

        try:
            self._push(update)
        except RPCError as e:
            self.logger.info("actual setting error was %s" % e)
            raise UnknownInterface(interface_id)

    def remove_interface_description(self, interface_id):
        update = Update()
        update.add_interface(interface_main_update(interface_id, [
            to_ele("<description operation=\"delete\" />")
        ]))

        try:
            self._push(update)
        except RPCError as e:
            if e.severity == "warning":
                raise InterfaceDescriptionNotSet(interface_id)
            else:
                raise UnknownInterface(interface_id)

    def edit_interface_spanning_tree(self, interface_id, edge=None):
        config = self.query(one_interface(interface_id), one_protocol_interface("rstp", interface_id))
        self.get_interface_config(interface_id, config)

        if edge is not None:
            modifications = _compute_edge_state_modifications(interface_id, edge, config)

            if modifications:
                update = Update()
                update.add_protocol_interface("rstp", to_ele("""
                   <interface>
                     <name>{}</name>
                     {}
                   </interface>
                """.format(interface_id, "".join(modifications))))

                self._push(update)

    def shutdown_interface(self, interface_id):
        update = Update()
        update.add_interface(interface_main_update(interface_id, [
            to_ele("<disable />")
        ]))

        try:
            self._push(update)
        except RPCError as e:
            self.logger.info("actual setting error was %s" % e)
            raise UnknownInterface(interface_id)

    def openup_interface(self, interface_id):
        update = Update()
        update.add_interface(interface_main_update(interface_id, [
            to_ele("<enable />")
        ]))

        try:
            self._push(update)
        except RPCError as e:
            self.logger.info("actual setting error was %s" % e)
            raise UnknownInterface(interface_id)

    def enable_lldp(self, interface_id, enabled):
        config = self.query(one_interface(interface_id), one_protocol_interface("lldp", interface_id))
        self.get_interface_config(interface_id, config)

        update_ele = None
        disabled_node = first(config.xpath("data/configuration/protocols/lldp/interface/name"
                                           "[text()=\"{0:s}\"]/../disable".format(interface_id)))
        if enabled:
            update_ele = protocol_interface_update(interface_id)
            if disabled_node is not None:
                update_ele.append(to_ele('<disable operation="delete"/>'))
        elif not enabled and disabled_node is None:
            update_ele = protocol_interface_update(interface_id)
            update_ele.append(to_ele('<disable/>'))

        if update_ele:
            update = Update()
            update.add_protocol_interface("lldp", update_ele)
            self._push(update)

    def add_bond(self, number):
        config = self.query(one_interface(bond_name(number)))
        if len(config.xpath("data/configuration/interfaces/interface")) > 0:
            raise BondAlreadyExist(number)

        update = Update()
        update.add_interface(bond_update(number, bond_lacp_options()))

        try:
            self._push(update)
        except RPCError as e:
            if "device value outside range" in e.message:
                raise BadBondNumber()

            raise

    def remove_bond(self, number):
        config = self.query(all_interfaces, one_protocol_interface("rstp", bond_name(number)))
        self.get_bond_config(number, config)

        update = Update()
        update.add_interface(interface_removal(bond_name(number)))

        rstp_node = first(config.xpath("data/configuration/protocols/rstp/interface/name[text()=\"{0:s}\"]/..".format(bond_name(number))))
        if rstp_node is not None:
            update.add_protocol_interface("rstp", rstp_interface_removal(bond_name(number)))

        for interface_node in self.get_bond_slaves_config(number, config):
            interface_name = first(interface_node.xpath("name")).text
            update.add_interface(free_from_bond_operation(interface_name))

        self._push(update)

    def add_interface_to_bond(self, interface, bond_id):
        config = self.query(all_interfaces, all_vlans, rstp_protocol_interfaces)
        bond = self.node_to_bond(self.get_bond_config(bond_id, config), config)
        self.get_interface_config(interface, config=config)

        update = Update()
        self.custom_strategies.add_enslave_to_bond_operations(update, interface, bond)

        for name_node in config.xpath("data/configuration/protocols/rstp/interface/name[starts-with(text(),'{}')]".format(interface)):
            update.add_protocol_interface("rstp", rstp_interface_removal(name_node.text))

        self._push(update)

    def remove_interface_from_bond(self, interface):
        config = self.query(all_interfaces)
        node = self.get_interface_config(interface, config)

        if len(node.xpath('ether-options/ieee-802.3ad')) is 0:
            raise InterfaceNotInBond

        update = Update()
        update.add_interface(free_from_bond_operation(interface))
        self._push(update)

    def set_bond_link_speed(self, number, speed):
        config = self.query(all_interfaces)
        self.get_bond_config(number, config)

        update = Update()
        update.add_interface(bond_update(number, bond_link_speed(speed)))

        self.custom_strategies.add_update_bond_members_speed_operations(
            update,
            self.get_bond_slaves_config(number, config),
            speed
        )

        self._push(update)

    def get_bond(self, number):
        config = self.query(all_interfaces, all_vlans)

        bond_node = self.get_bond_config(number, config)
        return self.node_to_bond(bond_node, config, self.get_bond_slaves_config(
            value_of(bond_node.xpath("name"), transformer=bond_number), config))

    def get_bonds(self):
        config = self.query(all_interfaces, all_vlans)
        bond_nodes = config.xpath("data/configuration/interfaces/interface/aggregated-ether-options/..")
        return [
            self.node_to_bond(node, config, self.get_bond_slaves_config(
                value_of(node.xpath("name"), transformer=bond_number), config))
            for node in bond_nodes]

    def set_bond_description(self, number, description):
        return self.set_interface_description(bond_name(number), description)

    def remove_bond_description(self, number):
        return self.remove_interface_description(bond_name(number))

    def set_bond_trunk_mode(self, number):
        return self.set_trunk_mode(bond_name(number))

    def set_bond_access_mode(self, number):
        return self.set_access_mode(bond_name(number))

    def add_bond_trunk_vlan(self, number, vlan):
        return self.add_trunk_vlan(bond_name(number), vlan)

    def remove_bond_trunk_vlan(self, number, vlan):
        return self.remove_trunk_vlan(bond_name(number), vlan)

    def configure_bond_native_vlan(self, number, vlan):
        return self.configure_native_vlan(bond_name(number), vlan)

    def remove_bond_native_vlan(self, number):
        return self.remove_native_vlan(bond_name(number))

    def edit_bond_spanning_tree(self, number, edge=None):
        return self.edit_interface_spanning_tree(bond_name(number), edge=edge)

    def _push(self, configuration):
        config = new_ele('config')
        config.append(configuration.root)

        self.logger.info("Sending edit : %s" % to_xml(config))
        try:
            self.netconf.edit_config(target="candidate", config=config)
        except RPCError as e:
            self.logger.info("An RPCError was raised : %s" % e)
            raise

    def query(self, *args):
        filter_node = new_ele("filter")
        conf = sub_ele(filter_node, "configuration")
        for arg in args:
            conf.append(arg())
        return self.netconf.get_config(source="candidate" if self.in_transaction else "running", filter=filter_node)

    def get_interface(self, interface_id):
        config = self.query(all_interfaces, all_vlans)
        interface_node = self.get_interface_config(interface_id, config)

        return self.node_to_interface(interface_node, config)

    def get_interface_config(self, interface_id, config=None):
        config = config or self.query(one_interface(interface_id))
        interface_node = first(config.xpath(
            "data/configuration/interfaces/interface/name[text()=\"{0:s}\"]/..".format(interface_id)))
        if interface_node is None:
            raise UnknownInterface(interface_id)
        return interface_node

    def get_vlan_config(self, number, config):
        vlan_node = first(config.xpath("data/configuration/vlans/vlan/vlan-id[text()=\"%s\"]/.." % number))
        if vlan_node is None:
            raise UnknownVlan(number)
        return vlan_node

    def get_bond_config(self, number, config):
        interface_node = first(config.xpath("data/configuration/interfaces/interface/name[text()=\"%s\"]/.." % bond_name(number)))
        if interface_node is None:
            raise UnknownBond(number)
        return interface_node

    def get_bond_slaves_config(self, bond_id, config=None):
        config = config or self.query(all_interfaces)

        return config.xpath(
            'data/configuration/interfaces/interface/ether-options/'
            'ieee-802.3ad/bundle[text()=\"{0}\"]/../../..'.format(
                bond_name(bond_id)))

    def get_port_mode(self, interface_node):
        if get_bond_master(interface_node) is not None:
            return BOND_MEMBER
        actual_port_mode_node = first(self.custom_strategies.get_port_mode_node_in_inteface_node(interface_node))
        if actual_port_mode_node is None:
            return None
        else:
            return {"access": ACCESS, "trunk": TRUNK}[actual_port_mode_node.text]

    def node_to_interface(self, interface_node, config):
        interface = Interface()
        interface.bond_master = get_bond_master(interface_node)
        interface.port_mode = self.get_port_mode(interface_node) or ACCESS
        vlans = list_vlan_members(interface_node, config)
        if interface.port_mode is ACCESS:
            interface.access_vlan = first(vlans)
        else:
            interface.trunk_vlans = vlans
        interface.trunk_native_vlan = value_of(interface_node.xpath("unit/family/ethernet-switching/native-vlan-id"), transformer=int)
        interface.name = value_of(interface_node.xpath("name"))
        interface.shutdown = first(interface_node.xpath("disable")) is not None
        return interface

    def node_to_bond(self, bond_node, config, member_nodes=None):
        member_nodes = member_nodes or []
        return Bond(
            number=value_of(bond_node.xpath("name"), transformer=bond_number),
            interface=self.node_to_interface(bond_node, config),
            link_speed=first_text(bond_node.xpath("aggregated-ether-options/link-speed")),
            members=[first_text(member.xpath('name')) for member in member_nodes]
        )


def all_vlans():
    return new_ele("vlans")


def all_interfaces():
    return new_ele("interfaces")


def one_interface(interface_id):
    def m():
        return to_ele("""
            <interfaces>
                <interface>
                    <name>%s</name>
                </interface>
            </interfaces>
        """ % interface_id)

    return m


def one_vlan(vlan_name):
    def m():
        return to_ele("""
            <vlans>
                <vlan>
                    <name>%s</name>
                </vlan>
            </vlans>
        """ % vlan_name)

    return m


def rstp_protocol_interfaces():
    return to_ele("""
        <protocols>
          <rstp>
            <interface />
          </rstp>
        </protocols>
    """)


def one_protocol_interface(protocol, interface_id):
    def m():
        return to_ele("""
            <protocols>
              <{protocol}>
                <interface>
                    <name>{}</name>
                </interface>
              </{protocol}>
            </protocols>
        """.format(interface_id, protocol=protocol))

    return m


class Update(object):
    def __init__(self):
        self.root = new_ele("configuration")
        self.vlans_root = None
        self.interfaces_root = None
        self.protocols_root = None
        self.sub_protocol_roots = {}

    def add_vlan(self, vlan):
        if self.vlans_root is None:
            self.vlans_root = sub_ele(self.root, "vlans")
        self.vlans_root.append(vlan)

    def add_interface(self, interface):
        if self.interfaces_root is None:
            self.interfaces_root = sub_ele(self.root, "interfaces")
        self.interfaces_root.append(interface)

    def add_protocol(self, protocol):
        if self.protocols_root is None:
            self.protocols_root = sub_ele(self.root, "protocols")
        self.protocols_root.append(protocol)

    def add_protocol_interface(self, protocol, interface):
        if protocol not in self.sub_protocol_roots:
            self.sub_protocol_roots[protocol] = to_ele("<{0}></{0}>".format(protocol))
            self.add_protocol(self.sub_protocol_roots[protocol])
        self.sub_protocol_roots[protocol].append(interface)


def bond_update(number, *aggregated_ether_options):
    content = to_ele("""
        <interface>
            <name>{0}</name>
            <aggregated-ether-options>
            </aggregated-ether-options>
        </interface>
    """.format(bond_name(number)))

    aggregated_ether_options_node = first(content.xpath("//aggregated-ether-options"))
    map(aggregated_ether_options_node.append, aggregated_ether_options)

    return content


def bond_lacp_options():
    return to_ele("""
        <lacp>
            <active/>
            <periodic>slow</periodic>
        </lacp>
    """)


def bond_link_speed(link_speed):
    return to_ele("""
        <link-speed>{0}</link-speed>
    """.format(link_speed))


def vlan_update(number, description):
    content = to_ele("""
        <vlan>
            <name>VLAN{0}</name>
            <vlan-id>{0}</vlan-id>
        </vlan>
    """.format(number))

    if description is not None:
        content.append(to_ele("<description>%s</description>" % description))
    return content


def interface_removal(name):
    return to_ele("""
        <interface operation="delete">
            <name>%s</name>
        </interface>""" % name)


def vlan_removal(name):
    return to_ele("""
        <vlan operation="delete">
            <name>%s</name>
        </vlan>""" % name)


def interface_unit_interface_removal(interface, unit):
    return to_ele("""
        <interface>
          <name>{}</name>
          <unit operation="delete">
            <name>{}</name>
          </unit>
        </interface>
        """.format(interface, unit))


def rstp_interface_removal(interface_id):
    return to_ele("""
        <interface operation="delete" >
            <name>%s</name>
        </interface>
        """ % interface_id)


def interface_vlan_members_update(name, unit, members_modification):
    content = to_ele("""
        <interface>
            <name>%s</name>
            <unit>
                <name>%s</name>
                <family>
                    <ethernet-switching>
                        <vlan />
                    </ethernet-switching>
                </family>
            </unit>
        </interface>
        """ % (name, unit))

    vlan_node = first(content.xpath("//vlan"))
    for m in members_modification:
        vlan_node.append(m)

    return content


def interface_update(name, unit, attributes=None, vlan_members=None):
    content = to_ele("""
        <interface>
            <name>%s</name>
            <unit>
                <name>%s</name>
                <family>
                    <ethernet-switching>
                    </ethernet-switching>
                </family>
            </unit>
        </interface>
        """ % (name, unit))
    ethernet_switching_node = first(content.xpath("//ethernet-switching"))

    for attribute in (attributes if attributes is not None else []):
        ethernet_switching_node.append(attribute)

    if vlan_members:
        vlan = new_ele("vlan")
        for attribute in vlan_members:
            vlan.append(attribute)
        ethernet_switching_node.append(vlan)

    return content


def interface_main_update(name, attributes):
    content = to_ele("""
        <interface>
            <name>%s</name>
        </interface>
        """ % name)

    for attribute in (attributes if attributes is not None else []):
        content.append(attribute)

    return content


def first(node):
    return node[0] if node else None


def first_text(node):
    return node[0].text if node else None


def parse_range(r):
    if regex.match("(\d+)-(\d+)", r):
        return range(int(regex[0]), int(regex[1]) + 1)
    elif regex.match("(\d+)", r):
        return [int(regex[0])]
    return []


def to_range(number_list):
    if len(number_list) > 1:
        return "%s-%s" % (number_list[0], number_list[-1])
    else:
        return str(number_list[0])


def get_l3_interface(vlan_node):
    if_name_node = first(vlan_node.xpath("l3-interface"))
    if if_name_node is not None:
        return if_name_node.text.split(".")
    else:
        return None, None


def parse_ips(interface_unit_node):
    return sorted(
        [IPNetwork(ip_node.text) for ip_node in interface_unit_node.xpath("family/inet/address/name")],
        key=lambda ip: (ip.value, ip.prefixlen)
    )


def parse_inet_filter(interface_unit_node, direction):
    val = None
    ac_in_node = first(interface_unit_node.xpath("family/inet/filter/%s/filter-name" % direction))
    if ac_in_node is not None:
        val = ac_in_node.text
    return val


def bond_name(number):
    return "ae{0}".format(number)


def bond_number(name):
    return int(name[2:])


def craft_members_modification_to_remove_vlan(interface_node, vlan_name, number):
    members_modifications = []
    for vlan_members_node in interface_node.xpath("unit/family/ethernet-switching/vlan/members"):
        if vlan_members_node.text == vlan_name:
            members_modifications.append(to_ele("<members operation=\"delete\">%s</members>" % vlan_members_node.text))
        else:
            vlan_list = parse_range(vlan_members_node.text)
            if number in vlan_list:
                members_modifications.append(to_ele("<members operation=\"delete\">%s</members>" % vlan_members_node.text))

                below = vlan_list[:vlan_list.index(number)]
                if len(below) > 0:
                    members_modifications.append(to_ele("<members>%s</members>" % to_range(below)))

                above = vlan_list[vlan_list.index(number) + 1:]
                if len(above) > 0:
                    members_modifications.append(to_ele("<members>%s</members>" % to_range(above)))

    return members_modifications


def free_from_bond_operation(interface_name):
    return to_ele("""
        <interface>
            <name>{0}</name>
            <ether-options>
                <ieee-802.3ad operation=\"delete\" />
            </ether-options>
        </interface>
        """.format(interface_name))


def interface_replace(interface_name, *ether_options):
    content = to_ele("""
        <interface operation=\"replace\">
            <name>{0}</name>
            <ether-options>
            </ether-options>
        </interface>
    """.format(interface_name))

    ether_options_node = first(content.xpath("//ether-options"))
    map(ether_options_node.append, ether_options)

    return content


def interface_speed(speed):
    return to_ele("""
        <speed>
            <ethernet-{0}/>
        </speed>
    """.format(speed))


def interface_speed_update(interface_name, speed):
    return to_ele("""
        <interface>
            <name>{0}</name>
            <ether-options>
                <speed>
                    <ethernet-{1}/>
                </speed>
            </ether-options>
        </interface>
    """.format(interface_name, speed))

def protocol_interface_update(name):
    return to_ele("""
        <interface>
          <name>{}</name>
        </interface>
    """.format(name))

def list_vlan_members(interface_node, config):
    vlans = set()
    for members in interface_node.xpath("unit/family/ethernet-switching/vlan/members"):
        vlan_id = value_of(config.xpath('data/configuration/vlans/vlan/name[text()="%s"]/../vlan-id' % members.text), transformer=int)
        if vlan_id:
            vlans = vlans.union([vlan_id])
        else:
            vlans = vlans.union(parse_range(members.text))
    return sorted(vlans)


def get_bond_master(interface_node):
    return value_of(
        interface_node.xpath('ether-options/ieee-802.3ad/bundle'),
        transformer=bond_number)


def value_of(xpath_result, transformer=None):
    node = first(xpath_result)
    if node is not None:
        return node.text if transformer is None else transformer(node.text)
    else:
        return None


def _compute_edge_state_modifications(interface_id, edge, config):
    modifications = []
    rstp_node = first(config.xpath("data/configuration/protocols/rstp/interface/name[text()=\"{0:s}\"]/.."
                                   .format(interface_id)))
    if rstp_node is not None:
        edge_node = first(rstp_node.xpath("edge"))
        no_root_port_node = first(rstp_node.xpath("no-root-port"))

        if edge is True:
            if edge_node is None:
                modifications.append("<edge />")
            if no_root_port_node is None:
                modifications.append("<no-root-port />")
        elif edge is False:
            if edge_node is not None:
                modifications.append("<edge operation=\"delete\" />")
            if no_root_port_node is not None:
                modifications.append("<no-root-port operation=\"delete\" />")
    return modifications
