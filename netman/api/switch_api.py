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

from flask import request

from netman.api.api_utils import BadRequest, to_response
from netman.api.objects import bond, interface, vlan
from netman.api.switch_api_base import SwitchApiBase
from netman.api.validators import Switch, is_boolean, is_vlan_number, Interface, Vlan, resource, content, is_ip_network, \
    IPNetworkResource, is_access_group_name, Direction, is_vlan, is_bond, Bond, \
    is_bond_link_speed, is_bond_number, is_description, is_vrf_name, \
    is_vrrp_group, VrrpGroup, is_dict_with, optional, is_type, is_int, is_unincast_rpf_mode
from netman.core.objects.interface_states import OFF, ON


class SwitchApi(SwitchApiBase):

    def hook_to(self, server):
        server.add_url_rule('/switches/<hostname>/versions', view_func=self.get_versions, methods=['GET'])
        server.add_url_rule('/switches/<hostname>/vlans', view_func=self.get_vlans, methods=['GET'])
        server.add_url_rule('/switches/<hostname>/vlans', view_func=self.add_vlan, methods=['POST'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>', view_func=self.get_vlan, methods=['GET'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>', view_func=self.remove_vlan, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/interfaces', view_func=self.get_vlan_interfaces, methods=['GET'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/ips', view_func=self.add_ip, methods=['POST'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/ips/<path:ip_network>', view_func=self.remove_ip, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/vrrp-groups', view_func=self.add_vrrp_group, methods=['POST'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/vrrp-groups/<vrrp_group_id>', view_func=self.remove_vrrp_group, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/access-groups/<direction>', view_func=self.set_vlan_access_group, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/access-groups/<direction>', view_func=self.unset_vlan_access_group, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/vrf-forwarding', view_func=self.set_vlan_vrf, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/vrf-forwarding', view_func=self.unset_vlan_vrf, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/dhcp-relay-server', view_func=self.add_dhcp_relay_server, methods=['POST'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/dhcp-relay-server/<ip_network>', view_func=self.remove_dhcp_relay_server, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/arp-routing', view_func=self.set_vlan_arp_routing_state, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/icmp-redirects', view_func=self.set_vlan_icmp_redirects_state, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/ntp', view_func=self.set_vlan_ntp_state, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/unicast-rpf-mode', view_func=self.set_vlan_unicast_rpf_mode, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/vlans/<vlan_number>/unicast-rpf-mode', view_func=self.unset_vlan_unicast_rpf_mode, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/interfaces', view_func=self.get_interfaces, methods=['GET'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>', view_func=self.reset_interface, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>', view_func=self.get_interface, methods=['GET'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/shutdown', view_func=self.set_shutdown_state, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/shutdown', view_func=self.unset_shutdown_state, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/port-mode', view_func=self.set_port_mode, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/access-vlan', view_func=self.set_access_vlan, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/access-vlan', view_func=self.unset_interface_access_vlan, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/trunk-vlans', view_func=self.add_trunk_vlan, methods=['POST'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/trunk-vlans/<vlan_number>', view_func=self.remove_trunk_vlan, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/trunk-native-vlan', view_func=self.set_interface_native_vlan, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/trunk-native-vlan', view_func=self.unset_interface_native_vlan, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/bond-master', view_func=self.add_interface_to_bond, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/bond-master', view_func=self.remove_interface_from_bond, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/description', view_func=self.set_interface_description, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/description', view_func=self.unset_interface_description, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/spanning-tree', view_func=self.edit_interface_spanning_tree, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/lldp', view_func=self.set_interface_lldp_state, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/auto-negotiation', view_func=self.set_interface_auto_negotiation_state, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/auto-negotiation', view_func=self.unset_interface_auto_negotiation_state, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/mtu', view_func=self.set_interface_mtu, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/interfaces/<path:interface_id>/mtu', view_func=self.unset_interface_mtu, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/bonds', view_func=self.get_bonds, methods=['GET'])
        server.add_url_rule('/switches/<hostname>/bonds', view_func=self.add_bond, methods=['POST'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>', view_func=self.get_bond, methods=['GET'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>', view_func=self.remove_bond, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>/link-speed', view_func=self.set_bond_link_speed, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>/port-mode', view_func=self.set_bond_port_mode, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>/access-vlan', view_func=self.set_bond_access_vlan, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>/access-vlan', view_func=self.remove_bond_access_vlan, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>/trunk-vlans', view_func=self.add_bond_trunk_vlan, methods=['POST'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>/trunk-vlans/<vlan_number>', view_func=self.remove_bond_trunk_vlan, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>/trunk-native-vlan', view_func=self.set_bond_native_vlan, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>/trunk-native-vlan', view_func=self.unset_bond_native_vlan, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>/description', view_func=self.set_bond_description, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>/description', view_func=self.unset_bond_description, methods=['DELETE'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>/spanning-tree', view_func=self.edit_bond_spanning_tree, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>/mtu', view_func=self.set_bond_mtu, methods=['PUT'])
        server.add_url_rule('/switches/<hostname>/bonds/<bond_number>/mtu', view_func=self.unset_bond_mtu, methods=['DELETE'])
        return self

    @to_response
    @resource(Switch)
    def get_versions(self, switch):
        """
        Displays various hardware and software versions about the switch

        :arg str hostname: Hostname or IP of the switch
        :code 200 OK:

        Example output:

        .. literalinclude:: ../doc_config/api_samples/get_switch_hostname_versions.json
            :language: json

        """

        return 200, switch.get_versions()

    @to_response
    @resource(Switch)
    def get_vlans(self, switch):
        """
        Displays informations about all VLANs

        :arg str hostname: Hostname or IP of the switch
        :code 200 OK:

        Example output:

        .. literalinclude:: ../doc_config/api_samples/get_switch_hostname_vlans.json
            :language: json

        """
        vlans = sorted(switch.get_vlans(), key=lambda x: x.number)

        return 200, [vlan.to_api(v) for v in vlans]

    @to_response
    @resource(Switch, Vlan)
    def get_vlan_interfaces(self, switch, vlan_number):
        """
        Displays interfaces use in a VLAN

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        :code 200 OK:

        Example output:

        .. literalinclude:: ../doc_config/api_samples/get_switch_hostname_vlans_vlan_interfaces.json
            :language: json

        """

        return 200, switch.get_vlan_interfaces(vlan_number)

    @to_response
    @resource(Switch, Vlan)
    def get_vlan(self, switch, vlan_number):
        """
        Displays informations about one VLAN

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        :code 200 OK:

        Example output:

        .. literalinclude:: ../doc_config/api_samples/get_switch_hostname_vlans_vlan.json
            :language: json

        """

        return 200, vlan.to_api(switch.get_vlan(vlan_number))

    @to_response
    @content(is_vlan)
    @resource(Switch)
    def add_vlan(self, switch, number, name):
        """
        Create an new VLAN

        :arg str hostname: Hostname or IP of the switch
        :body:
            Highlighted fields are mandatory

            .. literalinclude:: ../doc_config/api_samples/post_switch_hostname_vlans.json
                :language: json
                :emphasize-lines: 2

        """

        switch.add_vlan(number, name)
        return 201, None

    @to_response
    @resource(Switch, Vlan)
    def remove_vlan(self, switch, vlan_number):
        """
        Deletes a VLAN

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096

        """

        switch.remove_vlan(vlan_number)
        return 204, None

    @to_response
    @content(is_ip_network)
    @resource(Switch, Vlan)
    def add_ip(self, switch, vlan_number, validated_ip_network):
        """
        Adds an IP/Subnet to a vlan

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        :body:
            Highlighted fields are mandatory

            .. literalinclude:: ../doc_config/api_samples/post_switch_hostname_vlans_vlanid_ips.json
                :language: json
                :emphasize-lines: 2-3

            or

            .. literalinclude:: ../doc_config/api_samples/post_switch_hostname_vlans_vlanid_ips.txt
        """

        switch.add_ip_to_vlan(vlan_number, validated_ip_network)
        return 201, None

    @to_response
    @resource(Switch, Vlan, IPNetworkResource)
    def remove_ip(self, switch, vlan_number, ip_network):
        """
        Removes an IP/Subnet from a vlan

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        :arg str ip_network: IP/Subnet in the "x.x.x.x/xx" format
        """

        switch.remove_ip_from_vlan(vlan_number, ip_network)
        return 204, None

    @to_response
    @content(is_vrrp_group)
    @resource(Switch, Vlan)
    def add_vrrp_group(self, switch, vlan_number, group_id, ips=None, priority=None, hello_interval=None,
                       dead_interval=None, track_id=None, track_decrement=None):
        """
        Adds a VRRP group to a VLAN

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: VLAN number, between 1 and 4096
        :body:
            Highlighted fields are mandatory

            .. literalinclude:: ../doc_config/api_samples/post_switch_hostname_vlans_vlanid_vrrp_groups.json
                :language: json
                :emphasize-lines: 2-3

        """

        switch.add_vrrp_group(vlan_number=vlan_number,
                              group_id=group_id,
                              ips=ips,
                              priority=priority,
                              hello_interval=hello_interval,
                              dead_interval=dead_interval,
                              track_id=track_id,
                              track_decrement=track_decrement)
        return 201, None

    @to_response
    @resource(Switch, Vlan, VrrpGroup)
    def remove_vrrp_group(self, switch, vlan_number, vrrp_group_id):
        """
        Removes a VRRP group from a VLAN

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: VLAN number, between 1 and 4096
        :arg str vrrp_group_id: VRRP group number, between 1 and 255
        """

        switch.remove_vrrp_group(vlan_number, vrrp_group_id)
        return 204, None

    @to_response
    @content(is_access_group_name)
    @resource(Switch, Vlan, Direction)
    def set_vlan_access_group(self, switch, vlan_number, direction, access_group_name):
        """
        Sets the inbound or outgoing ip access-group on a Vlan

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        :arg int direction: ``in`` or ``out``
        :body:
            .. literalinclude:: ../doc_config/api_samples/put_switch_hostname_vlans_vlanid_accessgroups_in.txt
        """

        switch.set_vlan_access_group(vlan_number, direction, access_group_name)
        return 204, None

    @to_response
    @resource(Switch, Vlan, Direction)
    def unset_vlan_access_group(self, switch, vlan_number, direction):
        """
        Removes the inbound or outgoing ip access-group of a Vlan

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        :arg int direction: ``in`` or ``out``
        """

        switch.unset_vlan_access_group(vlan_number, direction)
        return 204, None

    @to_response
    @resource(Switch)
    def get_interface(self, switch, interface_id):
        """
        Displays informations about a physical interfaces

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: name of the interface
        :code 200 OK:

        Example output:

        .. literalinclude:: ../doc_config/api_samples/get_switch_hostname_interface.json
            :language: json

        """
        return 200, interface.to_api(switch.get_interface(interface_id))

    @to_response
    @resource(Switch)
    def get_interfaces(self, switch):
        """
        Displays informations about all physical interfaces

        :arg str hostname: Hostname or IP of the switch
        :code 200 OK:

        Example output:

        .. literalinclude:: ../doc_config/api_samples/get_switch_hostname_interfaces.json
            :language: json

        """
        interfaces = sorted(switch.get_interfaces(), key=lambda x: x.name.lower())

        return 200, [interface.to_api(i) for i in interfaces]

    @to_response
    @content(is_boolean)
    @resource(Switch, Interface)
    def set_shutdown_state(self, switch, interface_id, state):
        """
        Sets the shutdown state of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        :body:
            ``true`` or ``false``
        """

        if state:
            switch.set_interface_state(interface_id, OFF)
        else:
            switch.set_interface_state(interface_id, ON)

        return 204, None

    @to_response
    @resource(Switch, Interface)
    def unset_shutdown_state(self, switch, interface_id):
        """
        Unsets the shutdown state of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        """

        switch.unset_interface_state(interface_id)
        return 204, None

    @to_response
    @content(is_boolean)
    @resource(Switch, Interface)
    def set_interface_auto_negotiation_state(self, switch, interface_id, state):
        """
        Sets the auto_negotiation state of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        :body:
            ``true`` or ``false``
        """

        switch.set_interface_auto_negotiation_state(interface_id, ON if state is True else OFF)

        return 204, None

    @to_response
    @resource(Switch, Interface)
    def unset_interface_auto_negotiation_state(self, switch, interface_id):
        """
        Unsets the auto-negotiation state of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        """

        switch.unset_interface_auto_negotiation_state(interface_id)
        return 204, None

    @to_response
    @content(is_int)
    @resource(Switch, Interface)
    def set_interface_mtu(self, switch, interface_id, value):
        """
        Sets the mtu of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        :body:
            .. literalinclude:: ../doc_config/api_samples/put_switch_hostname_interfaces_intname_mtu.txt
        """

        switch.set_interface_mtu(interface_id, value)

        return 204, None

    @to_response
    @resource(Switch, Interface)
    def unset_interface_mtu(self, switch, interface_id):
        """
        Unsets the mtu of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        """

        switch.unset_interface_mtu(interface_id)
        return 204, None

    @to_response
    @content(is_int)
    @resource(Switch, Bond)
    def set_bond_mtu(self, switch, bond_number, value):
        """
        Sets the mtu of a bond

        :arg str hostname: Hostname or IP of the switch
        :arg int bond_number: Bond number
        :body:
            .. literalinclude:: ../doc_config/api_samples/put_switch_hostname_interfaces_intname_mtu.txt
        """

        switch.set_bond_mtu(bond_number, value)

        return 204, None

    @to_response
    @resource(Switch, Bond)
    def unset_bond_mtu(self, switch, bond_number):
        """
        Unsets the mtu of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg int bond_number: Bond number
        """

        switch.unset_bond_mtu(bond_number)
        return 204, None

    @to_response
    @resource(Switch, Interface)
    def set_port_mode(self, switch, interface_id):
        """
        Sets the port mode of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        :body:
            ``trunk`` or ``access``
        """

        mode = request.get_data().lower()
        if mode == 'trunk':
            switch.set_trunk_mode(interface_id)
        elif mode == 'access':
            switch.set_access_mode(interface_id)
        else:
            raise BadRequest('Unknown port mode detected {}'.format(mode))

        return 204, None

    @to_response
    @resource(Switch, Bond)
    def set_bond_port_mode(self, switch, bond_number):
        """
        Sets the port mode of a bond

        :arg str hostname: Hostname or IP of the switch
        :arg int bond_number: Bond number
        :body:
            ``trunk`` or ``access``
        """

        mode = request.get_data().lower()
        if mode == 'trunk':
            switch.set_bond_trunk_mode(bond_number)
        elif mode == 'access':
            switch.set_bond_access_mode(bond_number)
        else:
            raise BadRequest('Unknown port mode detected {}'.format(mode))

        return 204, None

    @to_response
    @content(is_vlan_number)
    @resource(Switch, Interface)
    def set_access_vlan(self, switch, interface_id, vlan_number):
        """
        Sets the access vlan of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        :body:
            .. literalinclude:: ../doc_config/api_samples/put_switch_hostname_interfaces_intname_accessvlan.txt

        """

        switch.set_access_vlan(interface_id, vlan_number)
        return 204, None

    @to_response
    @resource(Switch, Interface)
    def reset_interface(self, switch, interface_id):
        """
        Reset the interface to it's default settings

        Adding parameter to the interface is not yet supported. This requests only defaults the switch.

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)

        """

        if request.get_data():
            raise NotImplementedError('Providing data is not supported by this method')
        switch.reset_interface(interface_id)
        return 204, None

    @to_response
    @resource(Switch, Interface)
    def unset_interface_access_vlan(self, switch, interface_id):
        """
        Removes the access vlan of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)

        """
        switch.unset_interface_access_vlan(interface_id)
        return 204, None

    @to_response
    @content(is_vlan_number)
    @resource(Switch, Bond)
    def set_bond_access_vlan(self, switch, bond_number, vlan_number):
        """
        Sets the access vlan of a bond

        :arg str hostname: Hostname or IP of the switch
        :arg int bond_number: Bond number
        :body:
            .. literalinclude:: ../doc_config/api_samples/put_switch_hostname_interfaces_intname_accessvlan.txt

        """

        switch.set_bond_access_vlan(bond_number, vlan_number)
        return 204, None

    @to_response
    @resource(Switch, Bond)
    def remove_bond_access_vlan(self, switch, bond_number):
        """
        Removes the access vlan of a bond

        :arg str hostname: Hostname or IP of the switch
        :arg int bond_number: Bond number

        """
        switch.remove_bond_access_vlan(bond_number)
        return 204, None

    @to_response
    @content(is_vlan_number)
    @resource(Switch, Interface)
    def add_trunk_vlan(self, switch, interface, vlan_number):
        """
        Adds a vlan to the trunk members of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        :body:
            .. literalinclude:: ../doc_config/api_samples/post_switch_hostname_interfaces_intname_trunkvlans.txt

        """
        switch.add_trunk_vlan(interface, vlan_number)
        return 204, None

    @to_response
    @resource(Switch, Interface, Vlan)
    def remove_trunk_vlan(self, switch, interface_id, vlan_number):
        """
        Removes a vlan from the trunk members of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        :arg int vlan_number: Vlan number, between 1 and 4096

        """
        switch.remove_trunk_vlan(interface_id, vlan_number)
        return 204, None

    @to_response
    @content(is_vlan_number)
    @resource(Switch, Bond)
    def add_bond_trunk_vlan(self, switch, bond_number, vlan_number):
        """
        Adds a vlan to the trunk members of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg int bond_number: Bond number
        :body:
            .. literalinclude:: ../doc_config/api_samples/post_switch_hostname_interfaces_intname_trunkvlans.txt

        """
        switch.add_bond_trunk_vlan(bond_number, vlan_number)
        return 204, None

    @to_response
    @resource(Switch, Bond, Vlan)
    def remove_bond_trunk_vlan(self, switch, bond_number, vlan_number):
        """
        Removes a vlan from the trunk members of a bonded interface

        :arg str hostname: Hostname or IP of the switch
        :arg int bond_number: Bond number
        :arg int vlan_number: Vlan number, between 1 and 4096

        """
        switch.remove_bond_trunk_vlan(bond_number, vlan_number)
        return 204, None

    @to_response
    @content(is_vlan_number)
    @resource(Switch, Interface)
    def set_interface_native_vlan(self, switch, interface_id, vlan_number):
        """
        Sets the native vlan of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        :body:
            .. literalinclude:: ../doc_config/api_samples/put_switch_hostname_interfaces_intname_nativevlan.txt

        """

        switch.set_interface_native_vlan(interface_id, vlan_number)
        return 204, None

    @to_response
    @resource(Switch, Interface)
    def unset_interface_native_vlan(self, switch, interface_id):
        """
        Removes the native vlan of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)

        """
        switch.unset_interface_native_vlan(interface_id)
        return 204, None

    @to_response
    @content(is_vlan_number)
    @resource(Switch, Bond)
    def set_bond_native_vlan(self, switch, bond_number, vlan_number):
        """
        Sets the native vlan of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg int bond_number: Bond number
        :body:
            .. literalinclude:: ../doc_config/api_samples/put_switch_hostname_interfaces_intname_nativevlan.txt

        """

        switch.set_bond_native_vlan(bond_number, vlan_number)
        return 204, None

    @to_response
    @resource(Switch, Bond)
    def unset_bond_native_vlan(self, switch, bond_number):
        """
        Removes the native vlan of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg int bond_number: Bond number

        """
        switch.unset_bond_native_vlan(bond_number)
        return 204, None

    @to_response
    @resource(Switch, Bond)
    def get_bond(self, switch, bond_number):
        """
        Displays informations about a bond

        :arg str hostname: Hostname or IP of the switch
        :code 200 OK:

        Example output:

        .. literalinclude:: ../doc_config/api_samples/get_switch_hostname_bond_v2.json
            :language: json

        """

        return 200, bond.to_api(
            switch.get_bond(bond_number),
            version=request.headers.get("Netman-Max-Version"))

    @to_response
    @resource(Switch)
    def get_bonds(self, switch):
        """
        Displays informations about all bonds

        :arg str hostname: Hostname or IP of the switch
        :code 200 OK:

        Example output:

        .. literalinclude:: ../doc_config/api_samples/get_switch_hostname_bonds_v2.json
            :language: json

        """
        bonds = sorted(switch.get_bonds(), key=lambda x: x.number)

        return 200, [bond.to_api(
            b, version=request.headers.get("Netman-Max-Version")
        ) for b in bonds]

    @to_response
    @content(is_bond)
    @resource(Switch)
    def add_bond(self, switch, bond_number):
        """
        Create an new bond

        :arg str hostname: Hostname or IP of the switch
        :body:
            Highlighted fields are mandatory

            .. literalinclude:: ../doc_config/api_samples/post_switch_hostname_bonds.json
                :language: json
                :emphasize-lines: 2

        """

        switch.add_bond(bond_number)
        return 201, None

    @to_response
    @resource(Switch, Bond)
    def remove_bond(self, switch, bond_number):
        """
        Deletes a bond

        :arg str hostname: Hostname or IP of the switch
        :arg int bond_number: Bond number

        """

        switch.remove_bond(bond_number)
        return 204, None

    @to_response
    @content(is_bond_link_speed)
    @resource(Switch, Bond)
    def set_bond_link_speed(self, switch, bond_number, bond_link_speed):
        """
        Change a bond link speed

        :arg str hostname: Hostname or IP of the switch
        :arg int bond_number: Bond number
        :arg str bond_link_speed: Bond link speed
        :body:
            .. literalinclude:: ../doc_config/api_samples/put_switch_hostname_bonds_link_speed.txt
        """

        switch.set_bond_link_speed(bond_number, bond_link_speed)
        return 204, None

    @to_response
    @content(is_bond_number)
    @resource(Switch, Interface)
    def add_interface_to_bond(self, switch, interface_id, bond_number):
        """
        Add interface to bond

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        :arg int bond_number: Bond number
        :body:
            .. literalinclude:: ../doc_config/api_samples/put_switch_hostname_interfaces_bond_master.txt
        """

        switch.add_interface_to_bond(interface_id, bond_number)
        return 204, None

    @to_response
    @resource(Switch, Interface)
    def remove_interface_from_bond(self, switch, interface_id):
        """
        Free interface from bond

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        """

        switch.remove_interface_from_bond(interface_id)
        return 204, None

    @to_response
    @content(is_description)
    @resource(Switch, Interface)
    def set_interface_description(self, switch, interface_id, description):
        """
        Add a description to the interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        :body:
            A long interface description text
        """

        switch.set_interface_description(interface_id, description)
        return 204, None

    @to_response
    @resource(Switch, Interface)
    def unset_interface_description(self, switch, interface_id):
        """
        Remove interface description

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        """

        switch.unset_interface_description(interface_id)
        return 204, None

    @to_response
    @content(is_description)
    @resource(Switch, Bond)
    def set_bond_description(self, switch, bond_number, description):
        """
        Add a description to the bonded interface

        :arg str hostname: Hostname or IP of the switch
        :arg int bond_number: Bond number
        :body:
            A long interface description text
        """

        switch.set_bond_description(bond_number, description)
        return 204, None

    @to_response
    @resource(Switch, Bond)
    def unset_bond_description(self, switch, bond_number):
        """
        Remove bonded interface description

        :arg str hostname: Hostname or IP of the switch
        :arg int bond_number: Bond number
        """

        switch.unset_bond_description(bond_number)
        return 204, None

    @to_response
    @content(is_dict_with(
        edge=optional(is_type(bool))))
    @resource(Switch, Bond)
    def edit_bond_spanning_tree(self, switch, bond_number, **params):
        """
        Edit bond spanning tree properties

        :arg bool edge: Activates edge mode
        :body:
            .. literalinclude:: ../doc_config/api_samples/put_switch_hostname_interfaces_intname_spanningtree.json
        """

        switch.edit_bond_spanning_tree(bond_number, **params)

        return 204, None

    @to_response
    @content(is_dict_with(
        edge=optional(is_type(bool))))
    @resource(Switch, Interface)
    def edit_interface_spanning_tree(self, switch, interface_id, **params):
        """
        Edit interface spanning tree properties

        :arg bool edge: Activates edge mode
        :body:
            .. literalinclude:: ../doc_config/api_samples/put_switch_hostname_interfaces_intname_spanningtree.json
        """

        switch.edit_interface_spanning_tree(interface_id, **params)

        return 204, None

    @to_response
    @content(is_vrf_name)
    @resource(Switch, Vlan)
    def set_vlan_vrf(self, switch, vlan_number, vrf_name):
        """
        Set VLAN VRF name

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        :body:
            DEFAULT_LAN
        """

        switch.set_vlan_vrf(vlan_number, vrf_name)
        return 204, None

    @to_response
    @resource(Switch, Vlan)
    def unset_vlan_vrf(self, switch, vlan_number):
        """
        Remove VLAN VRF name

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        """

        switch.unset_vlan_vrf(vlan_number)
        return 204, None

    @to_response
    @content(is_ip_network)
    @resource(Switch, Vlan)
    def add_dhcp_relay_server(self, switch, vlan_number, validated_ip_network):
        """
        Set DHCP relay server (ip helper address)

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        :body:
            IP address of the DHCP server or its relay
        """

        switch.add_dhcp_relay_server(vlan_number=vlan_number, ip_address=validated_ip_network.ip)
        return 204, None

    @to_response
    @resource(Switch, Vlan, IPNetworkResource)
    def remove_dhcp_relay_server(self, switch, vlan_number, ip_network):
        """
        Remove DHCP relay server (ip helper address)

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        """

        switch.remove_dhcp_relay_server(vlan_number=vlan_number, ip_address=ip_network.ip)
        return 204, None

    @to_response
    @content(is_boolean)
    @resource(Switch, Interface)
    def set_interface_lldp_state(self, switch, interface_id, state):
        """
        Enable or disable the LLDP protocol on the interface

        :arg str hostname: Hostname or IP of the switch
        :arg str interface_id: Interface name (ex. ``FastEthernet0/1``, ``ethernet1/11``)
        :body:
            ``true`` or ``false``
        """

        switch.set_interface_lldp_state(interface_id, state)

        return 204, None

    @to_response
    @content(is_boolean)
    @resource(Switch, Vlan)
    def set_vlan_arp_routing_state(self, switch, vlan_number, state):
        """
        Sets the ARP routing state of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        :body:
            ``true`` or ``false``
        """

        switch.set_vlan_arp_routing_state(vlan_number, ON if state is True else OFF)

        return 204, None

    @to_response
    @content(is_boolean)
    @resource(Switch, Vlan)
    def set_vlan_icmp_redirects_state(self, switch, vlan_number, state):
        """
        Sets the ICMP redirects state of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        :body:
            ``true`` or ``false``
        """

        switch.set_vlan_icmp_redirects_state(vlan_number, state)

        return 204, None

    @to_response
    @content(is_boolean)
    @resource(Switch, Vlan)
    def set_vlan_ntp_state(self, switch, vlan_number, state):
        """
        Enable or disable the ntp state of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        :body:
            ``true`` or ``false``
        """

        switch.set_vlan_ntp_state(vlan_number, state)

        return 204, None

    @to_response
    @content(is_unincast_rpf_mode)
    @resource(Switch, Vlan)
    def set_vlan_unicast_rpf_mode(self, switch, vlan_number, mode):
        """
        Sets the Unicast RPF state of an interface *only strict is supported*

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        :body:
            ``STRICT``
        """

        switch.set_vlan_unicast_rpf_mode(vlan_number, mode)

        return 204, None

    @to_response
    @resource(Switch, Vlan)
    def unset_vlan_unicast_rpf_mode(self, switch, vlan_number):
        """
        Remove Unicast RPF configuration of an interface

        :arg str hostname: Hostname or IP of the switch
        :arg int vlan_number: Vlan number, between 1 and 4096
        """

        switch.unset_vlan_unicast_rpf_mode(vlan_number)
        return 204, None
