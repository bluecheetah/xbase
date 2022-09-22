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
import math 

from pybag.core import BBox, BBoxArray
from pybag.enum import RoundMode, Orient2D

from bag.util.immutable import Param
from bag.design.module import Module
from bag.layout.routing.grid import FillConfigType
from bag.layout.template import TemplateDB, TemplateBase

from xbase.layout.fill.base import DeviceFill
from xbase.schematic.momcap_core import xbase__momcap_core
from xbase.layout.data import LayoutInfo, draw_layout_in_template
from xbase.layout.cap.tech import MIMTech, MIMLayInfo


class MIMCapCore(TemplateBase):
    """MIMCap core
    """

    def __init__(self, temp_db: TemplateDB,
                 params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return xbase__momcap_core

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            top_layer=0,
            bot_layer=0,
            height=0,
            unit_height=0,
            unit_width=0,
            width=0,
            width_total=0,
            rotateable=False
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        ans = DeviceFill.get_default_param_values()
        ans.update(
            cap_config={},

        )
        return ans

    def draw_layout(self) -> None:

        grid = self.grid
        scaling = int(1/grid.resolution)

        bot_layer: int = self.params['bot_layer']
        top_layer: int = self.params['top_layer']
        width: int = self.params['width'] * scaling
        height: int = self.params['height'] * scaling
        unit_width: int = self.params['unit_width'] * scaling
        unit_height: int = self.params['unit_height'] * scaling
        width_total: int = self.params['width_total'] * scaling
        rotateable: bool = self.params['rotateable']
        array = True if (unit_width < width_total or
                         unit_height < height) else False

        top_cap = max(top_layer, bot_layer)
        bot_cap = min(top_layer, bot_layer)
        w_blk, h_blk = self.grid.get_block_size(top_cap, half_blk_x=True,
                                                half_blk_y=True) 
        tech_cls: MIMTech = grid.tech_info.get_device_tech('mim')

        # function in primitive
        mim_info: MIMLayInfo = tech_cls.get_mim_cap_info(top_cap,
                                                         bot_cap, width_total,
                                                         width, height, array,
                                                         unit_width,
                                                         unit_height)
        draw_layout_in_template(self, mim_info.lay_info)
        layoutinfo = mim_info.lay_info
                     
        # get pin box info
        xh = -(-layoutinfo.bound_box.xh//w_blk)*w_blk
        xl = -(-layoutinfo.bound_box.xl//w_blk)*w_blk
        yh = -(-layoutinfo.bound_box.yh//h_blk)*h_blk
        yl = -(-layoutinfo.bound_box.yl//h_blk)*h_blk

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
                top_tr = grid.coord_to_track(top_cap, xh, mode=RoundMode.LESS)
                top_pin = self.add_wires(top_cap, top_tr, mim_info.pin_top_yl,
                                         mim_info.pin_top_yh)
            else:  
                top_tr = grid.coord_to_track(top_cap, (yh+yl)//2, 
                                             mode=RoundMode.LESS)
                tr_wid = grid.coord_to_track(top_cap, yh) \
                    - grid.coord_to_track(top_cap, yl)
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
                tr_wid = grid.coord_to_track(bot_cap, yh) \
                    - grid.coord_to_track(bot_cap, yl)
                bot_pin = self.add_wires(bot_cap, bot_tr, bot_pin_x+w_blk,
                                         bot_pin_x+2*w_blk,
                                         width=math.floor(tr_wid))
            self.add_pin('bot', bot_pin)

