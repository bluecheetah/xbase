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

from bag.layout.routing.grid import RoutingGrid

from xbase.layout.mos.placement.data import MOSArrayPlaceInfo, MOSBasePlaceInfo


def test_arr_info_save_load(routing_grid: RoutingGrid, arr_info_specs: Dict[str, Any],
                            root_test_dir: Path) -> None:
    test_id: str = arr_info_specs['test_id']
    test_dir = root_test_dir.joinpath('arr_info', test_id)

    info = MOSArrayPlaceInfo.make_array_info(routing_grid, arr_info_specs)

    info.save(test_dir)
    new_info = MOSArrayPlaceInfo.load(routing_grid, test_dir)
    assert info == new_info
    assert hash(info) == hash(new_info)


def test_place_info_save_load(routing_grid: RoutingGrid, place_info_specs: Dict[str, Any],
                              root_test_dir: Path) -> None:
    test_id: str = place_info_specs['test_id']
    test_dir = root_test_dir.joinpath('place_info', test_id)

    info = MOSBasePlaceInfo.make_place_info(routing_grid, place_info_specs, name=test_id)

    info.save(test_dir)
    new_info = MOSBasePlaceInfo.load(routing_grid, test_dir, test_id)
    assert info == new_info
    assert hash(info) == hash(new_info)
