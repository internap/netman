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


from unittest import SkipTest

from tests.adapters.compliance_tests.get_interfaces_test import GetInterfacesTest
from tests.adapters.compliance_tests.add_vlan_test import AddVlanTest
from tests.adapters.model_list import available_models
from tests.adapters.compliance_tests.get_vlan_test import GetVlanTest

_test_classes = [
    GetVlanTest,
    AddVlanTest,
    GetInterfacesTest
]

# compliance rule of thumb:
# DELETING a resource (delete vlan) should raise if it doesn't exist
# functions are add / remove
# EMPTYING a resource (remove access vlan) doesnt raise
# functions are set / unset


def _add_tests_for_model(current_module, test_classes, specs):
    for test_class in test_classes:
        test_class.__test__ = False

        class_name = "{}{}".format(specs["model"].capitalize(), test_class.__name__)
        new_test_class = type(class_name, (test_class,), {"__test__": True, "switch_specs": specs})
        current_module[class_name] = _wrap_tests_with_not_implemented_tolerance(new_test_class)


def _wrap_tests_with_not_implemented_tolerance(test_class):
    for method in dir(test_class):
        if method.startswith("test_"):
            _wrap_test_method(method, test_class)

    return test_class


def _wrap_test_method(method, test_class):
    def wrapper(self):
        try:
            getattr(super(type(self), self), method)()
        except NotImplementedError:
            raise SkipTest("Method is not implemented")

    wrapper.__name__ = method
    setattr(test_class, method, wrapper)


for _specs in available_models:
    _add_tests_for_model(globals(), _test_classes, _specs)
