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
import time
from potion_client import Client
from potion_client_testing import MockAPITestCase


class InstanceTestCase(MockAPITestCase):

    def _create_foo(self, attr1="value1", attr2="value2"):
        self.foo = self.potion_client.Foo()
        self.foo.attr1 = attr1
        self.foo.attr2 = attr2
        self.foo.date = self.time
        self.foo.save()

    def setUp(self):
        super(InstanceTestCase, self).setUp()
        self.time = int(time.time())
        with HTTMock(self.get_mock):
            self.potion_client = Client()

    def test_create_foo(self):
        with HTTMock(self.post_mock):
            self._create_foo()

            expected = {
                "$uri": "/foo/1",
                "attr1": "value1",
                "attr2": "value2",
                "bars": [],
                "baz": None,
                "date": self.time
            }
            for key in expected.keys():
                self.assertEqual(getattr(self.foo, key), expected[key])

    def test_add_instance(self):
        with HTTMock(self.post_mock, self.get_mock):
            self._create_foo()
            bar = self.potion_client.Bar()
            bar.attr1 = 5
            bar.foo = self.foo
            bar.save()
            self.foo.refresh()
            self.assertIn(bar, self.foo.bars)

    def test_multiple_foos(self):
        with HTTMock(self.post_mock, self.get_mock):
            self._create_foo(attr1="value1", attr2="value3")
            self._create_foo(attr1="value1", attr2="value4")
            self._create_foo(attr1="value1", attr2="value5")
            self._create_foo(attr1="value1", attr2="value6")
            self._create_foo(attr1="value1", attr2="value7")
            self._create_foo(attr1="value1", attr2="value8")
            self._create_foo(attr1="value1", attr2="value9")

            instances = self.potion_client.Foo.instances
            self.assertEqual(len(instances), 7)

            self._create_foo(attr1="value1", attr2="value10")
            self._create_foo(attr1="value1", attr2="value11")
            self._create_foo(attr1="value1", attr2="value12")
            self._create_foo(attr1="value1", attr2="value13")
            self._create_foo(attr1="value1", attr2="value14")
            self._create_foo(attr1="value1", attr2="value15")
            self._create_foo(attr1="value1", attr2="value16")

            instances = self.potion_client.Foo.instances
            self.assertEqual(len(instances), 14)

            self._create_foo(attr1="value1", attr2="value17")
            self._create_foo(attr1="value1", attr2="value18")
            self._create_foo(attr1="value1", attr2="value19")
            self._create_foo(attr1="value1", attr2="value20")
            self._create_foo(attr1="value1", attr2="value21")
            self._create_foo(attr1="value1", attr2="value22")
            self._create_foo(attr1="value1", attr2="value23")

            instances = self.potion_client.Foo.instances
            self.assertEqual(len(instances), 21)
            instances = self.potion_client.Foo.instances.per_page(5)
            self.assertEqual(instances.slice_size, 5)

            self.assertEqual(len(instances), 21)
            self.assertEqual([foo.attr2 for foo in instances], ["value%i" % i for i in range(3, 24)])

            instances = self.potion_client.Foo.instances.where(attr2="value3")
            self.assertEqual(len(instances), 1)

    def test_get_foo(self):
        with HTTMock(self.post_mock, self.get_mock):
            self._create_foo()
            other_foo = self.potion_client.Foo(1)
            self.assertEqual(self.foo, other_foo)

    def test_search_foo(self):
        with HTTMock(self.post_mock, self.get_mock):
            self._create_foo()
            foo_by_attr = self.potion_client.Foo.instances.where(attr1={"$text": "value1"})
            self.assertEqual(len(foo_by_attr), 1)
            self.assertIn(self.foo, foo_by_attr)

    def test_change_foo(self):
        with HTTMock(self.post_mock, self.patch_mock):
            self._create_foo()
            self.foo.attr1 = "value3"
            self.foo.save()
            expected = {
                "$uri": "/foo/1",
                "attr1": "value3",
                "attr2": "value2",
                "bars": [],
                "baz": None,
                "date": self.time}
            for key in expected.keys():
                self.assertEqual(getattr(self.foo, key), expected[key])

    # TODO: it doesn't not return a json response
    def test_delete_foo(self):
        with HTTMock(self.delete_mock, self.post_mock):
            self._create_foo()
            self.foo.destroy()