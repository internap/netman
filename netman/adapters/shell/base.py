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


class TerminalClient(object):
    _default_command_timeout = 300
    _default_connect_timeout = 60

    def do(self, command, wait_for=None, include_last_line=False):
        raise NotImplemented()

    def send_key(self, key, wait_for=None, include_last_line=False):
        raise NotImplemented()

    def quit(self, command):
        raise NotImplemented()

    def get_current_prompt(self):
        raise NotImplemented()

    @staticmethod
    def set_default_command_timeout(command_timeout):
        TerminalClient._default_command_timeout = command_timeout

    @staticmethod
    def set_default_connect_timeout(connect_timeout):
        TerminalClient._default_connect_timeout = connect_timeout
