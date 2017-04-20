# Copyright 2016 Internap.
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

import unittest

from hamcrest import assert_that, is_
from netman.adapters import shell
from twisted.internet.protocol import Factory

from netman.adapters.shell.telnet import TelnetClient
from netman.core.objects.exceptions import ConnectTimeout
from tests.adapters.shell.mock_telnet import MockTelnet


class TelnetLoginSpecialCasesTest(unittest.TestCase):
    client = TelnetClient
    port = 10013

    def test_hanging_during_the_login_process_raises_a_connect_timeout(self):
        shell.default_connect_timeout = 0.1
        with self.assertRaises(ConnectTimeout) as expect:
            self.client("127.0.0.1", "admin", "1234", self.port)

        assert_that(str(expect.exception), is_("Timed out while connecting to 127.0.0.1 on port 10013"))


class PasswordHangingMockTelnet(MockTelnet):
    def validate_password(self, _):
        pass


class SwitchTelnetFactory(Factory):
    def __init__(self, prompt, commands):
        self.prompt = prompt
        self.commands = commands

    def protocol(self):
        return PasswordHangingMockTelnet(prompt=self.prompt, commands=self.commands)


def hanging_password_telnet_hook(reactor):
    reactor.listenTCP(interface="127.0.0.1",
                      port=TelnetLoginSpecialCasesTest.port,
                      factory=SwitchTelnetFactory("hostname>", []))
