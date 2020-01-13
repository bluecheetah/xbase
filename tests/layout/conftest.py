# SPDX-License-Identifier: Apache-2.0
# Copyright 2019 Blue Cheetah Analog Design Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Dict, Any

from pathlib import Path

import pytest

from bag.io.file import read_yaml


@pytest.fixture(scope="module")
def data_dir(request) -> Path:
    return Path(str(request.fspath.join('..', 'data')))


def pytest_generate_tests(metafunc):
    fixtures = metafunc.fixturenames

    if 'arr_info_specs' in fixtures:
        basename = 'arr_info'
    elif 'place_info_specs' in fixtures:
        basename = 'place_info'
    else:
        return

    data_dir = Path(metafunc.module.__file__).joinpath('..', 'data').resolve()
    spec_list = read_yaml(data_dir / f'{basename}.yaml')
    ids = [f'{basename}_{val}' for val in range(len(spec_list))]
    for specs, test_id in zip(spec_list, ids):
        specs['test_id'] = test_id
    metafunc.parametrize(f'{basename}_specs', spec_list, indirect=True, ids=ids)


@pytest.fixture(scope='session')
def arr_info_specs(request) -> Dict[str, Any]:
    return request.param


@pytest.fixture(scope='session')
def place_info_specs(request) -> Dict[str, Any]:
    return request.param
