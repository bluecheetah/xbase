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

from typing import Any, Dict, List, Tuple, Optional

from bag.util.immutable import Param
from bag.layout.template import TemplateDB

from xbase.layout.enum import MOSType, Alignment
from xbase.layout.wires import WireData
from xbase.layout.mos.placement.data import MOSArrayPlaceInfo, make_pinfo_compact
from xbase.layout.mos.data import MOSRowSpecs
from xbase.layout.mos.base import MOSBasePlaceInfo, MOSBase


class MOSOnly(MOSBase):
    """A MOSBase of only rows of transistors, no connection specs.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            lch='channel length.',
            fg='number of fingers.',
            row_list='list of mos_type/width/threshold tuples.',
            min_ntr='minimum number of horizontal tracks per row.',
            w_list='list of transistor widths.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(min_ntr=0, w_list=None)

    def draw_layout(self):
        lch: int = self.params['lch']
        fg: int = self.params['fg']
        row_list: List[Tuple[str, int, str]] = self.params['row_list']
        min_ntr: int = self.params['min_ntr']
        w_list: Optional[List[int]] = self.params['w_list']

        if not row_list:
            raise ValueError('Cannot draw empty rows.')
        if w_list is None:
            w_list = [info[1] for info in row_list]
        elif len(w_list) != len(row_list):
            raise ValueError('width list length mismatch')

        row_specs = []
        hm_layer = MOSBasePlaceInfo.get_conn_layer(self.grid.tech_info, lch) + 1
        empty_wires = WireData.make_wire_data([], Alignment.CENTER_COMPACT, '')
        for info in row_list:
            mtype, w, th = info[:3]
            if len(info) > 3:
                flip = info[3]
            else:
                flip = False
            row_specs.append(MOSRowSpecs(MOSType[mtype], w, th, empty_wires, empty_wires,
                                         flip=flip))

        ainfo = MOSArrayPlaceInfo(self.grid, lch, {}, {})
        min_height = self.grid.get_track_pitch(hm_layer) * min_ntr
        pinfo = make_pinfo_compact(ainfo, row_specs, True, True, min_height=min_height)

        self.draw_base(pinfo)
        self.set_mos_size(fg)

        for ridx in range(len(row_list)):
            self.add_mos(ridx, 0, fg, w=w_list[ridx])


class MOSOnlySPM(MOSBase):
    """A MOSBase of only rows of transistors, no connection specs.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            lch='channel length.',
            fg='number of fingers.',
            fg_sp='number of fingers in space block.',
            row_list='list of mos_type/width/threshold tuples.',
            min_ntr='minimum number of horizontal tracks per row.',
            mos_sub='True to draw transistor and substrate.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(mos_sub=False, min_ntr=0)

    def draw_layout(self):
        lch: int = self.params['lch']
        fg: int = self.params['fg']
        fg_sp: int = self.params['fg_sp']
        row_list: List[Tuple[str, int, str]] = self.params['row_list']
        min_ntr: int = self.params['min_ntr']
        mos_sub: bool = self.params['mos_sub']

        if not row_list:
            raise ValueError('Cannot draw empty rows.')

        row_specs = []
        empty_wires = WireData.make_wire_data([], Alignment.CENTER_COMPACT, '')
        hm_layer = MOSBasePlaceInfo.get_conn_layer(self.grid.tech_info, lch) + 1
        for mtype, w, th in row_list:
            row_specs.append(MOSRowSpecs(MOSType[mtype], w, th, empty_wires, empty_wires))

        ainfo = MOSArrayPlaceInfo(self.grid, lch, {}, {})
        min_height = self.grid.get_track_pitch(hm_layer) * min_ntr
        pinfo = make_pinfo_compact(ainfo, row_specs, True, True, min_height=min_height)

        self.draw_base(pinfo)
        self.set_mos_size(2 * fg + fg_sp)

        for ridx in range(len(row_list)):
            self.add_mos(ridx, 0, fg)
            if mos_sub:
                self.add_substrate_contact(ridx, fg + fg_sp, seg=fg)
            else:
                self.add_mos(ridx, fg + fg_sp, fg)


class MOSOnlySPE(MOSBase):
    """A MOSBase of only rows of transistors, no connection specs.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            lch='channel length.',
            fg='number of fingers.',
            fg_sp='number of fingers in space block.',
            row_list='list of mos_type/width/threshold tuples.',
        )

    def draw_layout(self):
        lch: int = self.params['lch']
        fg: int = self.params['fg']
        fg_sp: int = self.params['fg_sp']
        row_list: List[Tuple[str, int, str]] = self.params['row_list']

        if not row_list:
            raise ValueError('Cannot draw empty rows.')

        row_specs = []
        empty_wires = WireData.make_wire_data([], Alignment.CENTER_COMPACT, '')
        for mtype, w, th in row_list:
            row_specs.append(MOSRowSpecs(MOSType[mtype], w, th, empty_wires, empty_wires))

        ainfo = MOSArrayPlaceInfo(self.grid, lch, {}, {})
        pinfo = make_pinfo_compact(ainfo, row_specs, True, True)

        self.draw_base(pinfo)
        self.set_mos_size(2 * fg_sp + fg)

        for ridx in range(len(row_list)):
            self.add_mos(ridx, fg_sp, fg)


class SubOnly(MOSBase):
    """A MOSBase of only rows of transistors, no connection specs.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            lch='channel length.',
            fg='number of fingers.',
            row_list='list of mos_type/width/threshold tuples.',
        )

    def draw_layout(self):
        lch: int = self.params['lch']
        fg: int = self.params['fg']
        row_list: List[Tuple[str, int, str]] = self.params['row_list']

        if not row_list:
            raise ValueError('Cannot draw empty rows.')

        row_specs = []
        empty_wires = WireData.make_wire_data([], Alignment.CENTER_COMPACT, '')
        for mtype, w, th in row_list:
            row_specs.append(MOSRowSpecs(MOSType[mtype], w, th, empty_wires, empty_wires))

        ainfo = MOSArrayPlaceInfo(self.grid, lch, {}, {})
        pinfo = make_pinfo_compact(ainfo, row_specs, True, True)

        self.draw_base(pinfo)
        self.set_mos_size(fg)

        for ridx in range(len(row_list)):
            self.add_substrate_contact(ridx, 0, seg=fg)
