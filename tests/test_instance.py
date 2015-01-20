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

    def _create_foo(self):
        self.foo = self.potion_client.Foo()
        self.foo.attr1 = "value1"
        self.foo.attr2 = "value2"
        self.foo.save()

    def setUp(self):
        super(InstanceTestCase, self).setUp()
        with HTTMock(self.get_mock):
            self.potion_client = Client()

    def test_create_foo(self):
        with HTTMock(self.post_mock):
            self._create_foo()
            self.assertEqual(self.foo._instance, {"$uri": "/foo/1",
                                                  "attr1": "value1",
                                                  "attr2": "value2",
                                                  "bars": [],
                                                  "baz": None})

    def test_add_instance(self):
        with HTTMock(self.post_mock, self.get_mock):
            self._create_foo()
            bar = self.potion_client.Bar()
            bar.attr1 = 5
            bar.foo = self.foo
            bar.save()
            self.foo.refresh()
            self.assertIn(bar, self.foo.bars)

    def test_get_foo(self):
        with HTTMock(self.post_mock, self.get_mock):
            self._create_foo()
            other_foo = self.potion_client.Foo(1)
            self.assertEqual(self.foo, other_foo)

    def test_search_foo(self):
        with HTTMock(self.post_mock, self.get_mock):
            self._create_foo()
            foo_by_attr = self.potion_client.Foo.instances(where={"attr1": {"$text": "value1"}})
            self.assertEqual(len(foo_by_attr), 1)
            self.assertIn(self.foo, foo_by_attr)

    def test_change_foo(self):
        with HTTMock(self.post_mock, self.patch_mock):
            self._create_foo()
            self.foo.attr1 = "value3"
            self.foo.save()
            self.assertEqual(self.foo._instance, {"$uri": "/foo/1",
                                                  "attr1": "value3",
                                                  "attr2": "value2",
                                                  "bars": [],
                                                  "baz": None})

    # TODO: it doesn't not return a json response
    def test_delete_foo(self):
        with HTTMock(self.delete_mock, self.post_mock):
            self._create_foo()
            self.foo.destroy()