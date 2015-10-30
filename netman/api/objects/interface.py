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

from netman.api.objects import sub_dict
from netman.api.objects import base_interface
from netman.core.objects.interface import Interface


def to_api(interface):
    return dict(
        base_interface.to_api(interface),
        name=interface.name,
        bond_master=interface.bond_master,
    )


def to_core(serialized):
    params = dict(vars(base_interface.to_core(serialized)))
    params.update(sub_dict(serialized, 'name', 'bond_master'))
    return Interface(**params)
