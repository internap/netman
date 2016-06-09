# Copyright 2016 Internap.
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

from unittest import SkipTest

from tests import available_models
from tests.adapters.configured_test_case import ConfiguredTestCase
import sys


class ComplianceTestCase(ConfiguredTestCase):
    class __metaclass__(type):
        def __new__(mcs, name, bases, attrs):
            test_class = type.__new__(mcs, name, bases, attrs)
            if bases[0].__name__ == "ComplianceTestCase":
                _create_associated_test_classes(name, test_class)
            return test_class


def _create_associated_test_classes(test_case_name, test_class):
    test_class.__test__ = False
    for _specs in available_models:
        class_name = "{}{}".format(_specs["switch_descriptor"].model.capitalize(), test_case_name)
        new_test_class = type(class_name, (test_class,), {"__test__": True, "switch_specs": _specs})
        setattr(sys.modules[test_class.__module__], class_name,
                _wrap_tests_with_not_implemented_tolerance(new_test_class))


def _wrap_tests_with_not_implemented_tolerance(test_class):
    for method in dir(test_class):
        if method.startswith("test_") or method == "setUp":
            _wrap_test_method(method, test_class)
    return test_class


def _wrap_test_method(method, test_class):
    old_method = getattr(test_class, method)

    def wrapper(obj):
        try:
            old_method(obj)
        except NotImplementedError:
            raise SkipTest("Method is not implemented")
    wrapper.__name__ = method
    setattr(test_class, method, wrapper)
