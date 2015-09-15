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

import importlib
import unittest


class ExceptionsComplianceTest(unittest.TestCase):

    def test_for_remote_use_all_exceptions_should_be_instantiable_without_an_argument(self):

        exceptions_module = importlib.import_module("netman.core.objects.exceptions")

        for attribute in dir(exceptions_module):
            exception_class = getattr(exceptions_module, attribute)
            if isinstance(exception_class, type):
                try:
                    exception_class()
                except:
                    raise AssertionError("Class {0} should be instantiable with no params".format(attribute))

