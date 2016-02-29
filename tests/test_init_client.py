import json
from unittest import TestCase
from urllib.parse import urlparse, parse_qs
import responses
from potion_client import Client, Resource, PotionJSONDecoder
from potion_client.converter import PotionJSONEncoder
from potion_client.collection import PaginatedList
from potion_client.exceptions import ItemNotFound

__author__ = 'lyschoening'


class ClientInitTestCase(TestCase):
    @responses.activate
    def test_read_schema(self):
        responses.add(responses.GET, 'http://example.com/api/schema', json={
            "properties": {
                "user": {"$ref": "/api/user/schema#"}
            }
        })

        responses.add(responses.GET, 'http://example.com/api/user/schema', json={
            "type": "object",
            "description": "The description for 'user'.",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The description for 'user.name'."
                }
            },
            "links": [
                {
                    "rel": "self",
                    "href": "/api/user/{id}",
                    "method": "GET",
                    "targetSchema": {
                        "$ref": "#"
                    }
                }
            ]
        })

        client = Client('http://example.com/api')

        self.assertTrue(issubclass(client.User, Resource))
        self.assertEqual("The description for 'user'.", client.User.__doc__)
        self.assertIsInstance(client.User.name, property)
        self.assertEqual("The description for 'user.name'.", client.User.name.__doc__)

    @responses.activate
    def test_fetch_instance(self):
        responses.add(responses.GET, 'http://example.com/api/schema', json={
            "properties": {
                "user": {"$ref": "/api/user/schema#"}
            }
        })

        responses.add(responses.GET, 'http://example.com/api/user/schema', json={
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "links": [
                {
                    "rel": "self",
                    "href": "/api/user/{id}",
                    "method": "GET"
                }
            ]
        })

        responses.add(responses.GET, 'http://example.com/api/user/123', json={
            "$uri": "/api/user/123",
            "name": "foo"
        })

        client = Client('http://example.com/api')
        user = client.User.fetch(123)

        print('user:', user)

        self.assertEqual({
            "$uri": "/api/user/123",
            "name": "foo"
        }, dict(user))

        self.assertEqual(client.instance('/api/user/123'), user)
        self.assertEqual("foo", user.name)
        self.assertEqual(123, user.id)

        self.assertEqual(user, client.User(123)._self())

    @responses.activate
    def test_create(self):
        responses.add(responses.GET, 'http://example.com/api/schema', json={
            "properties": {
                "user": {"$ref": "/api/user/schema#"}
            }
        })

        responses.add(responses.GET, 'http://example.com/api/user/schema', json={
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "links": [
                {
                    "rel": "self",
                    "href": "/api/user/{id}",
                    "method": "GET"
                },
                {
                    "rel": "create",
                    "href": "/api/user",
                    "method": "POST"
                }
            ]
        })

        def request_callback(request):
            request_data = json.loads(request.body)
            self.assertEqual({"name": "Mr. Foo"}, request_data)
            return 201, {}, json.dumps({
                '$uri': '/api/user/{}'.format(1),
                'name': request_data['name']
            })

        responses.add_callback(responses.POST, 'http://example.com/api/user',
                               callback=request_callback,
                               content_type='application/json')

        client = Client('http://example.com/api')

        user = client.User.create(name="Mr. Foo")

        self.assertEqual(1, user.id)
        self.assertEqual('Mr. Foo', user.name)

        # TODO user.save() for create

    @responses.activate
    def test_first(self):
        client = Client('http://example.com', fetch_schema=False)

        User = client.resource_factory('user', {
            "type": "object",
            "properties": {
                "$uri": {
                    "type": "string",
                    "readOnly": True
                },
                "name": {
                    "type": "string"
                }
            },
            "links": [
                {
                    "rel": "instances",
                    "method": "GET",
                    "href": "/user",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "number"},
                            "per_page": {"type": "number"},
                        }
                    }
                }
            ]
        })

        def request_callback(request):
            print(request)
            print(request.url)

            if 'missing' in request.url:
                return 200, {}, '[]'
            return 200, {}, json.dumps([{"$uri": "/user/1", "name": "foo"}])

        responses.add_callback(responses.GET, 'http://example.com/user',
                               callback=request_callback,
                               content_type='application/json')

        self.assertTrue(User.instances.returns_pagination())

        foo = User.first(where={"name": "foo"})
        self.assertEqual("foo", foo.name)

        with self.assertRaises(ItemNotFound):
            missing = User.first(where={"name": "missing"})


    @responses.activate
    def test_send_single_value(self):
        responses.add(responses.GET, 'http://example.com/api/schema', json={
            "properties": {
                "button": {"$ref": "/button/schema#"}
            }
        })

        responses.add(responses.GET, 'http://example.com/button/schema', json={
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "links": [
                {
                    "rel": "toggleAll",
                    "href": "/button/toggle-all",
                    "method": "POST",
                    "schema": {
                        "type": "boolean"
                    }
                }
            ]
        })

        def request_callback(request):
            request_data = json.loads(request.body)
            return 201, {}, json.dumps(request_data)

        responses.add_callback(responses.POST, 'http://example.com/button/toggle-all',
                               callback=request_callback,
                               content_type='application/json')

        client = Client('http://example.com/api')

        result = client.Button.toggle_all(False)
        self.assertEqual(False, result)

        result = client.Button.toggle_all(True)
        self.assertEqual(True, result)

    def test_resource_update_property(self):
        client = Client('http://example.com/api', fetch_schema=False)

        User = client.resource_factory('user', {
            "type": "object",
            "description": "The description for 'user'.",
            "properties": {
                "$uri": {
                    "type": "string",
                    "readOnly": True
                },
                "name": {
                    "type": "string"
                }
            },
            "links": []
        })

        user = User()
        user.name = 'foo'
        self.assertEqual('foo', user.name)
        self.assertEqual('foo', user['name'])
        self.assertEqual({
            "$uri": None,
            "name": "foo"
        }, user._properties)

        with self.assertRaises(AttributeError):
            user.uri = '/user/123'

    @responses.activate
    def test_instance_cache(self):
        responses.add(responses.GET, 'http://example.com/schema', json={
            "properties": {}
        })

        client = Client('http://example.com')

        foo_a = client.instance('/foo')
        foo_b = client.instance('/foo')
        self.assertIs(foo_a, foo_b)

    def test_singleton(self):
        client = Client('http://example.com/api', fetch_schema=False)

        User = client.resource_factory('user', {
            "type": "object",
            "description": "The description for 'user'.",
            "properties": {
                "$uri": {
                    "type": "string",
                    "readOnly": True
                },
                "name": {
                    "type": "string"
                }
            },
            "links": [
                {
                    "rel": "self",
                    "href": "/api/user/{id}",
                    "method": "GET"
                }
            ]
        })

        user_a = User('/api/user/123')
        user_b = User('/api/user/123')

        self.assertIs(user_a, user_b)

        user_c = User(123)
        self.assertIs(user_a, user_c)

    def test_decode_instance(self):
        client = Client('http://example.com', fetch_schema=False)

        User = client.resource_factory('user', {
            "type": "object",
            "properties": {
                "$uri": {
                    "type": "string",
                    "readOnly": True
                },
                "name": {
                    "type": "string"
                }
            },
            "links": [
                {
                    "rel": "instances",
                    "method": "GET",
                    "href": "/user"
                }
            ]
        })

        result = json.loads(json.dumps({
            "$uri": "/user/123",
            "name": "foo"
        }), cls=PotionJSONDecoder, client=client)

        self.assertEqual(client.instance('/user/123'), result)
        self.assertEqual("foo", result.name)
        self.assertEqual(123, result.id)

    def test_encode_reference(self):
        client = Client('http://example.com', fetch_schema=False)

        User = client.resource_factory('user', {
            "type": "object",
            "properties": {
                "$uri": {
                    "type": "string",
                    "readOnly": True
                },
                "name": {
                    "type": "string"
                }
            },
            "links": [
                {
                    "rel": "instances",
                    "method": "GET",
                    "href": "/user"
                }
            ]
        })

        result = json.loads(json.dumps({
            "owner": User(uri='/user/123', name="foo")
        }, cls=PotionJSONEncoder))

        self.assertEqual({
            "owner": {"$ref": "/user/123"}
        }, result)

    @responses.activate
    def test_pagination(self):
        client = Client('http://example.com', fetch_schema=False)

        User = client.resource_factory('user', {
            "type": "object",
            "properties": {
                "$uri": {
                    "type": "string",
                    "readOnly": True
                },
                "name": {
                    "type": "string"
                }
            },
            "links": [
                {
                    "rel": "self",
                    "href": "/user/{id}",
                    "method": "GET"
                },
                {
                    "rel": "instances",
                    "method": "GET",
                    "href": "/user",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "page": {
                                "default": 1,
                                "minimum": 1,
                                "type": "integer"
                            },
                            "per_page": {
                                "default": 20,
                                "maximum": 100,
                                "minimum": 1,
                                "type": "integer"
                            }
                        }
                    },
                    "target_schema": {
                        "$ref": "#"
                    }
                }
            ]
        })

        def request_callback(request):
            users = [
                {
                    "$uri": "/user/{}".format(i),
                    "name": "user-{}".format(i)
                } for i in range(1, 36)
                ]

            params = parse_qs(urlparse(request.url).query)
            offset = (int(params['page'][0]) - 1) * int(params['per_page'][0])
            return 200, {'X-Total-Count': '35'}, json.dumps(users[offset:offset + int(params['per_page'][0])])

        responses.add_callback(responses.GET, 'http://example.com/user',
                               callback=request_callback,
                               content_type='application/json')

        result = User.instances()

        # TODO test: result = User.instances(where={"foo": {"$gt": 123}})
        # TODO magic: result = User.instances.where(foo__gt=123).sort(foo=DESC)

        self.assertIsInstance(result, PaginatedList)
        self.assertEqual(35, len(result))
        self.assertEqual(1, len(result._pages))
        self.assertEqual([
                             {
                                 "$uri": "/user/{}".format(i),
                                 "name": "user-{}".format(i)
                             } for i in range(1, 36)
                             ], list(result))
        self.assertEqual(2, len(result._pages))
        self.assertEqual(20, len(result._pages[1]))
        self.assertEqual(15, len(result._pages[2]))

    def test_response_errors(self):
        pass

    def test_circular_response(self):
        pass

    def test_resource_first(self):
        pass
