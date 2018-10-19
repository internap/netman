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

import threading

from fake_switches.switch_configuration import SwitchConfiguration


class ThreadedReactor(threading.Thread):

    _threaded_reactor = None

    @classmethod
    def start_reactor(cls, models, reactor_hook_callbacks):
        cls._threaded_reactor = ThreadedReactor()

        for callback in reactor_hook_callbacks:
            callback(cls._threaded_reactor.reactor)

        for specs in models:
            switch_descriptor = specs["switch_descriptor"]

            switch_config = SwitchConfiguration(
                ip=switch_descriptor.hostname,
                name="my_switch",
                privileged_passwords=[switch_descriptor.password],
                ports=specs["ports"])

            specs["service_class"](
                switch_descriptor.hostname,
                port=switch_descriptor.port,
                switch_core=specs["core_class"](switch_config),
                users={switch_descriptor.username: switch_descriptor.password}
            ).hook_to_reactor(cls._threaded_reactor.reactor)

        cls._threaded_reactor.start()

    @classmethod
    def stop_reactor(cls):
        cls._threaded_reactor.stop()

    def __init__(self, *args, **kwargs):
        threading.Thread.__init__(self, *args, **kwargs)
        from twisted.internet import reactor
        self.reactor = reactor

    def run(self):
        self.reactor.run(installSignalHandlers=False)

    def stop(self):
        self.reactor.callFromThread(self.reactor.stop)
