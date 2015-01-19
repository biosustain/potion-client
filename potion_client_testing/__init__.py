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
from flask import Flask
from flask_testing import TestCase
from flask_potion import fields, Api
from flask_potion.resource import ModelResource
from flask_sqlalchemy import SQLAlchemy
import requests
from sqlalchemy.orm import backref
from httmock import urlmatch


class MockResponseTool(object):

    encoding = "utf-8"

    @urlmatch(netloc='.*', method="GET", path=".*")
    def get_mock(self, url, request):
        return self.reply(self.client.get(url.path), request)

    @urlmatch(netloc='.*', method="POST", path=".*")
    def post_mock(self, url, request):
        body = json.loads(request.body)
        print(url.path, "[%s %s]" % (type(body), body))
        return self.reply(self.client.post(url.path, data=body), request)

    @urlmatch(netloc='.*', method="PATCH", path=".*")
    def patch_mock(self, url, request):
        body = json.loads(request.body)
        return self.reply(self.client.patch(url.path, data=body), request)

    @urlmatch(netloc='.*', method="DELETE", path=".*")
    def delete_mock(self, url, request):
        return self.reply(self.client.delete(url.path), request)

    def reply(self, response, request):
        content = "".join([b.decode(self.encoding) for b in response.response])
        res = requests.Response()
        res._content = content.encode(self.encoding)
        res._content_consumed = content
        res.status_code = response.status_code
        res.encoding = self.encoding
        res.headers = request.headers
        return res


class MockAPITestCase(MockResponseTool, TestCase):

    def create_app(self):
        app = Flask(__name__)
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.secret_key = 'XXX'
        app.debug = True
        return app

    def setUp(self):
        super(MockAPITestCase, self).setUp()
        self.api = Api(self.app)
        self.sa = sa = SQLAlchemy(self.app)

        class Foo(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            attr1 = sa.Column(sa.String, nullable=False)
            attr2 = sa.Column(sa.String)
            baz = sa.relationship("Baz", uselist=False, backref="foo")

        class Bar(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            attr1 = sa.Column(sa.Integer, nullable=False)
            foo_id = sa.Column(sa.Integer, sa.ForeignKey(Foo.id), nullable=False)
            foo = sa.relationship(Foo, backref=backref('bars', lazy='dynamic'))

        class Baz(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            foo_id = sa.Column(sa.Integer, sa.ForeignKey(Foo.id), nullable=False)

        sa.create_all()

        class ResourceFoo(ModelResource):
            class Schema:
                bars = fields.ToMany("bar")
                baz = fields.ToOne("baz")
            class Meta:
                model = Foo

        class ResourceBar(ModelResource):
            class Schema:
                foo = fields.ToOne(ResourceFoo)

            class Meta:
                model = Bar

        class ResourceBaz(ModelResource):
            class Schema:
                foo = fields.ToOne(ResourceFoo)

            class Meta:
                model = Baz

        self.api.add_resource(ResourceFoo)
        self.api.add_resource(ResourceBar)
        self.api.add_resource(ResourceBaz)

    def tearDown(self):
        self.sa.drop_all()