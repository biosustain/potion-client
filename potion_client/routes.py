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
import re
import string
from urllib.parse import urlparse
from jsonschema import validate
import requests
from potion_client import utils
from .constants import *
import logging
from potion_client.exceptions import NotFoundException
from potion_client.utils import params_to_dict, ditc_to_params

logger = logging.getLogger(__name__)
logger.level = logging.DEBUG


_string_formatter = string.Formatter()


class LinkProxy(object):
    def __init__(self, route_proxy, link):
        assert isinstance(link, (Link, type(None))), "Invalid link type (%s) for proxy" % type(link)
        self.route_proxy = route_proxy
        self.link = link

    def __call__(self, *args, **kwargs):
        return self.link(*args, obj=self.route_proxy.obj, **kwargs)


class RouteProxy(object):
    def __init__(self, route, obj):
        assert isinstance(route, Route), "Invalid route type (%s) for proxy" % type(route)
        assert isinstance(obj, (Resource, type)), "Invalid object type (%s) for proxy" % type(obj)
        self.route = route
        self.obj = obj
        self.default = None
        self._create_links_attributes()

    def _create_links_attributes(self):
        for link_name, link in self.route.links.items():
            setattr(self, link_name, LinkProxy(self, link))
        self.default = LinkProxy(self, self.route.default)

    def __call__(self, *args, **kwargs):
        return self.default(*args, **kwargs)

    @property
    def client(self):
        return self.obj.client


class Route(object):
    def __init__(self, path, name):
        self.default = None
        self.path = path
        self.name = name
        self.links = {}

    def __call__(self, *args, **kwargs):
        return self.default(*args, **kwargs)

    def generate_url(self, obj):
        base_url = obj.client.base_url
        url = "{base}{path}".format(base=base_url, path=self.path)
        logger.debug("Generated url: %s" % url)
        url = url.format(**self.extract_keys(obj, _string_formatter))
        if url.endswith("/"):
            return url[0:-1]
        return url

    def extract_keys(self, resource, formatter=_string_formatter):
        format_iterator = formatter.parse(self.path)
        object_values = dict([(t[1], getattr(resource, t[1])) for t in format_iterator if not t[1] is None])
        for key, val in object_values.items():
            if val is None:
                object_values[key] = ""
        return object_values


class LazyCollection(object):

    def __init__(self, collection):
        self.collection = collection
        self.pointer = 0

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
            print(page)
            if page != current_page:
                self.collection = self.collection.get_page(page)
                slice_size, current_page, last_page, min_i, max_i, limit_i = self._current_page_limits()

            print([slice_size, current_page, last_page, min_i, max_i, limit_i])
            i = index - min_i
            print(i)

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
        params.update(params_to_dict(url.query))
        url.query = ditc_to_params(params)
        response = requests.get(url.geturl(), **kwargs)
        return LazyCollectionSlice(response.json(), response.links, params, client, **kwargs)

    @classmethod
    def from_params(cls, path, client, params, **kwargs):
        url = urlparse(client.base_url + path)
        new_params = params_to_dict(url.query)
        new_params.update(params)
        url.query = ditc_to_params(new_params)
        response = requests.get(url.geturl(), **kwargs)
        return LazyCollectionSlice(response.json(), response.links, params, client, **kwargs)

    def __init__(self, items, links, client, params, **request_kwargs):
        self.items = items
        self.links = links
        self.request_kwargs = request_kwargs
        self.client = client
        self.params = params
        self.page = None
        self.last_page = None
        self.slice = None

        if not self.links is None:
            self._create_links()
            self._parse_links()

    def _parse_links(self):
        if 'self' in self.links:
            link = self.links['self']
            parse_url = urlparse(link[URL])
            params = params_to_dict(parse_url.query)
            self.params['page'] = self.page = int(params['page'])
            self.params['per_page'] = self.slice = int(params['per_page'])

        if 'last' in self.links:
            link = self.links['last']
            parse_url = urlparse(link[URL])
            params = params_to_dict(parse_url.query)
            self.last_page = int(params['page'])

    def _create_links(self):
        for link_name, link_desc in self.links.items():
            setattr(self, link_name, partial(self.from_url, link_desc[URL], self.client, **self.request_kwargs))

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

    def __call__(self, *args, obj=None, resolve=True, **kwargs):
        self.schema = self._resolve_schema(obj.client, self.schema)
        url = self.route.generate_url(obj)
        json, params = self._process_args(*args, **kwargs)
        res = requests.request(self.method, url=url, json=json, params=params, **self.request_kwargs)
        if res.status_code == 400:
            raise NotFoundException(url)
        elif res.status_code == 204:
            return None
        elif res.status_code > 400:
            raise RuntimeError("Error: %i\nMessage: %s" % (res.status_code, res.text))

        res_obj = res.json()
        valid_res = self._validate_out(res_obj)

        if not resolve:
            return valid_res

        if isinstance(valid_res, list):
            collection = LazyCollectionSlice(valid_res, res.links, obj.client, params, **self.request_kwargs)
            return LazyCollection(collection)

        return obj.client.resolve_element(valid_res)

    def _process_args(self, *args, **kwargs):
        json, params = None, None

        params = self._validate_in(kwargs)

        if self.method in [POST, PATCH]:
            params = self._validate_in(kwargs)
            args = self._check_input(args)
            json = self._validate_in(args)

        return json, params

    def _check_input(self, obj):
        if isinstance(obj, (list, tuple)):
            if len(obj) == 1:
                return self._check_input(obj[0])
            else:
                return [self._check_input(el) for el in obj]
        else:
            if isinstance(input, Resource):
                return obj._instance
            else:
                return obj

    def _resolve_schema(self, client, schema=None, default=None):
        if not schema is None:
            if isinstance(schema, dict):
                if REF in schema:
                    schema = client.resolve(schema[REF])

                for key, value in schema.items():
                    schema[key] = self._resolve_schema(client, value, value)
                return schema

        return default

    def _validate(self, schema, obj):
        if not schema is None:
            validate(obj, schema)
        return obj

    def _validate_params(self, input):
        self._validate(self.schema, input)
        for param in self.schema[PROPERTIES]:
            if 'default ' in self.schema[PROPERTIES][param]:
                if not param in input:
                    input[param] = self.schema[PROPERTIES][param]['default']
        return input

    def _validate_in(self, input):
        return self._validate(self.schema, input)

    def _validate_out(self, out):
        return self._validate(self.target_schema, out)


