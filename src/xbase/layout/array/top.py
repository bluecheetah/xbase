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

from typing import Any, Dict, Type, cast, Mapping, Optional

from pybag.core import BBox, Transform
from pybag.enum import Orientation

from bag.util.immutable import Param
from bag.util.importlib import import_class
from bag.layout.data import TemplateEdgeInfo
from bag.layout.template import TemplateDB, TemplateBase
from bag.layout.core import PyLayInstance
from bag.design.module import Module

from .tech import ArrayTech
from .primitives import ArrayEnd, ArrayEdge, ArrayCorner
from .base import ArrayPlaceInfo, ArrayBase


class ArrayBaseWrapper(TemplateBase):

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self._core: Optional[ArrayBase] = None

    @property
    def core(self) -> ArrayBase:
        return self._core

    @property
    def core_xform(self) -> Transform:
        return self._xform

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            cls_name='wrapped class name.',
            params='parameters for the wrapped class.',
            half_blk_x='Defaults to True.  True to allow half-block width.',
            half_blk_y='Defaults to True.  True to allow half-block height.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(half_blk_x=True, half_blk_y=True)

    def get_schematic_class_inst(self) -> Optional[Type[Module]]:
        return self._core.get_schematic_class_inst()

    def get_layout_basename(self) -> str:
        cls_name: str = self.params.get('cls_name', '')
        cls_name = cls_name.split('.')[-1]
        if cls_name.endswith('Core'):
            return cls_name[:-4]
        return cls_name + 'Wrap'

    def draw_layout(self):
        cls_name: str = self.params['cls_name']
        params: Mapping[str, Any] = self.params['params']

        gen_cls = cast(Type[ArrayBase], import_class(cls_name))
        master = self.new_template(gen_cls, params=params)

        inst = self.draw_boundaries(master, master.top_layer, half_blk_x=self.params['half_blk_x'],
                                    half_blk_y=self.params['half_blk_y'])
        # pass out schematic parameters
        self.sch_params = master.sch_params

        # re-export pins
        for name in inst.port_names_iter():
            self.reexport(inst.get_port(name))

    def draw_boundaries(self, master: ArrayBase, top_layer: int, *,
                        half_blk_x: bool = True, half_blk_y: bool = True) -> PyLayInstance:
        self._core = master
        tech_cls: ArrayTech = master.tech_cls
        core_box: BBox = master.bound_box
        info: ArrayPlaceInfo = master.place_info

        grid = self.grid

        blk_w, blk_h = grid.get_block_size(top_layer, half_blk_x=half_blk_x, half_blk_y=half_blk_y)

        arr_w = core_box.w
        arr_h = core_box.h
        binfo = info.blk_info
        edge_info = binfo.edge_info
        end_info = binfo.end_info
        corner_w = tech_cls.get_edge_width(edge_info, arr_w, blk_w)
        corner_h = tech_cls.get_end_height(end_info, arr_h, blk_h)
        nx = master.nx
        ny = master.ny
        spx = info.width
        spy = info.height
        bnd_params = dict(tech_kwargs=tech_cls.tech_kwargs, w=spx, h=corner_h,
                          info=end_info, options=info.blk_options)
        b_master = self.new_template(ArrayEnd, params=bnd_params, grid=master.grid)
        bnd_params['w'] = corner_w
        bnd_params['info'] = b_master.edge_info
        c_master = self.new_template(ArrayCorner, params=bnd_params)
        bnd_params['h'] = spy
        bnd_params['info'] = edge_info
        l_master = self.new_template(ArrayEdge, params=bnd_params)

        tot_w = arr_w + 2 * corner_w
        tot_h = arr_h + 2 * corner_h
        bbox = BBox(0, 0, tot_w, tot_h)
        self.set_size_from_bound_box(top_layer, bbox)

        self._xform = Transform(corner_w, corner_h)

        self.add_instance(c_master, inst_name='CLL')
        self.add_instance(c_master, inst_name='CLR', xform=Transform(tot_w, 0, Orientation.MY))
        self.add_instance(c_master, inst_name='CUL', xform=Transform(0, tot_h, Orientation.MX))
        self.add_instance(c_master, inst_name='CUR',
                          xform=Transform(tot_w, tot_h, Orientation.R180))

        self.add_instance(b_master, inst_name='EB', xform=Transform(corner_w, 0), nx=nx, spx=spx)
        self.add_instance(b_master, inst_name='ET',
                          xform=Transform(corner_w, tot_h, Orientation.MX), nx=nx, spx=spx)
        self.add_instance(l_master, inst_name='EL', xform=Transform(0, corner_h), ny=ny, spy=spy)
        self.add_instance(l_master, inst_name='ET',
                          xform=Transform(tot_w, corner_h, Orientation.MY), ny=ny, spy=spy)

        inst = self.add_instance(master, inst_name='RES', xform=self._xform)

        # set edge parameters
        self.edge_info = TemplateEdgeInfo(c_master.left_edge, c_master.bottom_edge,
                                          c_master.left_edge, c_master.bottom_edge)

        return inst
