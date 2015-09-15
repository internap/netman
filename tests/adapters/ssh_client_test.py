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
import time

from MockSSH import SSHCommand
import MockSSH
from hamcrest import equal_to, assert_that, is_
from twisted.internet import reactor

from netman.adapters.ssh_client import SshClient, Timeout


class SshClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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

        sshFactory = MockSSH.getSSHFactory(commands,
                                           "hostname>",
                                           tempfile.mkdtemp(),
                                           **users)
        reactor.listenTCP(10010, sshFactory, interface='127.0.0.1')

    def test_connect(self):
        ssh = SshClient("127.0.0.1", "admin", "1234", port=10010)
        res = ssh.do('hello')
        assert_that(res, equal_to(['Bonjour']))

    def test_connect_timeout(self):
        with self.assertRaises(Timeout):
            SshClient("1.0.0.1", "whatever", "whatever", connect_timeout=1)

    def test_connect_and_salute(self):
        ssh = SshClient("127.0.0.1", "admin", "1234", port=10010)
        ssh.do('passwd', wait_for="Password:")
        ssh.do('1234')
        res = ssh.do('hello')
        assert_that(res, equal_to(['Bonjour']))

    def test_timeout(self):
        ssh = SshClient("127.0.0.1", "admin", "1234", port=10010, command_timeout=1)
        ssh.do('passwd', wait_for="Password:")
        ssh.do('1234')
        with self.assertRaises(Timeout):
            ssh.do('hang')

    def test_async_result(self):
        ssh = SshClient("127.0.0.1", "admin", "1234", port=10010)
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
        ssh = SshClient("127.0.0.1", "admin", "1234", port=10010)
        res = ssh.do('skips')
        assert_that(res, equal_to(["5 lines skipped!"]))

    def test_read_prompt(self):
        ssh = SshClient("127.0.0.1", "admin", "1234", port=10010)
        res = ssh.get_current_prompt()
        assert_that(res, equal_to("hostname>"))

        ssh.do('passwd', wait_for="Password:")
        ssh.do('1234')

        res = ssh.get_current_prompt()
        assert_that(res, equal_to("hostname#"))

    def test_exit(self):
        ssh = SshClient("127.0.0.1", "admin", "1234", port=10010)
        ssh.do('passwd', wait_for="Password:")
        ssh.do('1234')
        res = ssh.do('hello')
        assert_that(res, equal_to(['Bonjour']))

        ssh.quit('exit')

    def test_chunked_reading(self):
        ssh = SshClient("127.0.0.1", "admin", "1234", port=10010, reading_chunk_size=1)
        res = ssh.do('hello')
        assert_that(res, equal_to(['Bonjour']))

    def test_a_complete_log_of_the_conversation_is_kept_and_up_to_date(self):
        ssh = SshClient("127.0.0.1", "admin", "1234", port=10010)
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
        ssh = SshClient("127.0.0.1", "admin", "1234", port=10010)
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


class HangingCommand(SSHCommand):
    def __init__(self, name, hang_time, *args):
        self.name = name
        self.hang_time = hang_time
        self.protocol = None  # set in __call__

    def __call__(self, protocol, *args):
        SSHCommand.__init__(self, protocol, self.name, *args)
        return self

    def start(self):
        time.sleep(self.hang_time)
        self.write("Done!\n")
        self.exit()


class MultiAsyncWriteCommand(SSHCommand):
    def __init__(self, name, count, interval, *args):
        self.name = name
        self.count = count
        self.interval = interval
        self.protocol = None  # set in __call__

    def __call__(self, protocol, *args):
        SSHCommand.__init__(self, protocol, self.name, *args)
        return self

    def start(self):
        for i in range(self.count):
            self.write("Line %d\n" % (i + 1))
            time.sleep(self.interval)

        self.exit()


class SkippingLineCommand(SSHCommand):
    def __init__(self, name, lines, *args):
        self.name = name
        self.lines = lines
        self.protocol = None  # set in __call__

    def __call__(self, protocol, *args):
        SSHCommand.__init__(self, protocol, self.name, *args)
        return self

    def start(self):
        for _ in range(self.lines):
            self.write("\r\n")

        self.write("%s lines skipped!\n" % self.lines)
        self.exit()


def exit_command_success(instance):
    instance.protocol.call_command(instance.protocol.commands['_exit'])


def passwd_change_protocol_prompt(instance):
    instance.protocol.prompt = "hostname#"
    instance.protocol.password_input = False

def passwd_write_password_to_transport(instance):
    instance.writeln("MockSSH: password is %s" % instance.valid_password)


class KeystrokeAnsweredCommand(SSHCommand):
    def __init__(self, name):
        self.name = name
        self.protocol = None  # set in __call__

    def __call__(self, protocol, *args):
        SSHCommand.__init__(self, protocol, self.name, *args)
        return self

    def start(self):
        self.write("whatup?")

        this = self

        def finish():
            this.writeln("k")
            this.writeln("K pressed")
            this.exit()
            this.protocol.keyHandlers.pop("k")

        self.protocol.keyHandlers.update({"k": finish})




