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
import json
from httmock import HTTMock
from potion_client import Client
from potion_client_testing import MockAPITestCase


class CreateClientTestCase(MockAPITestCase):

    def setUp(self):
        super(CreateClientTestCase, self).setUp()

    def test_init_client(self):
        with HTTMock(self.get_mock):
            c = Client()
            self.assertSetEqual(set(c._schema['properties'].keys()),
                                {'foo', 'bar', 'baz', 'biz', 'foo_with_mapped_biz'})
            self.assertEqual(c._schema['properties']['foo'], json.loads(self.decode(self.client.get("/foo/schema"))))
            self.assertEqual(c._schema['properties']['bar'], json.loads(self.decode(self.client.get("/bar/schema"))))
            self.assertEqual(c._schema['properties']['baz'], json.loads(self.decode(self.client.get("/baz/schema"))))
            self.assertEqual(c._schema['properties']['biz'], json.loads(self.decode(self.client.get("/biz/schema"))))
            self.assertEqual(c._schema['properties']['foo_with_mapped_biz'],
                             json.loads(self.decode(self.client.get("/foo_with_mapped_biz/schema"))))