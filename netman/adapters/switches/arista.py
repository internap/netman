import pyeapi
from pyeapi.api.vlans import Vlans, isvlan
from pyeapi.client import Node
from pyeapi.eapilib import CommandError

from netman.core.objects.exceptions import VlanAlreadyExist, UnknownVlan, BadVlanNumber, BadVlanName, \
    OperationNotCompleted
from netman.core.objects.switch_base import SwitchBase
from netman.core.objects.vlan import Vlan


def eapi(switch_descriptor):
    return Arista(switch_descriptor=switch_descriptor)


class Arista(SwitchBase):
    def __init__(self, switch_descriptor):
        super(Arista, self).__init__(switch_descriptor)
        self.switch_descriptor = switch_descriptor

    def _connect(self):
        self.conn = pyeapi.connect(host=self.switch_descriptor.hostname,
                                   username=self.switch_descriptor.username,
                                   password=self.switch_descriptor.password,
                                   port=self.switch_descriptor.port,
                                   transport='http')

        self.node = Node(self.conn, transport='http', host=self.switch_descriptor.hostname,
                         username=self.switch_descriptor.username, password=self.switch_descriptor.password,
                         port=self.switch_descriptor.port)

    def _disconnect(self):
        self.conn = None

    def _end_transaction(self):
        pass

    def _start_transaction(self):
        pass

    def get_vlan(self, number):
        try:
            vlans_info = self.conn.execute("show vlan {}".format(number))
        except CommandError:
            raise UnknownVlan(number)

        return self._extract_vlan_list(vlans_info)[0]

    def get_vlans(self):
        vlans_info = self.conn.execute("show vlan")

        return self._extract_vlan_list(vlans_info)

    def add_vlan(self, number, name=None):
        if not isvlan(number):
            raise BadVlanNumber()
        try:
            self.conn.execute("show vlan {}".format(number))
            raise VlanAlreadyExist(number)
        except CommandError:
            pass

        commands = ["name {}".format(name)] if name else []

        vlan = Vlans(self.node)
        if not vlan.configure_vlan(number, commands):
            raise BadVlanName()

    def remove_vlan(self, number):
        try:
            self.conn.execute("show vlan {}".format(number))
        except CommandError:
            raise UnknownVlan(number)

        vlan = Vlans(self.node)
        if not vlan.delete(number):
            raise OperationNotCompleted("Unable to remove vlan {}".format(number))

    def _extract_vlan_list(self, vlans_info):
        vlan_list = []
        for id, vlan in vlans_info['result'][0]['vlans'].items():
            if vlan['name'] == ("VLAN{:04d}".format(int(id))):
                vlan['name'] = None

            vlan_list.append(Vlan(number=int(id), name=vlan['name'], icmp_redirects=True, arp_routing=True, ntp=True))
        return vlan_list
