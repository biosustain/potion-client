import json
import requests
from potion_client import utils
from .constants import *


class Route(object):

    def __init__(self, route):
        pass

    def __call__(self, *args, **kwargs):
        pass


class Link(object):
    def __init__(self, route, method=None, schema=None):
        self.route = route
        self.method = method
        self.schema = schema

    def __call__(self, **kwargs):
        pass


class Resource(object):
    client = None
    schema = None
    _properties = None
    _instance = None
    _id = None

    def __init__(self, id=None, **kwargs):

        if id is None:  # make a new object
            self._id = None
            self._instance = {}
        else:
            self._id = None

    def __getattr__(self, item):
        if item in self._properties:
            self._ensure_instance()
            return self._instance[item]
        raise KeyError()

    def __setattr__(self, key, value):
        if key in self._properties:
            self._ensure_instance()
            self._instance[key] = value
        else:
            super(Resource, self).__setattr__(key, value)

    def _ensure_instance(self):
        if self._id is None:
            return
        if self._instance is not None:
            return
        self._instance = self.client.read(self)

    @classmethod
    def factory(cls, schema_uri, docstring, name, **requests_kwargs):
        schema_request = requests.get(schema_uri, **requests_kwargs)
        #handle not found
        schema = json.loads(schema_request.text)
        members = {}
        links = []
        for link_desc in schema[LINKS]:
            route = Route(link_desc[HREF])
            method = link_desc.get(METHOD, GET)
            link_schema = link_desc.get(SCHEMA, None)
            link = Link(route, method=method, schema=link_schema)
            rel = link_desc[REL]
            links.append(rel)
            members[rel] = link
        class_name = utils.camelize(name)
        bases = (cls,)
        # TODO add members for all the links (assume for now they do not interfere with properties)

        resource = type(class_name, bases, members)
        resource.__doc__ = docstring

        return resource


class Pagination(list):
    pass