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

"""This module defines abstract analog mosfet template classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple, Dict, Any, List, Mapping

import abc
import math
import bisect

from bag.math import lcm
from bag.util.immutable import Param, ImmutableList
from bag.layout.tech import TechInfo
from bag.layout.routing.grid import TrackSpec

from ..data import LayoutInfo, CornerLayInfo
from ..enum import MOSType, MOSCutMode, MOSAbutMode

from .data import (
    MOSRowSpecs, MOSRowInfo, RowExtInfo, MOSEdgeInfo, MOSLayInfo, ExtWidthInfo, ExtEndLayInfo,
    MOSBaseEndInfo, BlkExtInfo
)

if TYPE_CHECKING:
    from .base import MOSBasePlaceInfo


def _get_end_block_info(h_ext: int, h_end_min: int, blk_h: int) -> Tuple[int, int]:
    h_blk = -(-max(0, h_end_min - h_ext) // blk_h) * blk_h
    h_mos_end = h_blk + h_ext
    return h_mos_end, h_blk


class MOSTech(abc.ABC):
    """An abstract class for drawing transistor related layout.

    This class defines various methods use to draw layouts used by MOSBase.

    Parameters
    ----------
    tech_info : TechInfo
        the TechInfo object.
    lch : int
        the channel length.
    arr_options : Mapping[str, Any]
        process-specific options for the transistor array.
    """

    def __init__(self, tech_info: TechInfo, lch: int, arr_options: Mapping[str, Any]) -> None:
        self._tech_info = tech_info
        self._lch = lch
        self._arr_options = arr_options

        # fill config dictionary
        mos_entry_name: str = arr_options.get('mos_entry_name', 'mos')
        self._mos_config = {}
        for k, v in tech_info.config[mos_entry_name].items():
            if isinstance(v, dict):
                lch_list = v.get('lch', None)
                if lch_list is None:
                    self._mos_config[k] = v
                else:
                    idx = bisect.bisect_left(lch_list, lch)
                    self._mos_config[k] = v['val'][idx]
            else:
                self._mos_config[k] = v

    @property
    @abc.abstractmethod
    def blk_h_pitch(self) -> int:
        return 2

    @property
    @abc.abstractmethod
    def end_h_min(self) -> int:
        return 0

    @property
    @abc.abstractmethod
    def min_sep_col(self) -> int:
        raise NotImplementedError('Not implemented')

    @property
    @abc.abstractmethod
    def sub_sep_col(self) -> int:
        """int: column separation needed between transistor/substrate and substrate/substrate.

        This is guaranteed to be even.
        """
        raise NotImplementedError('Not implemented')

    @property
    @abc.abstractmethod
    def min_sub_col(self) -> int:
        raise NotImplementedError('Not implemented')

    @property
    @abc.abstractmethod
    def gr_edge_col(self) -> int:
        raise NotImplementedError('Not implemented')

    @property
    @abc.abstractmethod
    def abut_mode(self) -> MOSAbutMode:
        raise NotImplementedError('Not implemented')

    @abc.abstractmethod
    def can_short_adj_tracks(self, conn_layer: int) -> bool:
        raise NotImplementedError('Not implemented')

    @abc.abstractmethod
    def get_track_specs(self, conn_layer: int, top_layer: int) -> List[TrackSpec]:
        return []

    @abc.abstractmethod
    def get_edge_width(self, mos_arr_width: int, blk_pitch: int) -> int:
        return 0

    @abc.abstractmethod
    def get_mos_row_info(self, conn_layer: int, specs: MOSRowSpecs, bot_mos_type: MOSType,
                         top_mos_type: MOSType, global_options: Param) -> MOSRowInfo:
        raise NotImplementedError('Not implemented')

    @abc.abstractmethod
    def get_ext_width_info(self, bot_row_ext_info: RowExtInfo, top_row_ext_info: RowExtInfo,
                           ignore_vm_sp_le: bool = False) -> ExtWidthInfo:
        return ExtWidthInfo([], 0, 1)

    @abc.abstractmethod
    def get_extension_regions(self, bot_info: RowExtInfo, top_info: RowExtInfo, height: int
                              ) -> Tuple[MOSCutMode, int, int]:
        return MOSCutMode.BOTH, 0, 0

    @abc.abstractmethod
    def get_mos_conn_info(self, row_info: MOSRowInfo, conn_layer: int, seg: int, w: int, stack: int,
                          g_on_s: bool, options: Param) -> MOSLayInfo:
        raise NotImplementedError('Not implemented')

    @abc.abstractmethod
    def get_mos_abut_info(self, row_info: MOSRowInfo, edgel: MOSEdgeInfo, edger: MOSEdgeInfo
                          ) -> LayoutInfo:
        raise NotImplementedError('Not implemented')

    @abc.abstractmethod
    def get_mos_tap_info(self, row_info: MOSRowInfo, conn_layer: int, seg: int,
                         options: Param) -> MOSLayInfo:
        raise NotImplementedError('Not implemented')

    @abc.abstractmethod
    def get_mos_space_info(self, row_info: MOSRowInfo, num_cols: int, left_info: MOSEdgeInfo,
                           right_info: MOSEdgeInfo) -> MOSLayInfo:
        raise NotImplementedError('Not implemented')

    @abc.abstractmethod
    def get_mos_ext_info(self, num_cols: int, blk_h: int, bot_einfo: RowExtInfo,
                         top_einfo: RowExtInfo, gr_info: Tuple[int, int]) -> ExtEndLayInfo:
        raise NotImplementedError('Not implemented')

    @abc.abstractmethod
    def get_mos_ext_gr_info(self, num_cols: int, edge_cols: int, blk_h: int, bot_einfo: RowExtInfo,
                            top_einfo: RowExtInfo, sub_type: MOSType, einfo: MOSEdgeInfo
                            ) -> ExtEndLayInfo:
        raise NotImplementedError('Not implemented')

    @abc.abstractmethod
    def get_ext_geometries(self, re_bot: RowExtInfo, re_top: RowExtInfo,
                           be_bot: ImmutableList[BlkExtInfo], be_top: ImmutableList[BlkExtInfo],
                           cut_mode: MOSCutMode, bot_exty: int, top_exty: int,
                           dx: int, dy: int, w_edge: int) -> LayoutInfo:
        raise NotImplementedError('Not implemented')

    @abc.abstractmethod
    def get_mos_end_info(self, blk_h: int, num_cols: int, einfo: RowExtInfo) -> ExtEndLayInfo:
        raise NotImplementedError('Not implemented')

    @abc.abstractmethod
    def get_mos_row_edge_info(self, blk_w: int, rinfo: MOSRowInfo, einfo: MOSEdgeInfo
                              ) -> LayoutInfo:
        raise NotImplementedError('Not implemented')

    @abc.abstractmethod
    def get_mos_ext_edge_info(self, blk_w: int, einfo: MOSEdgeInfo) -> LayoutInfo:
        raise NotImplementedError('Not implemented')

    @abc.abstractmethod
    def get_mos_corner_info(self, blk_w: int, blk_h: int, einfo: MOSEdgeInfo) -> CornerLayInfo:
        raise NotImplementedError('Not implemented')

    @property
    def lch(self) -> int:
        return self._lch

    @property
    def arr_options(self) -> Mapping[str, Any]:
        return self._arr_options

    @property
    def tech_info(self) -> TechInfo:
        return self._tech_info

    @property
    def mos_config(self) -> Dict[str, Any]:
        return self._mos_config

    @property
    def conn_layer(self) -> int:
        return self.mos_config['conn_layer']

    @property
    def sub_w_default(self) -> int:
        return self.mos_config['sub_w_default']

    @property
    def w_range(self) -> Tuple[int, int]:
        return self.mos_config['mos_w_range']

    @property
    def w_resolution(self) -> int:
        return self.mos_config['mos_w_resolution']

    @property
    def sd_pitch(self) -> int:
        sd_constants: Tuple[int, int] = self.mos_config['sd_pitch_constants']
        return sd_constants[0] + self.lch * sd_constants[1]

    def get_mos_base_end_info(self, pinfo: MOSBasePlaceInfo, blk_pitch: int) -> MOSBaseEndInfo:
        blk_pitch = lcm([self.blk_h_pitch, blk_pitch])

        bot_rpinfo = pinfo.get_row_place_info(0)
        top_rpinfo = pinfo.get_row_place_info(-1)

        h_ext_bot = bot_rpinfo.yb_blk - bot_rpinfo.yb
        h_ext_top = top_rpinfo.yt - top_rpinfo.yt_blk

        h_end_min = self.end_h_min
        h_mos_end_bot, h_blk_bot = _get_end_block_info(h_ext_bot, h_end_min, blk_pitch)
        h_mos_end_top, h_blk_top = _get_end_block_info(h_ext_top, h_end_min, blk_pitch)
        return MOSBaseEndInfo((h_mos_end_bot, h_mos_end_top), (h_blk_bot, h_blk_top))

    def get_segments_from_em(self, conn_layer: int, idc: float = 0, iac_rms: float = 0,
                             iac_peak: float = 0, even: bool = False, **kwargs: Any) -> int:
        tech_info = self.tech_info

        tr_specs = self.get_track_specs(conn_layer, conn_layer + 1)
        lay, purp = tech_info.get_lay_purp_list(conn_layer)[0]
        tr_w = tr_specs[0].width

        idc_unit, iac_unit, ipeak_unit = tech_info.get_metal_em_specs(lay, purp, tr_w, **kwargs)
        num_wire = 1
        if idc_unit > 0:
            num_wire = max(num_wire, math.ceil(idc / idc_unit))
        if iac_unit > 0:
            num_wire = max(num_wire, math.ceil(iac_rms / iac_unit))
        if ipeak_unit > 0:
            num_wire = max(num_wire, math.ceil(iac_peak / ipeak_unit))

        seg = 2 * num_wire - 1
        return seg + int(even)
