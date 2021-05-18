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

from typing import Dict, Any, Optional, Mapping, Tuple

from bag.util.immutable import Param, ImmutableSortedDict
from bag.layout.routing.grid import RoutingGrid
from bag.layout.template import TemplateBase, TemplateDB

from ..data import draw_layout_in_template
from .data import ArrayLayInfo, WireArrayInfo
from .tech import ArrayTech


class ArrayUnit(TemplateBase):
    """Unit block of an device array.

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            desc='device description string.',
            blk_info='The unit block layout information object.',
        )

    def get_layout_basename(self) -> str:
        return f'{self.params["desc"]}Unit'

    def draw_layout(self) -> None:
        blk_info: ArrayLayInfo = self.params['blk_info']

        draw_layout_in_template(self, blk_info.lay_info)
        grid = self.grid
        if isinstance(list(blk_info.ports_info.values())[0], WireArrayInfo):
            for key, val in blk_info.ports_info.items():
                cur_warr = val.to_warr(grid)
                self.add_pin(key, cur_warr)
                self.prim_top_layer = cur_warr.layer_id
        else:
            for port_name, port_info in blk_info.ports_info.items():
                for lay_name, bbox_list in port_info:
                    for bbox in bbox_list:
                        self.add_pin_primitive(port_name, lay_name, bbox)
            self.prim_top_layer = grid.bot_layer


class ArrayEnd(TemplateBase):
    """End row block of device array.

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self.prim_top_layer = self.grid.bot_layer
        self._edge_info: Optional[ImmutableSortedDict[str, Any]] = None

    @property
    def edge_info(self) -> ImmutableSortedDict[str, Any]:
        return self._edge_info

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            tech_kwargs='parameters needed to create technology object.',
            w='block width.',
            h='block height.',
            info='boundary information object.',
            options='additional layout options.',
        )

    def get_layout_basename(self) -> str:
        grid: RoutingGrid = self.params['grid']
        tech_kwargs: Mapping[str, Any] = self.params['tech_kwargs']
        tech_cls: ArrayTech = grid.tech_info.get_device_tech(**tech_kwargs)
        return f'{tech_cls.desc}End'

    def draw_layout(self) -> None:
        tech_kwargs: Mapping[str, Any] = self.params['tech_kwargs']
        w: int = self.params['w']
        h: int = self.params['h']
        info: ImmutableSortedDict[str, Any] = self.params['info']
        options: Mapping[str, Any] = self.params['options']

        tech_cls: ArrayTech = self.grid.tech_info.get_device_tech(**tech_kwargs)

        end_info = tech_cls.get_end_info(w, h, info, **options)
        draw_layout_in_template(self, end_info.lay_info)
        self._edge_info = end_info.edge_info


class ArrayEdge(TemplateBase):
    """Edge column block of device array.

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self.prim_top_layer = self.grid.bot_layer

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            tech_kwargs='parameters needed to create technology object.',
            w='block width.',
            h='block height.',
            info='boundary information object.',
            options='additional layout options.',
        )

    def get_layout_basename(self) -> str:
        grid: RoutingGrid = self.params['grid']
        tech_kwargs: Mapping[str, Any] = self.params['tech_kwargs']
        tech_cls: ArrayTech = grid.tech_info.get_device_tech(**tech_kwargs)
        return f'{tech_cls.desc}Edge'

    def draw_layout(self) -> None:
        tech_kwargs: Mapping[str, Any] = self.params['tech_kwargs']
        w: int = self.params['w']
        h: int = self.params['h']
        info: ImmutableSortedDict[str, Any] = self.params['info']
        options: Mapping[str, Any] = self.params['options']

        tech_cls: ArrayTech = self.grid.tech_info.get_device_tech(**tech_kwargs)

        lay_info = tech_cls.get_edge_info(w, h, info, **options)
        draw_layout_in_template(self, lay_info)


class ArrayCorner(TemplateBase):
    """Corner block of device array.

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self.prim_top_layer = self.grid.bot_layer
        self._corner: Optional[Tuple[int, int]] = None
        self._edgel = self._edgeb = ImmutableSortedDict()

    @property
    def corner(self) -> Tuple[int, int]:
        return self._corner

    @property
    def left_edge(self) -> Param:
        return self._edgel

    @property
    def bottom_edge(self) -> Param:
        return self._edgeb

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            tech_kwargs='parameters needed to create technology object.',
            w='block width.',
            h='block height.',
            info='boundary information object.',
            options='additional layout options.',
        )

    def get_layout_basename(self) -> str:
        grid: RoutingGrid = self.params['grid']
        tech_kwargs: Mapping[str, Any] = self.params['tech_kwargs']
        tech_cls: ArrayTech = grid.tech_info.get_device_tech(**tech_kwargs)
        return f'{tech_cls.desc}Corner'

    def draw_layout(self) -> None:
        tech_kwargs: Mapping[str, Any] = self.params['tech_kwargs']
        w: int = self.params['w']
        h: int = self.params['h']
        info: ImmutableSortedDict[str, Any] = self.params['info']
        options: Mapping[str, Any] = self.params['options']

        tech_cls: ArrayTech = self.grid.tech_info.get_device_tech(**tech_kwargs)

        corner_info = tech_cls.get_corner_info(w, h, info, **options)
        draw_layout_in_template(self, corner_info.lay_info)
        self._corner = corner_info.corner
        self._edgel = corner_info.edgel
        self._edgeb = corner_info.edgeb
