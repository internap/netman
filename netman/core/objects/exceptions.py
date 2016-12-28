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

from netman.core.objects.access_groups import IN, OUT


class NetmanException(Exception):
    pass


class InvalidValue(NetmanException):
    def __init__(self, msg="Invalid Value"):
        super(InvalidValue, self).__init__(msg)


class UnknownResource(NetmanException):
    def __init__(self, msg="Resource not found"):
        super(UnknownResource, self).__init__(msg)


class Conflict(NetmanException):
    def __init__(self, msg="Conflicting value"):
        super(Conflict, self).__init__(msg)


class SessionAlreadyExists(Conflict):
    def __init__(self, session_id=None):
        super(SessionAlreadyExists, self).__init__(msg="Session ID already exists: {}".format(session_id))


class UnavailableResource(NetmanException):
    def __init__(self, msg="Resource not available"):
        super(UnavailableResource, self).__init__(msg)


class OperationNotCompleted(NetmanException):
    def __init__(self, problem=None):
        super(OperationNotCompleted, self).__init__("An error occured while completing operation, no modifications have been applied : {0}".format(problem))


class InterfaceResetIncomplete(NetmanException):
    def __init__(self, interface_data=None):
        super(InterfaceResetIncomplete, self).__init__("The interface reset has failed to remove these properties: {0}".format(interface_data))


class UnknownVlan(UnknownResource):
    def __init__(self, vlan_number=None):
        super(UnknownVlan, self).__init__("Vlan {} not found".format(vlan_number))


class UnknownInterface(UnknownResource):
    def __init__(self, interface=None):
        super(UnknownInterface, self).__init__("Unknown interface {}".format(interface))


class UnknownIP(UnknownResource):
    def __init__(self, ip_network=None):
        super(UnknownIP, self).__init__("IP {} not found".format(ip_network))


class UnknownAccessGroup(UnknownResource):
    def __init__(self, direction=None):
        super(UnknownAccessGroup, self).__init__("{} IP access group not found".format({IN: "Inbound", OUT: "Outgoing"}[direction] if direction else ""))


class UnknownSession(UnknownResource):
    def __init__(self, session_id=None):
        super(UnknownSession, self).__init__("Session \"{}\" not found.".format(session_id))


class UnknownVrf(UnknownResource):
    def __init__(self, name=None):
        super(UnknownVrf, self).__init__("VRF name \"{}\" was not configured.".format(name))


class UnknownDhcpRelayServer(UnknownResource):
    def __init__(self, vlan_number, ip_address):
        super(UnknownDhcpRelayServer, self).__init__("DHCP relay server {} not found on VLAN {}".format(ip_address, vlan_number))


class DhcpRelayServerAlreadyExists(UnknownResource):
    def __init__(self, vlan_number, ip_address):
        super(DhcpRelayServerAlreadyExists, self).__init__("DHCP relay server {} already exists on VLAN {}".format(ip_address, vlan_number))


class AccessVlanNotSet(UnknownResource):
    def __init__(self, interface=None):
        super(AccessVlanNotSet, self).__init__("Access Vlan is not set on interface {}".format(interface))


class TrunkVlanNotSet(UnknownResource):
    def __init__(self, interface=None):
        super(TrunkVlanNotSet, self).__init__("Trunk Vlan is not set on interface {}".format(interface))


class NativeVlanNotSet(UnknownResource):
    def __init__(self, interface=None):
        super(NativeVlanNotSet, self).__init__("Trunk native Vlan is not set on interface {}".format(interface))


class InterfaceSpanningTreeNotEnabled(UnknownResource):
    def __init__(self, interface=None):
        super(InterfaceSpanningTreeNotEnabled, self).__init__("Spanning tree is not enabled on interface {}".format(interface))


class VlanVrfNotSet(UnknownResource):
    def __init__(self, vlan=None):
        super(VlanVrfNotSet, self).__init__("VRF is not set on vlan {}".format(vlan))


class IPNotAvailable(Conflict):
    def __init__(self, ip_network=None, reason=None):
        super(IPNotAvailable, self).__init__("IP {} is not available in this vlan{}".format(ip_network, (": " + reason) if reason is not None else ""))


class IPAlreadySet(Conflict):
    def __init__(self, ip_network=None, present_ip_network=None):
        super(IPAlreadySet, self).__init__("IP {} is already present in this vlan as {}".format(ip_network, present_ip_network))


class VlanAlreadyExist(Conflict):
    def __init__(self, vlan_number=None):
        super(VlanAlreadyExist, self).__init__("Vlan {} already exists".format(vlan_number))


class InterfaceInWrongPortMode(Conflict):
    def __init__(self, mode=None):
        super(InterfaceInWrongPortMode, self).__init__("Operation cannot be performed on a {} mode interface".format(mode))


class VlanAlreadyInTrunk(Conflict):
    def __init__(self, vlan=None):
        super(VlanAlreadyInTrunk, self).__init__("Vlan {} cannot be set as native vlan because it is already a member of the trunk".format(vlan))


