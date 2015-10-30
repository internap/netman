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

from netman.api.objects import base_interface
from netman.api.objects import sub_dict
from netman.core.objects.bond import Bond


def to_api(bond):
    return dict(
        number=bond.number,
        link_speed=bond.link_speed,
        members=bond.members,
        **base_interface.to_api(bond)
    )


def to_core(api_bond):
    params = dict(vars(base_interface.to_core(api_bond)))
    params.update(sub_dict(api_bond, 'number', 'link_speed', 'members'))
    return Bond(**params)
