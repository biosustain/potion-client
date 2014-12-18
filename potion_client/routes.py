import json
import string
from jsonschema import validate
import requests
from potion_client import utils
from .constants import *
import logging
from potion_client.exceptions import NotFoundException  

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

    def __getitem__(self, pos):
        if isinstance(pos, tuple):
            page = pos[0]
            limit = pos[1]

        return self(per_page=limit, page=page)


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

    def __getitem__(self, pos):
        if isinstance(pos, tuple):
            page = pos[0]
            limit = pos[1]

        return self(per_page=limit, page=page)


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


class LazyCollectionIterartor(object):

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


class LazyCollection(object):

    @classmethod
    def from_url(cls, path, client, **kwargs):
        url = client.base_url + path
        response = requests.get(url, **kwargs)
        return LazyCollection(response.json(), response.links, client, **kwargs)

    def __init__(self, items, links, client, **request_kwargs):
        self.items = items
        self.links = links
        self.request_kwargs = request_kwargs
        self.client = client
        if not self.links is None:
            self._create_links()

    def __iter__(self):
        return LazyCollectionIterartor(self)

    def _create_links(self):
        for link_name, link_desc in self.links.items():
            setattr(self, link_name, lambda: self.from_url(link_desc[URL], self.client, **self.request_kwargs))

    def __getitem__(self, index):
        item = self.client.resolve_element(self.items[index])
        return item


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
        print(url)
        res = requests.request(self.method, url=url, json=json, params=params, **self.request_kwargs)
        print(res)
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
            return LazyCollection(valid_res, res.links, obj.client, **self.request_kwargs)

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
                return LazyCollection(item, {}, None)
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
