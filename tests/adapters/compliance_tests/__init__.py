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


from tests.adapters.configured_test_case import ConfiguredTestCase
from tests.adapters.model_list import available_models

from unittest import SkipTest
import inspect
import sys
import os


def _add_tests_for_model(current_module, test_classes, specs):
    for test_class in test_classes:
        test_class.__test__ = False

        class_name = "{}{}".format(specs["switch_descriptor"].model.capitalize(), test_class.__name__)
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


def _is_class_child_of(obj, parent_class):
    return (inspect.isclass(obj) and
            (not obj.__name__.startswith('_')) and
            issubclass(obj, parent_class) and
            (inspect.getmro(obj)[0] is not parent_class))


def _import_module(import_str):
    __import__(import_str)
    return sys.modules[import_str]


def _get_classes_from_module(module_name, class_type):
    classes = []
    module = _import_module(module_name)
    for obj_name in dir(module):
        if obj_name.startswith('_'):
            continue
        itm = getattr(module, obj_name)
        if _is_class_child_of(itm, class_type):
            classes.append(itm)
    return classes


def _get_classes_of_type_from_directory(class_type, dir_name):
    classes = []

    for dirpath, dirnames, filenames in os.walk(dir_name):
        relpath = os.path.relpath(dirpath, dir_name)
        if relpath == '.':
            relpkg = ''
        else:
            relpkg = '.%s' % '.'.join(relpath.split(os.sep))
        for fname in filenames:
            root, ext = os.path.splitext(fname)
            if ext != '.py' or root == '__init__':
                continue
            module_name = "%s%s.%s" % (__package__, relpkg, root)
            mod_classes = _get_classes_from_module(module_name, class_type)
            classes.extend(mod_classes)
    return classes

_test_classes = _get_classes_of_type_from_directory(ConfiguredTestCase, os.path.dirname(__file__))

for _specs in available_models:
    _add_tests_for_model(globals(), _test_classes, _specs)
