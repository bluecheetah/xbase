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

from pybag.core import BBox

from bag.util.immutable import Param
from bag.design.module import Module
from bag.layout.template import TemplateDB, TemplateBase

# from xbase.schematic.mimcap_core import xbase__mimcap_core
from xbase.layout.data import draw_layout_in_template
from xbase.layout.cap.tech import MIMTech, MIMLayInfo


class MIMCapCore(TemplateBase):
    """MIMCap core
    """
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        # return xbase__mimcap_core
        return None

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            mim_type='Type of MIM cap; standard by default',
            unit_width='width of single MIM unit (for array)',
            unit_height='height of single MIM unit (for array)',
            num_rows='number of rows',
            num_cols='number of columns',
            dum_row_b='number of dummy rows on bottom',
            dum_row_t='number of dummy rows on top',
            dum_col_l='number of dummy columns on left',
            dum_col_r='number of dummy columns on right',
            bot_port_tr_w='Track width of port on bottom layer',
            top_port_tr_w='Track width of port on top layer',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            mim_type='standard',
            num_rows=1,
            num_cols=1,
            dum_row_b=0,
            dum_row_t=0,
            dum_col_l=0,
            dum_col_r=0,
            bot_port_tr_w=1,
            top_port_tr_w=1,
        )

    def draw_layout(self) -> None:
        mim_type: str = self.params['mim_type']
        unit_width: int = self.params['unit_width']
        unit_height: int = self.params['unit_height'] 
        num_rows: int = self.params['num_rows']
        num_cols: int = self.params['num_cols']
        dum_row_b: int = self.params['dum_row_b']
        dum_row_t: int = self.params['dum_row_t']
        dum_col_l: int = self.params['dum_col_l']
        dum_col_r: int = self.params['dum_col_r']
        bot_port_tr_w: int = self.params['bot_port_tr_w']
        top_port_tr_w: int = self.params['top_port_tr_w']

        tech_cls: MIMTech = self.grid.tech_info.get_device_tech('mim')

        # primitive info
        bot_layer, top_layer = tech_cls.get_port_layers(mim_type)
        bot_w = self.grid.get_wire_total_width(bot_layer, bot_port_tr_w)
        top_w = self.grid.get_wire_total_width(top_layer, top_port_tr_w)
        mim_info: MIMLayInfo = tech_cls.get_mim_cap_info(bot_layer, top_layer, unit_width, unit_height,
                                                         num_rows, num_cols, dum_row_b, dum_row_t, dum_col_l, dum_col_r,
                                                         bot_w, top_w)
        draw_layout_in_template(self, mim_info.lay_info)
        top_bbox = mim_info.lay_info.bound_box

        self.set_size_from_bound_box(top_layer, top_bbox, round_up=True)

        # add primitive pins
        bot_lp = self.grid.tech_info.get_lay_purp_list(bot_layer)[0]
        top_lp = self.grid.tech_info.get_lay_purp_list(top_layer)[0]

        self.add_pin_primitive('bot', bot_lp[0], BBox(mim_info.pin_bot_xl, mim_info.pin_bot_y[0],
                                                      mim_info.pin_bot_xl + bot_w, mim_info.pin_bot_y[1]))
        self.add_pin_primitive('top', top_lp[0], BBox(mim_info.pin_top_xh - top_w, mim_info.pin_top_y[0],
                                                      mim_info.pin_top_xh, mim_info.pin_top_y[1]))

        # get schematic parameters
        tot_rows = num_rows + dum_row_b + dum_row_t
        tot_cols = num_cols + dum_col_l + dum_col_r
        self.sch_params = dict(
            mim_type=mim_type,
            unit_width=unit_width,
            unit_height=unit_height,
            num_rows=num_rows,
            num_cols=num_cols,
            num_dum=tot_rows * tot_cols - num_rows * num_cols,
        )
