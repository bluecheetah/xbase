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

"""This module shows an example of a double gate device."""

from typing import Any, Dict, Optional, Type

from bag.design.module import Module
from bag.util.immutable import Param
from bag.layout.template import TemplateDB

from xbase.layout.enum import MOSWireType
from xbase.layout.mos.data import MOSRowInfo
from xbase.layout.mos.base import MOSBase, MOSBasePlaceInfo
from xbase.layout.mos.top import MOSBaseWrapper

from xbase.schematic.mos_char import xbase__mos_char


class DoubleGateCore(MOSBase):
    """An example layout of a double gate to show usage.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return xbase__mos_char

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            pinfo='The MOSBasePlaceInfo object.',
            w='transistor width.',
            seg='number of segments.',
            g_on_s='True to draw gate on source',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(g_on_s=False)

    def draw_layout(self):
        seg: int = self.params['seg']
        w: int = self.params['w']
        g_on_s: bool = self.params['g_on_s']

        pinfo = MOSBasePlaceInfo.make_place_info(self.grid, self.params['pinfo'])
        self.draw_base(pinfo)

        dev_row = 1
        rinfo: MOSRowInfo = self.get_row_info(dev_row)
        lch = rinfo.lch
        mos_type_str = rinfo.row_type.name
        intent = rinfo.threshold

        if not rinfo.double_gate:
            raise ValueError("double_gate is not set to True in pinfo")

        # Optional flags draw_g and draw_g2 set which gate connections to draw.
        ports = self.add_mos(row_idx=dev_row, col_idx=0, seg=seg, g_on_s=g_on_s, sep_g=False,
                             w=w, draw_g=True, draw_g2=True)
        b_bot = self.add_substrate_contact(0, 0, seg=seg)
        b_top = self.add_substrate_contact(2, 0, seg=seg)

        self.set_mos_size()

        g = ports.g
        g2 = ports.g2
        s = ports.s
        d = ports.d

        g_tid = self.get_track_id(dev_row, MOSWireType.G, 'sig')
        g2_tid = self.get_track_id(dev_row, MOSWireType.G2, 'sig')
        d_tid = self.get_track_id(dev_row, MOSWireType.DS, 'sig', 0)
        s_tid = self.get_track_id(dev_row, MOSWireType.DS, 'sig', -1)
        
        b_tid0 = self.get_track_id(0, MOSWireType.DS, 'b')
        b_tid1 = self.get_track_id(2, MOSWireType.DS, 'b')

        b0 = self.connect_to_tracks(b_bot, b_tid0)
        b1 = self.connect_to_tracks(b_top, b_tid1)

        g_hm = self.connect_to_tracks(g, g_tid)
        g2_hm = self.connect_to_tracks(g2, g2_tid)

        s_hm = self.connect_to_tracks(s, s_tid)
        d_hm = self.connect_to_tracks(d, d_tid)

        
        self.add_pin('g', [g_hm, g2_hm], connect=True)
        self.add_pin('s', s_hm)
        self.add_pin('d', d_hm)
        self.add_pin('b', [b0, b1], connect=True)

        self.sch_params = dict(
            mos_type=mos_type_str,
            w=w,
            lch=lch,
            seg=seg,
            intent=intent,
            dum_info=[],
        )
