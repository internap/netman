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
import logging
from netaddr import IPAddress, IPNetwork

from tests.adapters.shell.terminal_client_test import telnet_hook_to_reactor, ssh_hook_to_reactor
from tests.adapters.unified_tests import available_models
from global_reactor import ThreadedReactor


def setup():
    ThreadedReactor.start_reactor(available_models, reactor_hook_callbacks=[telnet_hook_to_reactor, ssh_hook_to_reactor])


def tearDown():
    ThreadedReactor.stop_reactor()


class ExactIpNetwork(object):
    def __init__(self, ip, mask):
        self.ip = IPAddress(ip)
        self.mask = mask

    def __eq__(self, other):
        if not isinstance(other, IPNetwork):
            logging.error("{} is not an IPNetwork object".format(repr(other)))
            return False
        result = other.ip == self.ip and other.prefixlen == self.mask
        if not result:
            logging.error("Expected {}/{} and got {}/{}".format(self.ip, self.mask, other.ip, other.prefixlen))
        return result

    def __repr__(self):
        return "{}/{}".format(self.ip, self.mask)
