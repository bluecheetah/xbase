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

"""This module defines various MOM cap related templates."""

from typing import Any, Dict, Optional, Mapping, List, Tuple, Type

from pybag.core import BBox, BBoxArray

from bag.util.immutable import Param
from bag.design.module import Module
from bag.layout.routing.grid import FillConfigType
from bag.layout.template import TemplateDB, TemplateBase

from xbase.layout.fill.base import DeviceFill
from xbase.schematic.momcap_core import xbase__momcap_core


class MOMCapCore(TemplateBase):
    """MOMCap core
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return xbase__momcap_core

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            bot_layer='MOM cap bottom layer.',
            top_layer='MOM cap top layer.',
            width='MOM cap width, in resolution units.',
            height='MOM cap height, in resolution units.',
            margin='margin between cap and boundary, in resolution units.',
            port_tr_w='MOM cap port track width, in number of tracks.',
            options='MOM cap layout options.',
            fill_config='Fill configuration dictionary.  If not None, quantize to fill grid.',
            fill_dummy='True to draw dummy fill.',
            fill_pitch='dummy fill pitch.',
            mos_type='dummy fill transistor type.',
            threshold='dummy fill threshold.',
            half_blk_x='True to allow half horizontal blocks.',
            half_blk_y='True to allow half vertical blocks.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        ans = DeviceFill.get_default_param_values()
        ans.update(
            margin=0,
            port_tr_w=1,
            options=None,
            fill_config=None,
            fill_dummy=False,
            fill_pitch=2,
            half_blk_x=True,
            half_blk_y=True,
        )
        return ans

    def draw_layout(self) -> None:
        bot_layer: int = self.params['bot_layer']
        top_layer: int = self.params['top_layer']
        width: int = self.params['width']
        height: int = self.params['height']
        margin: int = self.params['margin']
        port_tr_w: int = self.params['port_tr_w']
        options: Optional[Mapping[str, Any]] = self.params['options']
        fill_config: Optional[FillConfigType] = self.params['fill_config']
        fill_dummy: bool = self.params['fill_dummy']
        mos_type: str = self.params['mos_type']
        threshold: str = self.params['threshold']
        half_blk_x: bool = self.params['half_blk_x']
        half_blk_y: bool = self.params['half_blk_y']

        grid = self.grid

        w_tot = width + 2 * margin
        h_tot = height + 2 * margin
        if fill_config is None:
            w_blk, h_blk = grid.get_block_size(top_layer, half_blk_x=half_blk_x,
                                               half_blk_y=half_blk_y)
        else:
            w_blk, h_blk = grid.get_fill_size(top_layer, fill_config, half_blk_x=half_blk_x,
                                              half_blk_y=half_blk_y)
        w_tot = -(-w_tot // w_blk) * w_blk
        h_tot = -(-h_tot // h_blk) * h_blk

        # set size
        self.array_box = bnd_box = BBox(0, 0, w_tot, h_tot)
        self.set_size_from_bound_box(top_layer, bnd_box)

        # setup capacitor options
        # get .  Make sure we can via up to top_layer + 1
        top_port_tr_w = port_tr_w
        port_w_dict = {top_layer: top_port_tr_w}
        for lay in range(top_layer - 1, bot_layer - 1, -1):
            top_port_tr_w = port_w_dict[lay] = grid.get_min_track_width(lay, top_ntr=top_port_tr_w)

        # draw cap
        cap_xl = (bnd_box.w - width) // 2
        cap_yb = (bnd_box.h - height) // 2
        cap_box = BBox(cap_xl, cap_yb, cap_xl + width, cap_yb + height)
        num_layer = top_layer - bot_layer + 1
        options = options or {}
        cw_list: List[Tuple[Tuple[str, str], Tuple[str, str], BBoxArray, BBoxArray]] = []
        cap_ports = self.add_mom_cap(cap_box, bot_layer, num_layer, port_widths=port_w_dict,
                                     cap_wires_list=cw_list, **options)

        # connect input/output, draw metal resistors
        show_pins = self.show_pins
        for lay, (nport, pport) in cap_ports.items():
            self.add_pin('plus', pport, show=show_pins)
            self.add_pin('minus', nport, show=show_pins)

        _, _, barr_n, barr_p = cw_list[-1]
        box_p = barr_p.get_bbox(0)
        box_n = barr_n.get_bbox(0)
        top_dir = grid.get_direction(top_layer)
        res_w = box_p.get_dim(top_dir.perpendicular())
        coord_c = box_p.get_center(top_dir)

        res_w2 = res_w // 2
        res_w4 = res_w2 // 2
        wl_p = coord_c - res_w2
        wu_p = coord_c + res_w2
        wl_n = coord_c - res_w4
        wu_n = coord_c + res_w4
        box_p.set_interval(top_dir, wl_p, wu_p)
        box_n.set_interval(top_dir, wl_n, wu_n)
        self.add_res_metal(top_layer, box_p)
        self.add_res_metal(top_layer, box_n)

        if fill_dummy:
            dum_params = dict(
                width=w_tot,
                height=h_tot,
                mos_type=mos_type,
                threshold=threshold,
            )
            master_dum = self.new_template(params=dum_params, temp_cls=DeviceFill)
            self.add_instance(master_dum)

        # TODO: fill metal too
        res_w = grid.get_track_info(top_layer).width
        self.sch_params = dict(
            res_p=dict(layer=top_layer, w=res_w, l=res_w2 * 2),
            res_n=dict(layer=top_layer, w=res_w, l=res_w4 * 2),
        )
