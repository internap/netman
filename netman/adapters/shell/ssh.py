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

from _socket import timeout, gaierror
import logging
import time

import paramiko
from netman.adapters import shell

from netman.adapters.shell.base import TerminalClient
from netman.core.objects.exceptions import CouldNotConnect, ConnectTimeout, CommandTimeout


class SshClient(TerminalClient):

    def __init__(self, host, username, password, port=22, prompt=('>', '#'), connect_timeout=None, command_timeout=None,
                 reading_interval=0.01, reading_chunk_size=9999):
        self.logger = logging.getLogger(__name__)

        self.host = host
        self.port = port
        self.username = username
        self.prompt = prompt
        self.command_timeout = command_timeout or shell.default_command_timeout
        self.connect_timeout = connect_timeout or shell.default_connect_timeout
        self.reading_interval = reading_interval
        self.reading_chunk_size = reading_chunk_size

        self.current_buffer = ''
        self.client = None
        self.channel = None
        self.full_log = ""

        self._open_channel(host, port, username, password, self.connect_timeout)

    def do(self, command, wait_for=None, include_last_line=False, use_connect_timeout=False):
        self.logger.debug("[SSH][{}@{}:{}] Send >> {}".format(self.username, self.host, self.port, command))

        self.channel.send(command + '\n')

        timeout = self.connect_timeout if use_connect_timeout else None
        return self._read_until(wait_for, include_last_line, timeout)

    def send_key(self, key, wait_for=None, include_last_line=False):
        self.logger.debug("[SSH][{}@{}:{}] Send KEY >> {}".format(self.username, self.host, self.port, key))

        self.channel.send(key)
        return self._read_until(wait_for, include_last_line)

    def quit(self, command):
        self.logger.debug("[SSH][{}@{}:{}] Quit >> {}".format(self.username, self.host, self.port, command))

        self.channel.send(command + '\n')

    def get_current_prompt(self):
        return self.current_buffer.splitlines()[-1]

    def _open_channel(self, host, port, username, password, connect_timeout):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.client.connect(host,
                                port=port,
                                username=username,
                                password=password,
                                timeout=connect_timeout,
                                allow_agent=False,
                                look_for_keys=False)
        except timeout:
            raise ConnectTimeout(host, port)
        except gaierror:
            raise CouldNotConnect(host, port)

        self.channel = self.client.invoke_shell()

        self._wait_for(self.prompt)

    def _read_until(self, wait_for, include_last_line, timeout=None):
        self._wait_for(wait_for or self.prompt, timeout)

        lines = self.current_buffer.splitlines()[1:]
        if not include_last_line:
            lines = lines[:-1]

        return filter(None, lines)

    def _wait_for(self, wait_for, timeout=None):
        self.current_buffer = ''

        started_at = time.time()
        while not self.current_buffer.endswith(wait_for):
            while not self.channel.recv_ready():
                if time.time() - started_at > (timeout or self.command_timeout):
                    raise CommandTimeout(wait_for, self.current_buffer)
                time.sleep(self.reading_interval)

            read = self.channel.recv(self.reading_chunk_size)
            self.logger.debug("[SSH][{}@{}:{}] Recv << {}".format(self.username, self.host, self.port, repr(read)))
            self.full_log += read
            self.current_buffer += read
