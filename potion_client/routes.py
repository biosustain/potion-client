# Copyright 2014 Novo Nordisk Foundation Center for Biosustainability, DTU.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from functools import partial
import string
from urllib.parse import urlparse, ParseResult
from jsonschema import validate
import requests
from potion_client import utils
from .constants import *
import logging
from potion_client.exceptions import HTTP_EXCEPTIONS

logger = logging.getLogger(__name__)
logger.level = logging.DEBUG


_string_formatter = string.Formatter()


class LinkProxy(object):
    def __init__(self, link, binding, **kwargs):
        assert isinstance(link, (Link, type(None))), "Invalid link type (%s) for proxy" % type(link)
        assert isinstance(binding, (Resource, type(Resource))), "Invalid link type (%s) for object" % type(object)
        self.link = link
        self.binding = binding
        self._kwargs = kwargs
        self._parse_schema()

    def _parse_schema(self):
        if self.link.schema.get(ADDITIONAL_PROPERTIES, False):
            for prop in self.link.schema[PROPERTIES].keys():
                setattr(self, prop, self._proxy(prop))

    def __call__(self, *args, **kwargs):
        self._kwargs.update(kwargs)
        return self.link(*args, binding=self.binding, **self._kwargs)

    def __repr__(self):
        return "[Proxy %s '%s']" % (self.link.method, self.link.route.path)

    def _proxy(self, name):

        def fun(*args, **kwargs):
            _kwargs = self._kwargs
            if len(args) > 0:
                assert len(kwargs) == 0, "Cannot set kwargs and args for %s" % name
                _kwargs[name] = args
            else:
                _kwargs[name] = kwargs

            return LinkProxy(self.link, self.binding, **_kwargs)
        return fun


class Route(object):
    def __init__(self, path):
        self.default = None
        self.path = path
        self.keys = utils.extract_keys(path)

    @property
    def is_instance(self):
        return len(self.keys) > 0

    def extract_keys(self, resource):
        object_values = dict([(key, getattr(resource, key)) for key in self.keys])
        for key, val in object_values.items():
            if val is None:
                object_values[key] = ""
        return object_values


class LazyCollection(object):

    def __init__(self, collection, total):
        self.collection = collection
        self.pointer = 0
        self.total = total

    def __len__(self):
        return self.total

    def __next__(self):
        if self.pointer < len(self.collection.items):
            item = self.collection[self.pointer]
            self.pointer += 1
        else:
            if hasattr(self.collection, "next"):
                self.collection = self.collection.next()
                item = self.collection[0]
                self.pointer = 1
            else:
                raise StopIteration
        return item

    def __iter__(self):
        if hasattr(self.collection, 'first'):
            self.collection = self.collection.first()
        return self

    def __getitem__(self, index):
        slice_size, current_page, last_page, min_i, max_i, limit_i = self._current_page_limits()
        if index < 0:
            pass
        elif index >= limit_i:
            raise IndexError("Index out of bounds (%i)" % index)
        else:
            page = int(index/slice_size) + 1
            if page != current_page:
                self.collection = self.collection.get_page(page)
                slice_size, current_page, last_page, min_i, max_i, limit_i = self._current_page_limits()

            i = index - min_i
            return self.collection[i]

    def _current_page_limits(self):
        slice_size = self.collection.slice
        current_page = self.collection.page
        last_page = self.collection.last_page
        if last_page is None:
            last_page = current_page
        limit_i = slice_size * last_page
        min_i = slice_size * (current_page - 1)
        max_i = min_i + slice_size
        return slice_size, current_page, last_page, min_i, max_i, limit_i


