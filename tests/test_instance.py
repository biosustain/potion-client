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

from httmock import HTTMock
from potion_client import Client
from potion_client_testing import MockAPITestCase


class InstanceTestCase(MockAPITestCase):

    def setUp(self):
        super(InstanceTestCase, self).setUp()
        with HTTMock(self.get_mock):
            self.potion_client = Client()
            self.foo = self.potion_client.Foo()
            self.foo.attr1 = "value1"
            self.foo.attr2 = "value2"
            self.foo.bars = []

    def test_create_foo(self):
        with HTTMock(self.post_mock):
            self.foo.save()
            self.assertEqual(self.foo._instance, {"$uri": "/foo/1",
                                                  "attr1": "value1",
                                                  "attr2": "value2",
                                                  "bars": [],
                                                  "baz": None})

    def test_add_instance(self):
        with HTTMock(self.post_mock):
            bar = self.potion_client.Bar()
            bar.attr1 = 5
            self.foo.save()
            bar.foo = self.foo
            bar.save()

    def test_change_foo(self):
        with HTTMock(self.post_mock, self.patch_mock):
            self.foo.save()
            self.foo.attr1 = "value3"
            self.foo.save()
            self.assertEqual(self.foo._instance, {"$uri": "/foo/1",
                                                  "attr1": "value1",
                                                  "attr2": "value3",
                                                  "bars": [],
                                                  "baz": None})

    def test_delete_foo(self):
        with HTTMock(self.delete_mock, self.post_mock):
            self.foo.save()
            self.foo.destroy()

