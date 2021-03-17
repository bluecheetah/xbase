# BSD 3-Clause License
#
# Copyright (c) 2018, Regents of the University of California
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""This module defines MOM cap on MOSBase."""

from typing import Any, Dict, Optional, Mapping, List, Tuple, Type

from pybag.core import BBox, BBoxArray

from bag.util.immutable import Param
from bag.design.module import Module
from bag.layout.template import TemplateDB

from xbase.layout.mos.base import MOSBasePlaceInfo, MOSBase
from xbase.schematic.momcap_core import xbase__momcap_core


class MOMCapOnMOS(MOSBase):
    """MOMCap core on MOSBase
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return xbase__momcap_core

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            pinfo='The MOSBasePlaceInfo object.',
            bot_layer='MOM cap bottom layer.',
            top_layer='MOM cap top layer.',
            width='MOM cap width, in resolution units.',
            margin='margin between cap and boundary, in resolution units.',
            port_tr_w='MOM cap port track width, in number of tracks.',
            options='MOM cap layout options.',
            half_blk_x='True to allow half horizontal blocks.',
            half_blk_y='True to allow half vertical blocks.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(
            margin=0,
            port_tr_w=1,
            options=None,
            half_blk_x=True,
            half_blk_y=True,
        )

    def draw_layout(self) -> None:
        pinfo = self.params['pinfo']
        if isinstance(pinfo, Mapping):
            pinfo = MOSBasePlaceInfo.make_place_info(self.grid, self.params['pinfo'])
        else:
            pinfo = pinfo[0]
        self.draw_base(pinfo)

        grid = self.grid

        bot_layer: int = self.params['bot_layer']
        top_layer: int = self.params['top_layer']
        width: int = self.params['width']
        margin: int = self.params['margin']
        port_tr_w: int = self.params['port_tr_w']
        options: Optional[Mapping[str, Any]] = self.params['options']
        half_blk_x: bool = self.params['half_blk_x']
        half_blk_y: bool = self.params['half_blk_y']

        w_tot = width + 2 * margin
        w_blk, h_blk = grid.get_block_size(top_layer, half_blk_x=half_blk_x,
                                           half_blk_y=half_blk_y)
        w_tot = -(-w_tot // w_blk) * w_blk
        h_tot = self.place_info.height

        # set size
        num_cols = -(-w_tot // self.sd_pitch)
        self.set_mos_size(num_cols)

        # setup capacitor options
        # get .  Make sure we can via up to top_layer + 1
        top_port_tr_w = port_tr_w
        port_w_dict = {top_layer: top_port_tr_w}
        for lay in range(top_layer - 1, bot_layer - 1, -1):
            top_port_tr_w = port_w_dict[lay] = grid.get_min_track_width(lay, top_ntr=top_port_tr_w)

        # draw cap
        cap_xl = (self.bound_box.w - width) // 2
        cap_yb = (self.bound_box.h - h_tot) // 2
        cap_box = BBox(cap_xl, cap_yb, cap_xl + width, cap_yb + h_tot)
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

        res_w = grid.get_track_info(top_layer).width
        self.sch_params = dict(
            res_p=dict(layer=top_layer, w=res_w, l=res_w2 * 2),
            res_n=dict(layer=top_layer, w=res_w, l=res_w4 * 2),
        )