class VrrpAlreadyExistsForVlan(Conflict):
    def __init__(self, vlan=None, vrrp_group_id=None):
        super(VrrpAlreadyExistsForVlan, self).__init__("Vrrp group {group} is already in use on vlan {vlan}".format(group=vrrp_group_id, vlan=vlan))


class VrrpDoesNotExistForVlan(InvalidValue):
    def __init__(self, vlan=None, vrrp_group_id=None):
        super(VrrpDoesNotExistForVlan, self).__init__("Vrrp group {group} does not exist for vlan {vlan}".format(group=vrrp_group_id, vlan=vlan))


class NoIpOnVlanForVrrp(InvalidValue):
    def __init__(self, vlan=None):
        super(NoIpOnVlanForVrrp, self).__init__("Vlan {vlan} needs an IP before configuring VRRP".format(vlan=vlan))


class BadVlanNumber(InvalidValue):
    def __init__(self):
        super(BadVlanNumber, self).__init__("Vlan number is invalid")


class BadInterfaceDescription(InvalidValue):
    def __init__(self, desc=None):
        super(BadInterfaceDescription, self).__init__("Invalid description : {}".format(desc))


class BadVrrpGroupNumber(InvalidValue):
    def __init__(self, minimum=None, maximum=None):
        super(BadVrrpGroupNumber, self).__init__("VRRP group number is invalid, must be contained between {min} and {max}".format(min=minimum, max=maximum))


class BadVrrpPriorityNumber(InvalidValue):
    def __init__(self, minimum=None, maximum=None):
        super(BadVrrpPriorityNumber, self).__init__("VRRP priority value is invalid, must be contained between {min} and {max}".format(min=minimum, max=maximum))


class BadVrrpTimers(InvalidValue):
    def __init__(self):
        super(BadVrrpTimers, self).__init__("VRRP timers values are invalid")


class BadVrrpAuthentication(InvalidValue):
    def __init__(self):
        super(BadVrrpAuthentication, self).__init__("VRRP authentication is invalid")


class BadVrrpTracking(InvalidValue):
    def __init__(self):
        super(BadVrrpTracking, self).__init__("VRRP tracking values are invalid")


class BadVlanName(InvalidValue):
    def __init__(self):
        super(BadVlanName, self).__init__("Vlan name is invalid")


class LockedSwitch(UnavailableResource):
    def __init__(self):
        super(LockedSwitch, self).__init__("Switch is locked and can't be modified")


class UnableToAcquireLock(UnavailableResource):
    def __init__(self):
        super(UnableToAcquireLock, self).__init__("Unable to acquire a lock in a timely fashion")


class BadBondNumber(InvalidValue):
    def __init__(self):
        super(BadBondNumber, self).__init__("Bond number is invalid")


class InterfaceNotInBond(UnknownResource):
    def __init__(self):
        super(InterfaceNotInBond, self).__init__("Interface not associated to specified bond")


class BondAlreadyExist(Conflict):
    def __init__(self, number=None):
        super(BondAlreadyExist, self).__init__("Bond {} already exists".format(number))


class UnknownBond(UnknownResource):
    def __init__(self, number=None):
        super(UnknownBond, self).__init__("Bond {} not found".format(number))


class BadBondLinkSpeed(InvalidValue):
    def __init__(self):
        super(BadBondLinkSpeed, self).__init__("Malformed bond link speed")


class UnknownSwitch(UnknownResource):
    def __init__(self, name=None):
        super(UnknownSwitch, self).__init__("Switch \"{0}\" is not configured".format(name))


class MalformedSwitchSessionRequest(InvalidValue):
    def __init__(self):
        super(MalformedSwitchSessionRequest, self).__init__("Malformed switch session request")


class Timeout(Exception):
    pass


class ConnectTimeout(Exception):
    def __init__(self, host=None, port=None):
        super(ConnectTimeout, self).__init__("Timed out while connecting to {} on port {}".format(host, port))


class CommandTimeout(Exception):
    def __init__(self, wait_for=None, buffer=None):
        super(CommandTimeout, self).__init__("Command timed out expecting {}. Current read buffer: {}"
                                             .format(repr(wait_for), buffer))


class PrivilegedAccessRefused(Exception):
    def __init__(self, buffer=None):
        super(PrivilegedAccessRefused, self).__init__("Could not get PRIVILEGED exec mode. "
                                                      "Current read buffer: {}".
                                                      format(buffer))


class CouldNotConnect(Exception):
    def __init__(self, host=None, port=None):
        super(CouldNotConnect, self).__init__("Could not connect to {} on port {}".format(host, port))


class InvalidAccessGroupName(InvalidValue):
    def __init__(self, name=None):
        super(InvalidAccessGroupName, self).__init__("Access Group Name is invalid: {}".format(name))


class InvalidMtuSize(InvalidValue):
    def __init__(self, err_msg=None):
        super(InvalidMtuSize, self).__init__("MTU value is invalid : {}".format(err_msg))
