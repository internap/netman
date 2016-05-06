import unittest
from copy import deepcopy

from hamcrest import assert_that
from hamcrest import is_

from netman.adapters.threading_lock_factory import ThreadingLockFactory
from netman.core.switch_factory import FlowControlSwitchFactory
from tests.system_tests import NetmanTestApp, get_available_switch


class SessionTest(unittest.TestCase):

    def test_multiple_proxies_works(self):
        with NetmanTestApp() as partial_client1, NetmanTestApp() as partial_client2:
            factory = FlowControlSwitchFactory(None, ThreadingLockFactory())
            switch_descriptor = deepcopy(get_available_switch("juniper"))

            client1 = partial_client1(switch_descriptor)
            first_netman_url = "{}:{}".format(client1.host, client1.port)

            client2 = partial_client2(switch_descriptor)
            second_netman_url = "{}:{}".format(client2.host, client2.port)

            switch_descriptor.netman_server = [first_netman_url, second_netman_url]

            switch = factory.get_switch_by_descriptor(switch_descriptor)

            with switch.transaction():
                switch.add_vlan(1497, "one")

            assert_that(client2.get("/switches/{hostname}/vlans/1497").json()["name"], is_("one"))
