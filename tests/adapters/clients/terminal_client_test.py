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

import tempfile
import textwrap
import unittest

import MockSSH
from hamcrest import equal_to, assert_that, is_
from twisted.internet import reactor
from twisted.internet.protocol import Factory

from netman.adapters.telnet_client import TelnetClient
from tests.adapters.clients.mock_telnet import MockTelnet
from tests.adapters.clients.mock_terminal_commands import passwd_change_protocol_prompt, passwd_write_password_to_transport, \
    HangingCommand, MultiAsyncWriteCommand, SkippingLineCommand, exit_command_success, KeystrokeAnsweredCommand
from netman.adapters.ssh_client import SshClient, Timeout

command_passwd = MockSSH.PromptingCommand(
    name='passwd',
    password='1234',
    password_prompt="Password:",
    success_callbacks=[passwd_change_protocol_prompt],
    failure_callbacks=[passwd_write_password_to_transport])

command_hello = MockSSH.ArgumentValidatingCommand(
    name='hello',
    success_callbacks=[lambda instance: instance.writeln("Bonjour")],
    failure_callbacks=[lambda instance: instance.writeln("Nope")])

command_hang = HangingCommand(name='hang', hang_time=1.1)

command_flush = MultiAsyncWriteCommand(name='flush', count=5, interval=0.1)

command_skips= SkippingLineCommand(name='skips', lines=5)

command_exit = MockSSH.ArgumentValidatingCommand('exit',
                                                 [exit_command_success],
                                                 [lambda instance: instance.writeln("Nope")],
                                                 *[])

command_question = KeystrokeAnsweredCommand('keystroke')

commands = [command_passwd, command_hello, command_hang, command_flush,
            command_skips, command_exit, command_question]
users = {'admin': '1234'}

class TerminalClientTest(unittest.TestCase):
    __test__ = False

    client = None
    port = None

    def test_connect(self):
        ssh = self.client("127.0.0.1", "admin", "1234", self.port)
        res = ssh.do('hello')
        assert_that(res, equal_to(['Bonjour']))

    def test_connect_timeout(self):
        with self.assertRaises(Timeout):
            SshClient("1.0.0.1", "whatever", "whatever", connect_timeout=1)

    def test_connect_and_salute(self):
        ssh = self.client("127.0.0.1", "admin", "1234", self.port)
        ssh.do('passwd', wait_for="Password:")
        ssh.do('1234')
        res = ssh.do('hello')
        assert_that(res, equal_to(['Bonjour']))

    def test_timeout(self):
        ssh = self.client("127.0.0.1", "admin", "1234", self.port, command_timeout=1)
        ssh.do('passwd', wait_for="Password:")
        ssh.do('1234')
        with self.assertRaises(Timeout):
            ssh.do('hang')

    def test_async_result(self):
        ssh = self.client("127.0.0.1", "admin", "1234", self.port)
        ssh.do('passwd', wait_for="Password:")
        ssh.do('1234')
        res = ssh.do('flush')
        assert_that(res, equal_to([
            "Line 1",
            "Line 2",
            "Line 3",
            "Line 4",
            "Line 5",
            ]))

    def test_empty_lines_are_filtered_out(self):
        ssh = self.client("127.0.0.1", "admin", "1234", self.port)
        res = ssh.do('skips')
        assert_that(res, equal_to(["5 lines skipped!"]))

    def test_read_prompt(self):
        ssh = self.client("127.0.0.1", "admin", "1234", self.port)
        res = ssh.get_current_prompt()
        assert_that(res, equal_to("hostname>"))

        ssh.do('passwd', wait_for="Password:")
        ssh.do('1234')

        res = ssh.get_current_prompt()
        assert_that(res, equal_to("hostname#"))

    def test_exit(self):
        ssh = self.client("127.0.0.1", "admin", "1234", self.port)
        ssh.do('passwd', wait_for="Password:")
        ssh.do('1234')
        res = ssh.do('hello')
        assert_that(res, equal_to(['Bonjour']))

        ssh.quit('exit')

    def test_chunked_reading(self):
        ssh = self.client("127.0.0.1", "admin", "1234", self.port, reading_chunk_size=1)
        res = ssh.do('hello')
        assert_that(res, equal_to(['Bonjour']))

    def test_a_complete_log_of_the_conversation_is_kept_and_up_to_date(self):
        ssh = self.client("127.0.0.1", "admin", "1234", self.port)
        ssh.do('passwd', wait_for="Password:")
        ssh.do('1234')
        res = ssh.do('hello')
        assert_that(res, equal_to(['Bonjour']))

        ssh.quit('exit')

        assert_that(ssh.full_log.replace("\r\n", "\n"), equal_to(textwrap.dedent("""\
            hostname>passwd
            Password:
            hostname#hello
            Bonjour
            hostname#""")))

    def test_send_a_keystroke(self):
        ssh = self.client("127.0.0.1", "admin", "1234", port=self.port)
        res = ssh.do('keystroke', wait_for="?", include_last_line=True)
        assert_that(res[-1], is_("whatup?"))
        res = ssh.send_key('k', wait_for=">", include_last_line=True)
        assert_that(res, equal_to(['K pressed', "hostname>"]))

        ssh.quit('exit')

        assert_that(ssh.full_log.replace("\r\n", "\n"), equal_to(textwrap.dedent("""\
            hostname>keystroke
            whatup?k
            K pressed
            hostname>""")))



class SshClientTest(TerminalClientTest):
    __test__ = True

    client = SshClient
    port = 10010
    
    @classmethod
    def setUpClass(cls):
        sshFactory = MockSSH.getSSHFactory(commands,
                                           "hostname>",
                                           tempfile.mkdtemp(),
                                           **users)
        reactor.listenTCP(cls.port, sshFactory, interface='127.0.0.1')


class TelnetClientTest(TerminalClientTest):
    __test__ = True

    client = TelnetClient
    port = 10011
    
    @classmethod
    def setUpClass(cls):
        reactor.listenTCP(interface="127.0.0.1", port=cls.port, factory=SwitchTelnetFactory("hostname>", commands))



class SwitchTelnetFactory(Factory):
    def __init__(self, prompt, commands):
        self.prompt = prompt
        self.commands = commands

    def protocol(self):
        return MockTelnet(prompt=self.prompt, commands=self.commands)
