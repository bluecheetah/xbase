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

"""This module defines the default transistor characterization layout generator."""

from typing import Any, Dict, Optional, Type

from bag.design.module import Module
from bag.util.immutable import Param
from bag.layout.template import TemplateDB

from ..enum import MOSType, MOSWireType
from .placement.data import MOSArrayPlaceInfo, make_pinfo_compact
from .data import MOSRowSpecs
from .base import MOSBase
from .top import MOSBaseWrapper

from ...schematic.mos_char import xbase__mos_char


class MOSCharCore(MOSBase):
    """A MOSBase of only rows of transistors, no connection specs.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return xbase__mos_char

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            mos_type='transistor type.',
            w='transistor width.',
            lch='channel length.',
            seg='number of segments.',
            fg_dum='number of dummy fingers.',
            intent='threshold flavor.',
            stack='number of transistors in a stack.',
            tr_widths='TrackManager width dictionary.',
            tr_spaces='TrackManager space dictionary.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(stack=1)

    def draw_layout(self):
        mos_type_str: str = self.params['mos_type']
        w: int = self.params['w']
        lch: int = self.params['lch']
        seg: int = self.params['seg']
        fg_dum: int = self.params['fg_dum']
        intent: str = self.params['intent']
        stack: int = self.params['stack']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']

        assert seg & 1 == 0, f'This generator requires seg={seg} to be even. MOS characterization results are ' \
                             f'reported per finger, so this restriction is not an issue.'
        assert fg_dum & 1 == 0, f'This generator requires fg_dum={fg_dum} to be even.'

        mos_type: MOSType = MOSType[mos_type_str]
        if mos_type.is_substrate:
            raise ValueError('Can only draw transistors.')
        sub_type = mos_type.sub_type

        row_specs_dict = [
            dict(
                mos_type=sub_type.name,
                width=w,
                threshold=intent,
                bot_wires=[],
                top_wires=['b'],
            ),
            dict(
                mos_type=mos_type.name,
                width=w,
                threshold=intent,
                bot_wires=['g'],
                top_wires=['s', 'd'],
            ),
            dict(
                mos_type=sub_type.name,
                width=w,
                threshold=intent,
                bot_wires=['b'],
                top_wires=[],
                flip=True,
            ),
        ]

        row_specs = [MOSRowSpecs.make_row_specs(table) for table in row_specs_dict]
        ainfo = MOSArrayPlaceInfo(self.grid, lch, tr_widths, tr_spaces)
        pinfo = make_pinfo_compact(ainfo, row_specs, True, True)

        self.draw_base(pinfo)

        tap_ncols = self.get_tap_ncol()
        seg_sep = self.min_sep_col
        seg_sep_sub = self.sub_sep_col
        row_info = pinfo.get_row_place_info(1).row_info

        # --- Placement --- #
        # Row 1: tap, dum, mos, dum, tap
        vdd_list, vss_list = [], []
        cur_col = 0
        self.add_tap(cur_col, vdd_list, vss_list)
        cur_col += tap_ncols + seg_sep_sub
        duml = self.add_mos(1, cur_col, fg_dum)
        cur_col += fg_dum
        if not self.can_abut_mos(row_info):
            cur_col += seg_sep
        mos = self.add_mos(1, cur_col, seg, stack=stack, abut=True)
        cur_col += seg * stack
        if not self.can_abut_mos(row_info):
            cur_col += seg_sep
        cur_col += fg_dum
        dumr = self.add_mos(1, cur_col, fg_dum, flip_lr=True)
        cur_col += seg_sep_sub + tap_ncols
        self.add_tap(cur_col, vdd_list, vss_list, flip_lr=True)

        self.set_mos_size(cur_col)

        # Rows 0 and 2: substrate rows
        b_bot = self.add_substrate_contact(0, 0, seg=cur_col)
        b_top = self.add_substrate_contact(2, 0, seg=cur_col)

        # --- Routing --- #
        d_tid = self.get_track_id(1, MOSWireType.DS, 'd')
        d = self.connect_to_tracks(mos.d, d_tid)
        self.add_pin('d', d)

        g_tid = self.get_track_id(1, MOSWireType.G, 'g')
        g = self.connect_to_tracks(mos.g, g_tid)
        self.add_pin('g', g)

        s_tid = self.get_track_id(1, MOSWireType.DS, 's')
        s = self.connect_to_tracks(mos.s, s_tid)
        self.add_pin('s', s)

        b_tid0 = self.get_track_id(0, MOSWireType.DS, 'b')
        b_tid1 = self.get_track_id(2, MOSWireType.DS, 'b')

        if self.can_abut_mos(row_info):
            s_duml = duml.s[:-1]
            s_dumr = dumr.s[:-1]
            dum_info = [((mos_type_str, w, lch, intent, '', ''), 2 * fg_dum - 2),
                        ((mos_type_str, w, lch, intent, 's', ''), 2)]
        else:
            s_duml = duml.s
            s_dumr = dumr.s
            dum_info = [((mos_type_str, w, lch, intent, '', ''), fg_dum),
                        ((mos_type_str, w, lch, intent, '', ''), fg_dum)]
        b_warrs0 = [b_bot, duml.d, dumr.d, s_duml, s_dumr]
        b_warrs1 = [b_top, duml.d, dumr.d, s_duml, s_dumr]
        b_warrs0.extend(vdd_list)
        b_warrs0.extend(vss_list)
        b_warrs1.extend(vdd_list)
        b_warrs1.extend(vss_list)
        b0 = self.connect_to_tracks(b_warrs0, b_tid0)
        b1 = self.connect_to_tracks(b_warrs1, b_tid1)
        self.add_pin('b', [b0, b1])

        self.sch_params = dict(
            mos_type=mos_type_str,
            w=w,
            lch=lch,
            seg=seg,
            intent=intent,
            stack=stack,
            dum_info=dum_info,
        )


class MOSChar(MOSBaseWrapper):
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBaseWrapper.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return MOSCharCore.get_params_info()

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return MOSCharCore.get_default_param_values()

    def get_layout_basename(self) -> str:
        return 'MOSChar'

    def draw_layout(self):
        master = self.new_template(MOSCharCore, params=self.params)
        inst = self.draw_boundaries(master, master.top_layer)
        self.sch_params = master.sch_params

        # re-export pins
        for name in inst.port_names_iter():
            self.reexport(inst.get_port(name))
