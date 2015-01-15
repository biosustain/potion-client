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
import string


def camelize(string):
    assert isinstance(string, str)
    return "".join([part.capitalize() for part in string.replace("-", "_").split("_")])


def params_to_dict(params_string):
    dict = {}
    for part in params_string.split("&"):
        key, value = part.split("=")
        if not key in dict:
            dict[key] = []
        dict[key].append(value)

    for key in dict.keys():
        if len(dict[key]) == 1:
            dict[key] = dict[key][0]

    return dict


def ditc_to_params(dict):
    s = []
    for key, value in dict.items():
        s.append("%s=%s" % (key, value))

    return "&".join(s)


def extract_keys(a_string, formatter=string.Formatter()):
    format_iterator = formatter.parse(a_string)
    return [t[1] for t in format_iterator if not t[1] is None]
