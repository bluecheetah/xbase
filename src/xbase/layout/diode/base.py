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

from __future__ import annotations

from typing import Any, Optional, Mapping, List

from bag.layout.tech import TechInfo
from bag.layout.routing.base import WDictType, SpDictType
from bag.layout.routing.grid import RoutingGrid, TrackSpec

from ..enum import ExtendMode
from ..array.base import ArrayPlaceInfo
from .tech import DiodeTech


class DiodeBasePlaceInfo(ArrayPlaceInfo):
    def __init__(self, parent_grid: RoutingGrid, wire_specs: Mapping[int, Any],
                 tr_widths: WDictType, tr_spaces: SpDictType, top_layer: int, nx: int, ny: int, *,
                 conn_layer: Optional[int] = None, dio_type: str = '',
                 tr_specs: Optional[List[TrackSpec]] = None,
                 half_space: bool = True, ext_mode: ExtendMode = ExtendMode.AREA,
                 **kwargs: Any) -> None:
        tech_cls: DiodeTech = parent_grid.tech_info.get_device_tech('diode', dio_type=dio_type)

        ArrayPlaceInfo.__init__(self, parent_grid, wire_specs, tr_widths, tr_spaces, top_layer,
                                nx, ny, tech_cls, conn_layer=conn_layer, tr_specs=tr_specs,
                                half_space=half_space, ext_mode=ext_mode, dio_type=dio_type,
                                **kwargs)

    @classmethod
    def get_tech_cls(cls, tech_info: TechInfo, **kwargs: Any) -> DiodeTech:
        dio_type = kwargs.get('dio_type', '')
        return tech_info.get_device_tech('diode', dio_type=dio_type)
