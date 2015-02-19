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

from datetime import datetime, timezone
from httmock import HTTMock
from potion_client import Client
from potion_client.routes import MappedAttributeDict
from potion_client_testing import MockAPITestCase


class InstancesTestCase(MockAPITestCase):

    def _create_foo(self, attr1="value1", attr2="value2"):
        foo = self.potion_client.Foo()
        foo.attr1 = attr1
        foo.attr2 = attr2
        foo.attr3 = "attr3"
        foo.date = self.time
        foo.save()
        return foo

    def _create_foo_with_mapped_biz(self, attr1="value1"):
        foo = self.potion_client.FooWithMappedBiz()
        foo.attr1 = attr1
        foo.date = self.time
        foo.save()
        return foo

    def _create_bar(self, attr1=5, foo=None):
        bar = self.potion_client.Bar()
        bar.attr1 = attr1
        bar.foo = foo
        bar.save()
        return bar

    def _create_baz(self, attr1=1.0, attr2=None, foo=None):
        baz = self.potion_client.Baz(attr1=attr1, foo=foo, attr2=None)
        baz.save()
        return baz

    def _create_biz(self, attr1="value1", attr2=1.0):
        biz = self.potion_client.Biz(attr1=attr1, attr2=attr2)
        biz.save()
        return biz

    def setUp(self):
        MockAPITestCase.setUp(self)
        self.time = datetime.fromtimestamp(0, timezone.utc)
        with HTTMock(self.get_mock):
            self.potion_client = Client()

    def test_one_to_one(self):
        with HTTMock(self.post_mock, self.get_mock):
            foo = self._create_foo()
            self._create_foo()
            self._create_foo()
            baz = self._create_baz(foo=foo)
            query = self.potion_client.Foo.instances.where(baz=baz)
            self.assertEqual(len(query), 1)
            self.assertIn(foo, query)

    def test_create_foo(self):
        with HTTMock(self.post_mock):
            foo = self._create_foo()

            expected = {
                "$uri": "/foo/1",
                "attr1": "value1",
                "attr2": "value2",
                "bars": [],
                "baz": None,
                "date": self.time
            }
            for key in expected.keys():
                self.assertEqual(getattr(foo, key), expected[key])

    def test_add_one_to_many(self):
        with HTTMock(self.post_mock, self.get_mock):
            foo = self._create_foo()
            bar = self._create_bar(foo=foo)
            foo.refresh()
            self.assertIn(bar, foo.bars)

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

            instances = self.potion_client.Foo.instances.where(attr2={"$startswith": "value3"})
            self.assertEqual(len(instances), 1)

    def test_get_foo(self):
        with HTTMock(self.post_mock, self.get_mock):
            foo = self._create_foo()
            other_foo = self.potion_client.Foo(1)
            self.assertEqual(foo, other_foo)

    def test_search_foo(self):
        with HTTMock(self.post_mock, self.get_mock):
            foo = self._create_foo()
            self._create_foo(attr1="value3")
            foo_by_attr = self.potion_client.Foo.instances.where(attr1={"$startswith": "value1"})
            len(foo_by_attr)
            self.assertEqual(len(foo_by_attr), 1)
            self.assertIn(foo, foo_by_attr)

    def test_change_foo(self):
        with HTTMock(self.post_mock, self.patch_mock):
            foo = self._create_foo()
            foo.attr1 = "value3"
            foo.save()
            expected = {
                "$uri": "/foo/1",
                "attr1": "value3",
                "attr2": "value2",
                "bars": [],
                "baz": None,
                "date": self.time}
            for key in expected.keys():
                self.assertEqual(getattr(foo, key), expected[key])

    def test_delete_foo(self):
        with HTTMock(self.delete_mock, self.post_mock):
            foo = self._create_foo()
            self.assertEqual(foo.destroy(), None)

    def test_any_field(self):
        with HTTMock(self.post_mock, self.get_mock, self.patch_mock):
            foo = self._create_foo()
            baz = self._create_baz(attr1=2, foo=foo)
            self.assertEqual(baz.attr2, None)
            baz.attr2 = {}
            baz.save()
            self.assertEqual(baz.attr2, {})
            baz.attr2 = {"a": 1}
            baz.save()
            self.assertEqual(baz.attr2, {"a": 1})
            baz.attr2 = None
            baz.save()
            self.assertEqual(baz.attr2, None)
            baz.attr2 = ["a", 2, 2.1, {"a": 2}]
            baz.save()
            self.assertEqual(baz.attr2,  ["a", 2, 2.1, {"a": 2}])
            baz.attr2 = {"a": [123, 123, 456], "b": {}}
            baz.save()
            self.assertEqual(baz.attr2, {"a": [123, 123, 456], "b": {}})

    def test_item_attribute(self):
        with HTTMock(self.post_mock, self.get_mock, self.patch_mock):
            foo = self._create_foo()
            foo.update_attr3("value3")
            self.assertEqual(foo.read_attr3(), "value3")

    def test_empty_instances(self):
        with HTTMock(self.get_mock):
            self.assertEqual(self.potion_client.Foo.instances(), [])

    def test_mapped_attribute(self):
        with HTTMock(self.get_mock, self.post_mock, self.patch_mock):
            foo = self._create_foo_with_mapped_biz()
            self.assertIsInstance(foo.bizes, MappedAttributeDict)
            biz = self._create_biz()
            foo.bizes["bizzy1"] = biz
            foo.save()
            self.assertEqual(foo.bizes["bizzy1"], biz)
            foo = self.potion_client.FooWithMappedBiz(foo.id)
            self.assertEqual(foo.bizes["bizzy1"], biz)
            biz = self.potion_client.Biz(biz.id)
            self.assertEqual(foo.bizes["bizzy1"], biz)