class Resource:
    client = None
    _schema = None
    _instance_routes = None
    _self_route = None

    def __init__(self, id=None, instance=None):
        self._create_route_proxies()
        self._id = id
        self._instance = instance
        if id is None:  # make a new object
            self._instance = {}

    def _create_route_proxies(self):
        for route in self._instance_routes:
            setattr(self, route.name, RouteProxy(route, self))

    def __getattr__(self, key):
        if key in self._schema[PROPERTIES]:
            self._ensure_instance()
            item = self._instance.get(key, None)
            if isinstance(item, list):
                return LazyCollectionSlice(item, {}, None)
            else:
                return self.client.resolve_element(item)
        else:
            getattr(super(Resource, self), key, self)

    def __setattr__(self, key, value):
        if key in self._schema[PROPERTIES]:
            property_def = self._schema[PROPERTIES][key]
            if REF in property_def:
                self._schema[PROPERTIES][key] = self.client.resolve(property_def[REF], target_schema=self._schema)
            validate(value,  self._schema[PROPERTIES][key])
            self._ensure_instance()
            self._instance[key] = value
        else:
            super(Resource, self).__setattr__(key, value)

    def _ensure_instance(self):
        if self._instance is None:
            self._instance = self.self_route(resolve=False)

    def save(self):
        validate(self._instance, self._schema)
        if self.id is None:
            self._instance = self.self_route.create(self._instance, resolve=False)
        else:
            self._instance = self.self_route.update(self._instance, resolve=False)

    @property
    def id(self):
        if self._id is None:
            if self._instance and (URI in self._instance):
                self._id = self._instance[URI].split("/")[-1]
        return self._id

    @property
    def self_route(self):
        return RouteProxy(self._self_route, self)

    def delete(self):
        if self.id is None:
            #raise some kind of error
            raise RuntimeError()
        else:
            self._ensure_instance()
            self.self_route.delete(self._instance[URI])
            self._id = None
            del self._instance[URI]

    def __dir__(self):
        return super(Resource, self).__dir__() + list(self._schema[PROPERTIES].keys())

    @classmethod
    def factory(cls, docstring, name, schema, requests_kwargs):
        class_name = utils.camelize(name)
        resource = type(class_name, (cls, ), {})
        resource.__doc__ = docstring
        resource._schema = schema
        resource._instance_routes = []
        routes = {}
        class_routes = []
        self_desc = list(filter(lambda l: l[REL] == SELF, schema[LINKS]))[0]

        self_route = Route(self_desc[HREF], SELF)
        resource._self_route = self_route
        self_link = Link(self_route,
                         method=self_desc[METHOD],
                         schema=self_desc.get(SCHEMA, {}),
                         target_schema=self_desc.get(TARGET_SCHEMA, {}),
                         requests_kwargs=requests_kwargs)

        self_route.default = self_link
        self_route.links["create"] = Link(self_route, method=POST, requests_kwargs=requests_kwargs)
        self_route.links["update"] = Link(self_route, method=PATCH, requests_kwargs=requests_kwargs)
        self_route.links["delete"] = Link(self_route, method=DELETE, requests_kwargs=requests_kwargs)

        for link_desc in schema[LINKS]:
            if link_desc[REL] == SELF:
                continue
            is_instance = link_desc[HREF].startswith(self_route.path)

            rel = link_desc[REL].split(":")
            route_name = rel[0]

            if not route_name in routes.keys():

                route = Route(link_desc[HREF], route_name)
                routes[route_name] = route
                if is_instance:
                    resource._instance_routes.append(route)
                else:
                    class_routes.append(route)
            else:
                route = routes[route_name]

            link = Link(route,
                        method=link_desc[METHOD],
                        schema=link_desc.get(SCHEMA, {}),
                        target_schema=link_desc.get(TARGET_SCHEMA, {}),
                        requests_kwargs=requests_kwargs)
            if len(rel) == 1:
                route.default = link
            else:
                route.links[rel[1]] = link

        for route in class_routes:
            setattr(resource, route.name, RouteProxy(route, resource))

        return resource

    def __str__(self):
        return str(self._instance)
