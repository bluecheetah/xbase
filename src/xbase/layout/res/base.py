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

import abc

from typing import Any, Optional, Mapping, List, cast, Union

from bag.util.immutable import Param
from bag.layout.template import TemplateDB
from bag.layout.tech import TechInfo
from bag.layout.routing.base import WDictType, SpDictType
from bag.layout.routing.grid import RoutingGrid, TrackSpec

from ..mos.data import MOSType
from ..enum import ExtendMode
from ..array.base import ArrayPlaceInfo, ArrayBase
from .tech import ResTech


class ResBasePlaceInfo(ArrayPlaceInfo):
    def __init__(self, parent_grid: RoutingGrid, wire_specs: Mapping[int, Any],
                 tr_widths: WDictType, tr_spaces: SpDictType, top_layer: int, nx: int, ny: int, *,
                 conn_layer: Optional[int] = None, res_type: str = 'standard', mos_type: str = '',
                 threshold: str = '', tr_specs: Optional[List[TrackSpec]] = None,
                 half_space: bool = True, ext_mode: ExtendMode = ExtendMode.AREA,
                 **kwargs: Any) -> None:
        metal = (res_type == 'metal')
        tech_cls: ResTech = parent_grid.tech_info.get_device_tech('res', metal=metal)
        self._res_config = parent_grid.tech_info.config['res_metal' if metal else 'res']

        if not mos_type:
            mos_type = tech_cls.mos_type_default
        if not threshold:
            threshold = tech_cls.threshold_default

        ArrayPlaceInfo.__init__(self, parent_grid, wire_specs, tr_widths, tr_spaces, top_layer,
                                nx, ny, tech_cls, conn_layer=conn_layer, tr_specs=tr_specs,
                                half_space=half_space, ext_mode=ext_mode, res_type=res_type,
                                mos_type=mos_type, threshold=threshold, **kwargs)

        self._res_type = res_type
        self._mos_type = MOSType[mos_type]
        self._threshold = threshold

        self._w_res = tech_cls.get_width(**kwargs)
        self._l_res = tech_cls.get_length(**kwargs)

    def __eq__(self, other: Any) -> bool:
        # noinspection PyProtectedMember
        return (ArrayPlaceInfo.__eq__(self, other) and
                self._res_type == other._res_type and
                self._mos_type == other._mos_type and
                self._threshold == other._threshold)

    @classmethod
    def get_tech_cls(cls, tech_info: TechInfo, **kwargs: Any) -> ResTech:
        res_type = kwargs.get('res_type', 'standard')

        metal = (res_type == 'metal')
        return tech_info.get_device_tech('res', metal=metal)

    @property
    def res_type(self) -> str:
        return self._res_type

    @property
    def mos_type(self) -> MOSType:
        return self._mos_type

    @property
    def threshold(self) -> str:
        return self._threshold

    @property
    def res_config(self) -> Mapping[str, Any]:
        return self._res_config

    @property
    def has_substrate_port(self) -> bool:
        return self._res_config['has_substrate_port']

    @property
    def w_res(self) -> int:
        return self._w_res

    @property
    def l_res(self) -> int:
        return self._l_res


class ResArrayBase(ArrayBase, abc.ABC):
    """Array of resistors"""

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        ArrayBase.__init__(self, temp_db, params, **kwargs)

    @property
    def has_substrate_port(self) -> bool:
        return cast(ResTech, self.tech_cls).has_substrate_port

    @property
    def sub_type(self) -> MOSType:
        return cast(ResBasePlaceInfo, self.place_info).mos_type

    def draw_base(self, obj: Union[ResBasePlaceInfo, Mapping[str, Any]]) -> ResBasePlaceInfo:
        if isinstance(obj, ResBasePlaceInfo):
            pinfo = obj
        else:
            pinfo = ResBasePlaceInfo(self.grid, **obj)

        super().draw_base(pinfo)
        return pinfo
