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


class Route(object):
    def __init__(self, path, klass):
        self.path = path
        self.instance = None
        self.resource_class = klass

    def __get__(self, instance, owner):
        if instance is None:
            self.instance = owner
            return self._get()
        else:
            self.instance = instance
            return self

    def __call__(self):
        return self._get()

    def generate_url(self):
        base_url = self.instance.client.base_url
        url = "{base}{path}".format(base=base_url, path=self.path)
        logger.debug("Generated url: %s" % url)
        return url.format(**self.extract_keys(self.instance, _string_formatter))

    def extract_keys(self, resource, formatter=_string_formatter):
        format_iterator = formatter.parse(self.path)
        return dict([(t[1], getattr(resource, t[1])) for t in format_iterator if not t[1] is None])


class LazyCollection(object):
    def __init__(self, page, limit, total, resolver):
        self.page = page
        self.total = total
        self.limit = limit
        self.pointer = 0
        self.resolver = resolver

    def __getitem__(self, index):
        if index > self.total:
            raise IndexError("Index out of bounds %i (size %i)" % (index, self.total))
        else:
            page = self.total/index
            real_index = index - (page*index)
            if page != self.page:
                self.items = self.resolver(page, self.limit)
                self.page = page
            return self.items[real_index]


class Link(object):
    def __init__(self, method="GET", schema=None, target_schema=None, requests_kwargs=None):
        self.method = method
        self.schema = schema
        self.target_schema = target_schema
        self.requests_kwargs = requests_kwargs

    def __call__(self, **kwargs):
        kwargs.update(self.requests_kwargs)
        url = self.route.generate_url()
        response = requests.request(self.method, url=url, **kwargs)
        if response.status_code == 404:
            raise NotFoundException(url)

        obj = response.json()
        resource_class = self.route.resource_class
        expected_type = object
        if TYPE in self.target_schema:
            expected_type = TYPES[self.target_schema[TYPE]]
        elif REF in self.schema:
            # fragment_class, fragment = self.resolve_fragment(self.route.client)
            # expected_schema = fragment._resolve_fragment(fragment)
            expected_type = list

        if ITEMS in self.target_schema:
            resource_class = self.route.instance.client._url_identifiers[self.target_schema[ITEMS]]


        assert isinstance(obj, expected_type)
        if expected_type == list:
            return LazyCollection()
        else:
            return obj

    def __getitem__(self, pos):
        if isinstance(pos, tuple):
            page = pos[0]
            limit = pos[1]
        else:
            page = pos
            limit = self.schema.get('pagination', DEFAULT_PER_PAGE)

        return self(params={'per_page': limit, 'page': page})


class Resource:
    client = None
    _schema = None

    @classmethod
    def get(cls, id):
        instance = cls.__new__(cls)
        instance.id = id
        instance._ensure_instance()
        return instance

    @classmethod
    def _from_json(cls, json):
        print(json)
        id = json[URI].split("/")[-1]
        instance = cls.__new__(cls)
        instance.id = id
        instance._instance = json
        return instance

    def __init__(self, id=None, instance=None):
        self.id = id
        self._instance = instance
        if id is None:  # make a new object
            self._instance = {}

    def __getattr__(self, item):
        if item in self._schema[PROPERTIES]:
            self._ensure_instance()
            return self._instance.get(item, None)
        else:
            getattr(super(Resource, self), item, self)

    def __setattr__(self, key, value):
        if key in self._schema[PROPERTIES]:
            self._ensure_instance()
            self._instance[key] = value
        else:
            super(Resource, self).__setattr__(key, value)

    def _ensure_instance(self):
        if self._instance is None:
            self._instance = self.self()

    def save(self):
        validate(self._instance, self._schema)
        if self.id is None:
            self.self.create()
        else:
            self.self.update()

    def delete(self):
        if self.id is None:
            #raise some kind of error
            raise RuntimeError()
        else:
            self.self.destroy()

    def __dir__(self):
        return super(Resource, self).__dir__() + list(self._schema[PROPERTIES].keys())

    @classmethod
    def resolve(self, path):
        root, target = path.split("#")
        if len(root) == 0:
            schema = self._schema
        else:
            klass = self.client._url_identifiers[root+"#"]
            schema = klass._schema

        base, section, fragment = target.split("/")

        return self._schema_resolver.resolve_fragment(schema[section], fragment)

    @classmethod
    def factory(cls, docstring, name, schema, requests_kwargs):
        class_name = utils.camelize(name)
        resource = type(class_name, (cls, ), {})
        resource.__doc__ = docstring
        resource._schema = schema
        routes = {}
        for link_desc in schema[LINKS]:
            link = Link(method=link_desc[METHOD], schema=link_desc.get(SCHEMA, {}),
                        target_schema=link_desc.get(TARGET_SCHEMA, {},),
                        requests_kwargs=requests_kwargs)

            rel = link_desc[REL].split(":")
            route_name = rel[0]
            if not route_name in routes:
                routes[route_name] = {HREF: link_desc[HREF], LINKS: {}}

            if len(rel) == 1:
                routes[route_name][LINKS]["_get"] = link
            else:
                routes[route_name][LINKS][rel[1]] = link

        for route_name, route_desc in routes.items():
            route = Route(route_desc[HREF], resource)
            setattr(resource, route_name, route)
            for link_name, link in route_desc[LINKS].items():
                setattr(route, link_name, link)
                link.route = route

        return resource


class Pagination(list):
    pass