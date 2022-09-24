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

"""This module defines various MIM cap related templates."""

from typing import Any, Optional, Mapping, Type
import math 

from pybag.core import BBox
from pybag.enum import RoundMode, Orient2D

from bag.util.immutable import Param
from bag.design.module import Module
from bag.layout.template import TemplateDB, TemplateBase

from xbase.layout.fill.base import DeviceFill
from xbase.schematic.mimcap_core import xbase__mimcap_core
from xbase.layout.data import draw_layout_in_template
from xbase.layout.cap.tech import MIMTech, MIMLayInfo


class MIMCapCore(TemplateBase):
    """MIMCap core
    """

    def __init__(self, temp_db: TemplateDB,
                 params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return xbase__mimcap_core

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            top_layer='Top layer of MIM cap',
            bot_layer='Bottom layer of MIM cap',
            unit_height='height of single unit (for array)',
            unit_width='width of single unit (for array)',
            rows='number of rows',
            columns='number of columns',
            dum_columns='number of dummy columns',
            rotateable='True if horizontal cap, false if cap needs to be rotated vertically'
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        ans = DeviceFill.get_default_param_values()
        ans.update(
            top_layer=0,
            bot_layer=0,
            unit_height=0,
            unit_width=0,
            rows=1,
            columns=1,
            dum_columns=0,
            rotateable=False
        )
        return ans

    def draw_layout(self) -> None:

        grid = self.grid

        bot_layer: int = self.params['bot_layer']
        top_layer: int = self.params['top_layer']
        unit_width: int = self.params['unit_width'] 
        unit_height: int = self.params['unit_height'] 
        rows: int = self.params['rows'] 
        columns: int = self.params['columns']
        dum_columns: int = self.params['dum_columns']
        rotateable: bool = self.params['rotateable']

        top_cap = max(top_layer, bot_layer)
        bot_cap = min(top_layer, bot_layer)
        w_blk, h_blk = self.grid.get_block_size(top_cap, half_blk_x=True,
                                                half_blk_y=True) 
        tech_cls: MIMTech = grid.tech_info.get_device_tech('mim')

        # function in primitive
        mim_info: MIMLayInfo = tech_cls.get_mim_cap_info(top_cap,
                                                         bot_cap, rows, columns, 
                                                         dum_columns,
                                                         unit_width,
                                                         unit_height)
        draw_layout_in_template(self, mim_info.lay_info)
        layoutinfo = mim_info.lay_info
                     
        # get pin box info
        xh = (layoutinfo.bound_box.xh//w_blk)*w_blk
        xl = -(-layoutinfo.bound_box.xl//w_blk)*w_blk
        yh = -(-layoutinfo.bound_box.yh//h_blk)*h_blk
        yl = (layoutinfo.bound_box.yl//h_blk)*h_blk

        self.set_size_from_bound_box(top_cap, BBox(0, 0, xh, yh))
        bot_pin_x = -(-mim_info.pin_bot_xh//w_blk)*w_blk

        # add primitive or wire pins depending on if need to rotate
        if rotateable:
            self.add_pin_primitive('bot', bot_cap,
                                   BBox(int(xl), int(mim_info.pin_top_yl), 
                                        int(xl+w_blk), int(mim_info.pin_top_yh)
                                        ))
            self.add_pin_primitive('top', top_cap,
                                   BBox(int(xh-w_blk),
                                        int(mim_info.pin_bot_yl),
                                        int(xh), int(mim_info.pin_bot_yh)))
        else:
            top_dir = grid.get_direction(top_cap)
            if top_dir == Orient2D.y:
                top_tr = grid.coord_to_track(top_cap, xh, mode=RoundMode.LESS_EQ)
                top_pin = self.add_wires(top_cap, top_tr, mim_info.pin_top_yl,
                                         mim_info.pin_top_yh)
            else:  
                top_tr = grid.coord_to_track(top_cap, (yh+yl)//2, 
                                             mode=RoundMode.LESS_EQ)
                tr_wid = grid.coord_to_track(top_cap, yh) - grid.coord_to_track(top_cap, yl)
                top_pin = self.add_wires(top_cap, top_tr, xh-w_blk, xh,
                                         width=math.floor(tr_wid))
            self.add_pin('top', top_pin)

            bot_dir = grid.get_direction(bot_cap)
            if bot_dir == Orient2D.y:
                bot_tr = grid.coord_to_track(bot_cap, bot_pin_x,
                                             mode=RoundMode.GREATER_EQ)
                bot_pin = self.add_wires(bot_cap, bot_tr, mim_info.pin_bot_yl,
                                         mim_info.pin_bot_yh)
            else: 
                bot_tr = grid.coord_to_track(bot_cap, (yh+yl)//2,
                                             mode=RoundMode.GREATER_EQ)
                tr_wid = grid.coord_to_track(bot_cap, yh) - grid.coord_to_track(bot_cap, yl)
                bot_pin = self.add_wires(bot_cap, bot_tr, bot_pin_x,
                                         bot_pin_x+w_blk,
                                         width=math.floor(tr_wid))
            self.add_pin('bot', bot_pin)

    
        # draw metal resistors
        if self.has_res_metal():
            # _, _, barr_n, barr_p = cw_list[-1]
            # TODO: check in process with resistor metals
            box_p = BBox(int(xh-w_blk),
                         int(mim_info.pin_bot_yl),
                         int(xh), int(mim_info.pin_bot_yh))
            box_n = BBox(int(xl), int(mim_info.pin_top_yl), 
                         int(xl+w_blk), int(mim_info.pin_top_yh)
                         )
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
                has_res_metal=True,
                res_p=dict(layer=top_layer, w=res_w, l=res_w * 2),
                res_n=dict(layer=top_layer, w=res_w, l=res_w * 2),
            )
            
        else:
            self.sch_params = dict(has_res_metal=False)

