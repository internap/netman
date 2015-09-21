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

import re
import telnetlib
from telnetlib import IAC, DO, DONT, WILL, WONT

from netman.adapters.terminal_client import TerminalClient, Timeout


class TelnetClient(TerminalClient):

    def __init__(self, host, username, password, port=23, prompt=('>', '#'),
                 connect_timeout=10, command_timeout=30, **_):
        self.prompt = prompt
        self.command_timeout = command_timeout

        self.full_log = ""

        self.telnet = _connect(host, port, connect_timeout)
        self._login(username, password)

    def do(self, command, wait_for=None, include_last_line=False):
        self.telnet.write(command + "\n")
        result = self._read_until(wait_for)

        return _filter_input_and_empty_lines(command, include_last_line, result)

    def send_key(self, key, wait_for=None, include_last_line=False):
        self.telnet.write(key)
        result = self._read_until(wait_for)

        return _filter_input_and_empty_lines(key, include_last_line, result)

    def quit(self, command):
        self.telnet.write(command + "\n")

    def get_current_prompt(self):
        return self.full_log.splitlines()[-1]

    def _login(self, username, password):
        self.telnet.read_until(":", self.command_timeout)
        self.telnet.write(username + "\n")
        self.telnet.read_until(":", self.command_timeout)
        self.telnet.write(password + "\n")

        result = self._wait_for(list(self.prompt))
        self.full_log += result[len(password):].lstrip()

    def _read_until(self, wait_for):
        expect = wait_for or self.prompt
        if isinstance(expect, basestring):
            expect = [expect]
        expect = [re.escape(s) for s in list(expect)]

        result = self._wait_for(expect)
        self.full_log += result

        return result

    def _wait_for(self, expect):
        result = self.telnet.expect(expect, timeout=self.command_timeout)
        if result[0] == -1:
            raise Timeout()
        return result[2]


def _connect(host, port, timeout):
    try:
        telnet = telnetlib.Telnet(host, port, timeout)
    except timeout:
        raise Timeout()

    telnet.set_option_negotiation_callback(_accept_all)
    return telnet


def _accept_all(sock, cmd, opt):
    print "received {} {}".format(ord(cmd), ord(opt))
    if cmd == WILL:
        sock.sendall(IAC + DO + opt)
    elif cmd == WONT:
        sock.sendall(IAC + DONT + opt)


def _filter_input_and_empty_lines(command, include_last_line, result):
    lines = result[len(command):].splitlines()
    if not include_last_line:
        lines = lines[:-1]
    return filter(None, lines)
