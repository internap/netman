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
# limitations under the License

import MockSSH

from fake_switches.terminal.telnet import StatefulTelnet


class MockTelnet(StatefulTelnet):
    """
    This aims to act as a telent server over the SAME contract as MockSSH
    Taking the same commands and making them work the same ensure
    the same test code can be applied to SSH and Telnet
    """

    def __init__(self, prompt, commands):
        self._password_input = False

        super(MockTelnet, self).__init__()
        self.prompt = prompt
        self.commands = {c.name: c for c in commands}
        self.cmdstack = []
        self.password_input = False
        self.terminal = self

        self.commands["_exit"] = ExitCommand("_exit")

    @property
    def password_input(self):
        return self._password_input

    @password_input.setter
    def password_input(self, value):
        if self._password_input != value:
            self._password_input = value
            if self._password_input:
                self.enable_input_replacement("")
            else:
                self.disable_input_replacement()

    def connectionMade(self):
        super(MockTelnet, self).connectionMade()
        self.keyHandlers = self._key_handlers
        self.write('Username:')
        self.handler = self.validate_username

    def loseConnection(self):
        self.connectionLost("requested")

    def validate_username(self, _):
        self.write('Password:')
        self.handler = self.validate_password

    def validate_password(self, _):
        self.cmdstack = [RootCommand(self)]
        self.cmdstack[0].resume()
        self.handler = self.command

    def show_prompt(self):
        self.write(self.prompt)

    def command(self, data):
        line = data.rstrip()
        if len(self.cmdstack) > 1:
            self.cmdstack[-1].lineReceived(line)
        else:
            parts = line.split(" ")
            command = parts[0]
            if command in self.commands:
                self.call_command(self.commands[command], parts)

    def call_command(self, cmd, parts=None):
        cmd(self)
        cmd.args = parts
        self.cmdstack.append(cmd)
        cmd.start()

    def nextLine(self):
        return self.next_line()


class RootCommand(object):
    def __init__(self, terminal):
        self.terminal = terminal

    def resume(self):
        self.terminal.show_prompt()


class ExitCommand(MockSSH.command_exit):
    def __init__(self, name, *args):
        self.name = name

    def __call__(self, protocol, *args):
        MockSSH.SSHCommand.__init__(self, protocol, self.name, *args)
        return self
