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

import time

from MockSSH import SSHCommand


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

class AmbiguousCommand(SSHCommand):
    def __init__(self, name, *args):
        self.name = name
        self.protocol = None  # set in __call__

    def __call__(self, protocol, *args):
        SSHCommand.__init__(self, protocol, self.name, *args)
        return self

    def start(self):
        self.write("working -> done!\n")
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




