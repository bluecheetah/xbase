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

from bag.design.database import ModuleDB
from bag.design.module import Module
from bag.util.immutable import Param
from bag.layout.template import TemplateDB

from ..enum import MOSType, MOSWireType
from .placement.data import MOSArrayPlaceInfo, make_pinfo_compact
from .data import MOSRowSpecs
from .base import MOSBase
from .top import MOSBaseWrapper


class MOSCharCore(MOSBase):
    """A MOSBase of only rows of transistors, no connection specs.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        # noinspection PyTypeChecker
        return ModuleDB.get_schematic_class('xbase', 'mos_char')

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

        fg_tot = fg_dum * 2 + seg * stack
        self.set_mos_size(fg_tot)

        b_bot = self.add_substrate_contact(0, 0, seg=fg_tot)
        b_top = self.add_substrate_contact(2, 0, seg=fg_tot)
        mos = self.add_mos(1, fg_dum, seg, stack=stack, abut=True)

        d_tid = self.get_track_id(1, MOSWireType.DS, 'd')
        g_tid = self.get_track_id(1, MOSWireType.G, 'g')
        s_tid = self.get_track_id(1, MOSWireType.DS, 's')
        b_tid0 = self.get_track_id(0, MOSWireType.DS, 'b')
        b_tid1 = self.get_track_id(2, MOSWireType.DS, 'b')

        d = self.connect_to_tracks(mos.d, d_tid)
        g = self.connect_to_tracks(mos.g, g_tid)
        s = self.connect_to_tracks(mos.s, s_tid)

        # TODO: support dummy transistors
        # duml = self.add_mos(1, 0, fg_dum)
        # dumr = self.add_mos(1, fg_tot, fg_dum, flip_lr=True)
        # s_duml = duml.s[:-1]
        # s_dumr = dumr.s[:-1]
        # b_warrs0 = [b_bot, duml.d, dumr.d, s_duml, s_dumr]
        # b_warrs1 = [b_top, duml.d, dumr.d, s_duml, s_dumr]
        # b0 = self.connect_to_tracks(b_warrs0, b_tid0)
        # b1 = self.connect_to_tracks(b_warrs1, b_tid1)
        b0 = self.connect_to_tracks(b_bot, b_tid0)
        b1 = self.connect_to_tracks(b_top, b_tid1)

        self.add_pin('d', d)
        self.add_pin('g', g)
        self.add_pin('s', s)
        # self.add_pin('b', b0)
        # self.add_pin('b', b1)
        self.add_pin('b', b0, label='b:')
        self.add_pin('b', b1, label='b:')

        self.sch_params = dict(
            mos_type=mos_type_str,
            w=w,
            lch=lch,
            seg=seg,
            intent=intent,
            stack=stack,
            dum_info=[],
            # dum_info=[((mos_type_str, w, lch, intent, '', 's'), 2 * fg_dum)],
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