class LazyCollectionSlice(object):

    @classmethod
    def from_url(cls, path, client, params, **kwargs):
        url = urlparse(client.base_url + path)
        params.update(utils.params_to_dictionary(url.query))
        query = utils.dictionary_to_params(params)
        url = ParseResult(url.scheme, url.netloc, url.path, url.params, query, url.fragment)
        response = requests.get(url.geturl(), **kwargs)
        return LazyCollectionSlice(response.json(), response.links, client, params, **kwargs)

    @classmethod
    def from_params(cls, path, client, params, **kwargs):
        url = urlparse(client.base_url + path)
        new_params = utils.params_to_dictionary(url.query)
        new_params.update(params)
        query = utils.dictionary_to_params(new_params)
        url = ParseResult(url.scheme, url.netloc, url.path, url.params, query, url.fragment)
        response = requests.get(url.geturl(), **kwargs)
        return LazyCollectionSlice(response.json(), response.links, client, params, **kwargs)

    def __init__(self, items, links, client, params, **request_kwargs):
        self.items = items
        self.links = links
        self.request_kwargs = request_kwargs
        self.client = client
        self.params = params
        self.page = None
        self.last_page = None
        self.slice = None

        if self.links is not None:
            self._parse_links()
            self._create_links()

    def _parse_links(self):
        if 'self' in self.links:
            link = self.links['self']
            parse_url = urlparse(link[URL])
            params = utils.params_to_dictionary(parse_url.query)
            self.params['page'] = self.page = int(params['page'])
            self.params['per_page'] = self.slice = int(params['per_page'])

        if 'last' in self.links:
            link = self.links['last']
            parse_url = urlparse(link[URL])
            params = utils.params_to_dictionary(parse_url.query)
            self.last_page = int(params['page'])
        else:
            self.last_page = int(self.params['page'])

    def _create_links(self):
        for link_name, link_desc in self.links.items():
            f = partial(self.from_url, link_desc[URL], self.client, self.params, **self.request_kwargs)
            setattr(self, link_name, f)

    def __getitem__(self, index):
        item = self.client.resolve_element(self.items[index])
        return item

    def get_page(self, page):
        self_link = self.links['self']
        params = {"page": page}
        return self.from_params(self_link[URL], self.client, params, **self.request_kwargs)


class Link(object):
    def __init__(self, route, method=GET, schema=None, target_schema=None, requests_kwargs=None):
        self.route = route
        self.method = method
        self.schema = schema
        self.target_schema = target_schema
        self.request_kwargs = requests_kwargs

    def __call__(self, *args, binding=None, resolve=True, **kwargs):
        # TODO: set the proper schema for input
        url = self.generate_url(binding, self.route)
        json, params = self._process_args(binding, *args, **kwargs)
        res = requests.request(self.method, url=url, json=json, params=params, **self.request_kwargs)
        print(res.text)
        if res.status_code >= 400:
            raise HTTP_EXCEPTIONS.get(res.status_code, RuntimeError("Error: %i\nMessage: %s" % (res.status_code, res.text)))
        res_obj = res.json()

        # TODO: set the proper schema for output
        self.target_schema = {}
        valid_res = self._validate_out(res_obj, binding)
        if not resolve:
            return valid_res

        if isinstance(valid_res, list):
            collection = LazyCollectionSlice(valid_res, res.links, binding.client, params, **self.request_kwargs)
            return LazyCollection(collection, int(res.headers["X-Total-Count"]))

        return binding.client.resolve_element(valid_res)

    def generate_url(self, obj, route):
        base_url = obj.client.base_url
        url = "{base}{path}".format(base=base_url, path=route.path)
        if isinstance(obj, Resource):
            url = url.format(**{k: getattr(obj, str(k)) for k in self.route.keys})
        if url.endswith("/"):
            return url[0:-1]
        logger.debug("Generated url: %s" % url)
        return url

    def _process_args(self, binding, *args, **kwargs):
        json, params = None, None
        if len(args) == 1:
            args = args[0]
        if self.method in [POST, PATCH]:
            args = self._check_input(args)
            json = self._validate_in(args, binding)
        else:
            params = self._validate_in(kwargs, binding)

        return json, params

    def _check_input(self, obj):
        if isinstance(obj, Resource):
            return self._check_input(obj.instance)
        elif isinstance(obj, (list, tuple)):
            return [self._check_input(el) for el in obj]
        elif isinstance(obj, dict):
            for key, value in obj.items():
                obj[key] = self._check_input(value)
            return obj
        else:
            return obj

    def _validate_params(self, params):
        utils.validate_schema(self.schema, params)
        for param in self.schema[PROPERTIES]:
            if 'default ' in self.schema[PROPERTIES][param]:
                if param not in params:
                    params[param] = self.schema[PROPERTIES][param]['default']
        return params

    def _validate_in(self, params, binding):
        if REF in self.schema and self.schema[REF] == "#":
            self.schema = getattr(binding, "_schema")
        return utils.validate_schema(self.schema, params)

    def _validate_out(self, out, binding):
        if REF in self.schema and self.schema[REF] == "#":
            self.target_schema = getattr(binding, "_schema")
        return utils.validate_schema(self.target_schema, out)

    def __repr__(self):
        return "[Link %s '%s']" % (self.method, self.route.path)


