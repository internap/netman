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
from hamcrest import equal_to, assert_that, is_, starts_with
from mock import patch, Mock

from twisted.internet.protocol import Factory

from netman.adapters import shell
from netman.adapters.shell.ssh import SshClient
from netman.adapters.shell.telnet import TelnetClient
from netman.core.objects.exceptions import CouldNotConnect, CommandTimeout, ConnectTimeout
from tests.adapters.shell.mock_telnet import MockTelnet
from tests.adapters.shell.mock_terminal_commands import passwd_change_protocol_prompt, passwd_write_password_to_transport, \
    HangingCommand, MultiAsyncWriteCommand, SkippingLineCommand, exit_command_success, KeystrokeAnsweredCommand, \
    AmbiguousCommand

command_passwd = MockSSH.PromptingCommand(
    name='passwd',
    password='1234',
    prompt="Password:",
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

abiguous_command = AmbiguousCommand('ambiguous')

commands = [command_passwd, command_hello, command_hang, command_flush,
            command_skips, command_exit, command_question, abiguous_command]
users = {'admin': '1234'}


class TerminalClientTest(unittest.TestCase):
    __test__ = False

    client = None
    port = None

    def test_connect(self):
        client = self.client("127.0.0.1", "admin", "1234", self.port)
        res = client.do('hello')
        assert_that(res, equal_to(['Bonjour']))

    def test_connect_unicode(self):
        client = self.client(u"127.0.0.1", u"admin", u"1234", self.port)
        res = client.do(u'hello')
        assert_that(res, equal_to(['Bonjour']))

    def test_connect_timeout(self):
        with self.assertRaises(ConnectTimeout) as expect:
            self.client("10.0.0.0", "whatever", "whatever", connect_timeout=1)

        assert_that(str(expect.exception), starts_with("Timed out while connecting to 10.0.0.0 on port"))

    def test_connect_error(self):
        with self.assertRaises(CouldNotConnect) as expect:
            self.client("url.invalid", "bleh", "blah", 12345)

        assert_that(str(expect.exception), is_("Could not connect to url.invalid on port 12345"))

    def test_connect_and_salute(self):
        client = self.client("127.0.0.1", "admin", "1234", self.port)
        client.do('passwd', wait_for="Password:")
        client.do('1234')
        res = client.do('hello')
        assert_that(res, equal_to(['Bonjour']))

    def test_timeout(self):
        client = self.client("127.0.0.1", "admin", "1234", self.port, command_timeout=1)
        client.do('passwd', wait_for="Password:")
        client.do('1234')
        with self.assertRaises(CommandTimeout):
            client.do('hang')

    def test_async_result(self):
        client = self.client("127.0.0.1", "admin", "1234", self.port)
        client.do('passwd', wait_for="Password:")
        client.do('1234')
        res = client.do('flush')
        assert_that(res, equal_to([
            "Line 1",
            "Line 2",
            "Line 3",
            "Line 4",
            "Line 5",
            ]))

    def test_empty_lines_are_filtered_out(self):
        client = self.client("127.0.0.1", "admin", "1234", self.port)
        res = client.do('skips')
        assert_that(res, equal_to(["5 lines skipped!"]))

    def test_read_prompt(self):
        client = self.client("127.0.0.1", "admin", "1234", self.port)
        res = client.get_current_prompt()
        assert_that(res, equal_to("hostname>"))

        client.do('passwd', wait_for="Password:")
        client.do('1234')

        res = client.get_current_prompt()
        assert_that(res, equal_to("hostname#"))

    def test_exit(self):
        client = self.client("127.0.0.1", "admin", "1234", self.port)
        client.do('passwd', wait_for="Password:")
        client.do('1234')
        res = client.do('hello')
        assert_that(res, equal_to(['Bonjour']))

        client.quit('exit')

    def test_chunked_reading(self):
        client = self.client("127.0.0.1", "admin", "1234", self.port, reading_chunk_size=1)
        res = client.do('hello')
        assert_that(res, equal_to(['Bonjour']))

    def test_a_complete_log_of_the_conversation_is_kept_and_up_to_date(self):
        client = self.client("127.0.0.1", "admin", "1234", self.port)
        client.do('passwd', wait_for="Password:")
        client.do('1234')
        res = client.do('hello')
        assert_that(res, equal_to(['Bonjour']))

        client.quit('exit')

        assert_that(client.full_log.replace("\r\n", "\n"), equal_to(textwrap.dedent("""\
            hostname>passwd
            Password:
            hostname#hello
            Bonjour
            hostname#""")))

    def test_send_a_keystroke(self):
        client = self.client("127.0.0.1", "admin", "1234", port=self.port)
        res = client.do('keystroke', wait_for="?", include_last_line=True)
        assert_that(res[-1], is_("whatup?"))
        res = client.send_key('k', wait_for=">", include_last_line=True)
        assert_that(res, equal_to(['K pressed', "hostname>"]))

        client.quit('exit')

        assert_that(client.full_log.replace("\r\n", "\n"), equal_to(textwrap.dedent("""\
            hostname>keystroke
            whatup?k
            K pressed
            hostname>""")))

    def test_support_regex(self):
        client = self.client("127.0.0.1", "admin", "1234", port=self.port)
        res = client.do('ambiguous', wait_for=('>', '#'))
        client.quit('exit')

        assert_that(res, equal_to(['working -> done!']))

    def _get_some_credentials(self):
        return {'host': "host.com", 'username': "user", 'password': "pass"}


class SshClientTest(TerminalClientTest):
    __test__ = True

    client = SshClient
    port = 10010

    @patch('netman.adapters.shell.ssh.SshClient._open_channel')
    def test_changing_default_connect_timeout(self, open_channel_method_mock):
        shell.default_connect_timeout = 60

        SshClient(**self._get_some_credentials())
        self.assertEqual(60, open_channel_method_mock.call_args[0][4])

        shell.default_connect_timeout = 120

        SshClient(**self._get_some_credentials())
        self.assertEqual(120, open_channel_method_mock.call_args[0][4])

    @patch('netman.adapters.shell.ssh.SshClient._open_channel', Mock())
    def test_changing_default_command_timeout(self):
        shell.base.default_command_timeout = 300

        ssh = SshClient(**self._get_some_credentials())
        self.assertEqual(300, ssh.command_timeout)

        shell.default_command_timeout = 600

        ssh2 = SshClient(**self._get_some_credentials())
        self.assertEqual(600, ssh2.command_timeout)


class TelnetClientTest(TerminalClientTest):
    __test__ = True

    client = TelnetClient
    port = 10011

    @patch('netman.adapters.shell.telnet.telnetlib.Telnet')
    @patch('netman.adapters.shell.telnet.TelnetClient._login', Mock())
    def test_changing_default_connect_timeout(self, connect_method_mock):
        shell.default_connect_timeout = 60

        TelnetClient(**self._get_some_credentials())
        self.assertEqual(60, connect_method_mock.call_args[0][2])

        shell.default_connect_timeout = 120

        TelnetClient(**self._get_some_credentials())
        self.assertEqual(120, connect_method_mock.call_args[0][2])

    @patch('netman.adapters.shell.telnet.telnetlib.Telnet', Mock())
    @patch('netman.adapters.shell.telnet.TelnetClient._login', Mock())
    def test_changing_default_command_timeout(self):
        shell.default_command_timeout = 300

        telnet = TelnetClient(**self._get_some_credentials())
        self.assertEqual(300, telnet.command_timeout)

        shell.default_command_timeout = 600

        telnet2 = TelnetClient(**self._get_some_credentials())
        self.assertEqual(600, telnet2.command_timeout)


class SwitchTelnetFactory(Factory):
    def __init__(self, prompt, commands):
        self.prompt = prompt
        self.commands = commands

    def protocol(self):
        return MockTelnet(prompt=self.prompt, commands=self.commands)


def telnet_hook_to_reactor(reactor):
    reactor.listenTCP(interface="127.0.0.1", port=TelnetClientTest.port, factory=SwitchTelnetFactory("hostname>", commands))


def ssh_hook_to_reactor(reactor):
    sshFactory = MockSSH.getSSHFactory(commands,
                                       "hostname>",
                                       tempfile.mkdtemp(),
                                       **users)
    reactor.listenTCP(interface='127.0.0.1', port=SshClientTest.port, factory=sshFactory)
