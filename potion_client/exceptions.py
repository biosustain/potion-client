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


class OneOfException(Exception):
    def __init__(self, errors):
        self._errors = errors

    @property
    def message(self):
        return "Caused by one of %s" % ([str(e) for e in self._errors])


class HTTPException(Exception):
    pass


class NotFoundException(HTTPException):
    pass


class BadRequestException(HTTPException):
    pass


class InternalServerErrorException(HTTPException):
    pass


class ConflictException(HTTPException):
    pass


HTTP_EXCEPTIONS = {
    400: BadRequestException,
    404: NotFoundException,
    409: ConflictException,
    500: InternalServerErrorException
}

HTTP_MESSAGES = {
    400: "Bad Request (400)",
    404: "Not Found (404)",
    409: "Conflict",
    500: "Internal Server Error (500)"
}