class Resource:
    client = None
    _schema = None
    _instance_links = None
    _self_route = None

    def __init__(self, oid=None, instance=None):
        self._create_proxies()
        self._id = oid
        self._instance = instance
        if oid is None:  # make a new object
            self._instance = {}

    @property
    def instance(self):
        instance = {}

        for key in self.properties.keys():
            read_only = self.properties[key].get(READ_ONLY, False)
            value = self._instance.get(key, None)
            if value is None:
                value = utils.convert_value(value, self.properties[key])

            if not read_only and value is not None:
                instance[key] = value

        return instance

    def _create_proxies(self):
        for name, link in self._instance_links.items():
            setattr(self, name, LinkProxy(link, self))

    @property
    def properties(self):
        return self._schema.get(PROPERTIES, {})

    def __getattr__(self, key):
        if key in self._schema[PROPERTIES]:
            self._ensure_instance()
            item = self._instance.get(key, None)
            if isinstance(item, list):
                return utils.evaluate_list(item, self.client)
            else:
                return self.client.resolve_element(item)
        else:
            getattr(super(Resource, self), key, self)

    def __setattr__(self, key, value):
        assert not key.startswith("$"), "Invalid property %s" % key

        if key in self._schema[PROPERTIES]:
            property_definition = self._define_property(key)
            value = utils.convert_value(value, property_definition)

            validate(value, property_definition)
            self._ensure_instance()
            self._instance[key] = value
        else:
            super(Resource, self).__setattr__(key, value)

    def _define_property(self, key):
        if REF in self._schema[PROPERTIES][key]:
            self._schema[PROPERTIES][key] = self.client.resolve(self._schema[PROPERTIES][key][REF],
                                                                target_schema=self._schema)
        definition = self._schema[PROPERTIES][key]
        return definition

    def _ensure_instance(self):
        if self._instance is None:
            self._instance = self.self(resolve=False)

    def save(self):
        if self.id is None:
            assert isinstance(self.create, LinkProxy)
            self._instance = self.create(self, resolve=False)
        else:
            assert isinstance(self.update, LinkProxy)
            self._instance = self.update(self, resolve=False)

    def refresh(self):
        self._instance = self.self(resolve=False)

    @property
    def id(self):
        if self._id is None:
            if self._instance and (URI in self._instance):
                self._id = utils.parse_uri(self._instance[URI])[-1]
        return self._id

    def __dir__(self):
        return super(Resource, self).__dir__() + list(self._schema[PROPERTIES].keys())

    @property
    def uri(self):
        self._ensure_instance()
        if URI in self._instance:
            return self._instance[URI]

    @classmethod
    def factory(cls, docstring, name, schema, requests_kwargs, client):
        class_name = utils.camelize(name)

        resource = type(class_name, (cls, ), {})
        resource.__doc__ = docstring
        resource._schema = schema
        resource.client = client
        resource._instance_links = {}

        routes = {}

        for link_desc in schema[LINKS]:
            if link_desc[HREF] in routes:
                route = routes[link_desc[HREF]]
            else:
                route = Route(link_desc[HREF])
                routes[link_desc[HREF]] = route

            link = Link(route,
                        method=link_desc[METHOD],
                        schema=link_desc.get(SCHEMA, {}),
                        target_schema=link_desc.get(TARGET_SCHEMA, {}),
                        requests_kwargs=requests_kwargs)

            if route.is_instance:
                resource._instance_links[link_desc[REL]] = link
            else:
                setattr(resource, link_desc[REL], LinkProxy(link, resource))

        return resource

    def __str__(self):
        return "<%s %s: %s>" % (self.__class__, getattr(self, "id"), str(self._instance))

    def __eq__(self, other):
        if self.uri and other.uri:
            return self.uri == other.uri
        else:
            super(Resource, self).__eq__(other)