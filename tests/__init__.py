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
from flask import Flask
from flask_testing import TestCase
from flask_potion import fields, Api
from flask_potion.resource import ModelResource
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref
from tests import ApiClient
from httmock import urlmatch, response


class MockResponseTool():
    def __init__(self, client):
        self.client = client

    @urlmatch(netloc='*', method="GET")
    def get_mock(self, url, request):
        self.reply(self.client.get(url))

    @urlmatch(netloc='*', method="POST")
    def post_mock(self, url, request):
        self.reply(self.client.post(url))

    @urlmatch(netloc='*', method="PATCH")
    def patch_mock(self, url, request):
        self.reply(self.client.patch(url))

    @urlmatch(netloc='*', method="DELETE")
    def delete_mock(self, url, request):
        self.reply(self.client.delete(url))

    def reply(self, res):
        return response(res.status_code, res.content, res.headers)


class MockAPITestCase(TestCase, MockResponseTool):

    def create_app(self):
        app = Flask(__name__)
        app.secret_key = 'XXX'
        app.test_client_class = ApiClient
        app.debug = True
        return app

    def setUp(self):
        super(MockAPITestCase, self).setUp()
        app = self.create_app()
        self.api = Api(app)
        self.sa = sa = SQLAlchemy(app)

        class Foo(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            attr1 = sa.Column(sa.String, nullable=False)
            attr2 = sa.Column(sa.String)

        class Bar(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            attr1 = sa.Column(sa.Integer, nullable=False)
            foo_id = sa.Column(sa.Integer, sa.ForeignKey(Foo.id), nullable=False)
            foo = sa.relationship(Foo, backref=backref('bars', lazy='dynamic'))

        sa.create_all()

        class ResourceFoo(ModelResource):
            class Schema:
                bar = fields.ToMany("bar")

            class Meta:
                model = Foo

        class ResourceBar(ModelResource):
            class Schema:
                foo = fields.ToOne(ResourceFoo)

            class Meta:
                model = Bar

        self.api.add_resource(ResourceFoo)
        self.api.add_resource(ResourceBar)

    def tearDown(self):
        self.sa.drop_all()