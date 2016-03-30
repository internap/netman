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
import signal
import unittest

from netman.adapters.switches.juniper.base import all_vlans
from netman.adapters.switches.juniper.standard import netconf
from tests import available_models


class JuniperIssue125Test(unittest.TestCase):

    def setUp(self):
        specs = next(s for s in available_models if s["switch_descriptor"].model == "juniper")

        self.switch = netconf(specs["switch_descriptor"])
        self.switch.connect()
        self.switch.start_transaction()

    def tearDown(self):
        try:
            with Timeout(seconds=3):
                self.switch.rollback_transaction()
                self.switch.end_transaction()
                self.switch.disconnect()
        except AssertionError:
            pass

    def test_juniper_does_not_break_with_after_reading_a_4096_chunk(self):
        self._setup_vlan_list_to_be_the_exact_problematic_size(4097)

        self.switch.query(all_vlans)
        with Timeout(seconds=1, error_message="ssh reading is stuck"):
            self.switch.query(all_vlans)

    def _setup_vlan_list_to_be_the_exact_problematic_size(self, problematic_size):
        self.switch.add_vlan(1000, name="a")
        result_with_one_vlan = self.switch.query(all_vlans).data_xml
        self.switch.add_vlan(1001, name="a")
        result_with_two_vlan = self.switch.query(all_vlans).data_xml

        vlan_with_no_name_size = len(result_with_two_vlan) - len(result_with_one_vlan) - 1

        rpc_wrapper_size = 134
        max_name_length = 250

        target_xml_size = problematic_size - rpc_wrapper_size
        original_size = len(result_with_two_vlan)
        number_of_full_vlans_to_add = (target_xml_size - original_size) / (max_name_length + vlan_with_no_name_size)

        for i in range(0, number_of_full_vlans_to_add):
            self.switch.add_vlan(2000 + i, name="x" * max_name_length)

        remaining_size_to_add = original_size + number_of_full_vlans_to_add * (max_name_length + vlan_with_no_name_size)

        self.switch.add_vlan(1002, name="x" * (target_xml_size - remaining_size_to_add - vlan_with_no_name_size))


class Timeout:
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise AssertionError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)
