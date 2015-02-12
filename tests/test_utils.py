# Copyright 2015 Novo Nordisk Foundation Center for Biosustainability, DTU.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from unittest import TestCase
from potion_client import utils


class UtilsTestCase(TestCase):

    def test_camelize(self):
        self.assertEqual("SnakeCase", utils.camelize("snake_case"))
        self.assertEqual("DNA", utils.camelize("D_N_A"))
        self.assertEqual("Dna", utils.camelize("DNA"))

    def test_snake_case(self):
        pass

    def test_types(self):
        self.assertEqual(utils.type_for("object"), [dict])
        self.assertEqual(utils.type_for("array"), [list])
        self.assertEqual(utils.type_for("number"), [float])
        self.assertEqual(utils.type_for("string"), [str])
        self.assertEqual(utils.type_for("integer"), [int])
        self.assertEqual(utils.type_for("boolean"), [bool])
        self.assertEqual(utils.type_for("null"), [type(None)])