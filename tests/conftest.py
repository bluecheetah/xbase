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

from pathlib import Path

import pytest

from bag.env import create_tech_info, create_routing_grid
from bag.layout.tech import TechInfo
from bag.layout.routing.grid import RoutingGrid


@pytest.fixture(scope='session')
def tech_info() -> TechInfo:
    return create_tech_info()


@pytest.fixture(scope='session')
def routing_grid(tech_info: TechInfo) -> RoutingGrid:
    return create_routing_grid(tech_info=tech_info)


@pytest.fixture(scope='session')
def root_test_dir() -> Path:
    ans = Path('pytest_output', 'framework', 'xbase')
    ans.mkdir(parents=True, exist_ok=True)
    return ans
