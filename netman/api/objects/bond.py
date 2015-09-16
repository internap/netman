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

from netman.api.objects import Serializable
from netman.core.objects.bond import Bond
from netman.api.objects.interface import SerializableInterface


class SerializableBond(Serializable):
    def __init__(self, src):
        super(SerializableBond, self).__init__(['number', 'link_speed', 'interface', 'members'])

        self.number = src.number
        self.link_speed = src.link_speed
        self.interface = SerializableInterface(src.interface)
        self.members = src.members

    @classmethod
    def to_core(cls, **serialized):
        return Bond(
            interface=SerializableInterface.to_core(**serialized.pop('interface')),
            ** serialized
        )
