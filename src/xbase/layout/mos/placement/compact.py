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

"""This module contains transistor row placement methods and data structures."""

from __future__ import annotations

from typing import Optional, Sequence, Tuple, Mapping, Union, Dict, List

from dataclasses import dataclass

from pybag.enum import Direction, RoundMode
from pybag.core import COORD_MIN, COORD_MAX

from bag.util.math import HalfInt
from bag.util.immutable import ImmutableSortedDict, ImmutableList, Param
from bag.layout.routing.base import TrackManager
from bag.layout.routing.grid import RoutingGrid

from ...enum import MOSWireType
from ...wires import WireGraph
from ..tech import MOSTech
from ..data import MOSRowSpecs, MOSRowInfo, RowExtInfo, RowPlaceInfo, ExtWidthInfo


def place_rows_compact(tr_manager: TrackManager, tech_cls: MOSTech,
                       specs_list: Sequence[MOSRowSpecs], tot_height_min: int,
                       tile_blk_h: int, bot_mirror: bool, top_mirror: bool, global_options: Param
                       ) -> Tuple[ImmutableList[RowPlaceInfo], List[Tuple[WireGraph, WireGraph]]]:
    pspecs_list = _get_row_place_specs(tech_cls, specs_list, global_options)
    return _place_rows(tr_manager, tech_cls, pspecs_list, tot_height_min, tile_blk_h,
                       bot_mirror, top_mirror)


@dataclass(eq=True, frozen=True, init=False)
class RowPlaceSpecs:
    """Information needed to compute placement of transistor rows."""
    row_specs: MOSRowSpecs
    row_info: MOSRowInfo
    bot_conn_y_table: ImmutableSortedDict[MOSWireType, Tuple[int, int]]
    top_conn_y_table: ImmutableSortedDict[MOSWireType, Tuple[int, int]]
    bot_ext_info: RowExtInfo
    top_ext_info: RowExtInfo
    mid_conn_y_table: Optional[ImmutableSortedDict[MOSWireType, Tuple[int, int]]]

    def __init__(self, row_specs: MOSRowSpecs, row_info: MOSRowInfo,
                 bot_conn_y_table: Mapping[MOSWireType, Tuple[int, int]],
                 top_conn_y_table: Mapping[MOSWireType, Tuple[int, int]],
                 bot_ext_info: RowExtInfo, top_ext_info: RowExtInfo,
                 mid_conn_y_table: Optional[Mapping[MOSWireType, Tuple[int, int]]] = {}):
        # work around: this is how you set attributes for frozen data classes
        object.__setattr__(self, 'row_specs', row_specs)
        object.__setattr__(self, 'row_info', row_info)
        object.__setattr__(self, 'bot_conn_y_table', ImmutableSortedDict(bot_conn_y_table))
        object.__setattr__(self, 'mid_conn_y_table', ImmutableSortedDict(mid_conn_y_table))
        object.__setattr__(self, 'top_conn_y_table', ImmutableSortedDict(top_conn_y_table))
        object.__setattr__(self, 'bot_ext_info', bot_ext_info)
        object.__setattr__(self, 'top_ext_info', top_ext_info)


class PlaceFun:
    def __init__(self, vm_layer: int, grid: RoutingGrid, table: Dict[str, int], mode: RoundMode
                 ) -> None:
        self._vm_layer = vm_layer
        self._grid = grid
        self._table = table
        self._mode = mode

    def __call__(self, ptype: str, tr_w: int, idx: HalfInt) -> HalfInt:
        y = self._table.get(ptype, None)
        if y is None:
            return idx

        grid = self._grid
        vm_ext = grid.get_via_extensions(Direction.LOWER, self._vm_layer, 1, tr_w)[0]
        return grid.find_next_track(self._vm_layer + 1, y + self._mode.value * vm_ext,
                                    tr_width=tr_w, mode=self._mode)


def _get_row_place_specs(tcls: MOSTech, specs_list: Sequence[MOSRowSpecs],
                         global_options: Param) -> Sequence[RowPlaceSpecs]:
    """For each MOSRowSpecs, construct MOSRowInfo and RowPlaceSpecs"""
    conn_layer = tcls.conn_layer

    num_rows = len(specs_list)
    info_list = []
    for row_idx, specs in enumerate(specs_list):
        if row_idx == 0:
            bot_row_type = specs.mos_type
        else:
            bot_row_type = specs_list[row_idx - 1].mos_type
        if row_idx == num_rows - 1:
            top_row_type = specs.mos_type
        else:
            top_row_type = specs_list[row_idx + 1].mos_type

        if specs.flip:
            bot_row_type, top_row_type = top_row_type, bot_row_type

        # get information dictionary
        row_info = tcls.get_mos_row_info(conn_layer, specs, bot_row_type, top_row_type,
                                         global_options)

        # get bottom/top Y coordinates
        bot_conn_y_table = {wtype: row_info.get_conn_y(wtype)
                            for wtype in row_info.bot_conn_types}
        top_conn_y_table = {wtype: row_info.get_conn_y(wtype)
                            for wtype in row_info.top_conn_types}
        if specs.double_gate:
            mid_conn_y_table = {wtype: row_info.get_conn_y(wtype)
                                for wtype in row_info.mid_conn_types}
        else:
            mid_conn_y_table = {}

        if specs.flip:
            bext_info = row_info.top_ext_info
            text_info = row_info.bot_ext_info
        else:
            bext_info = row_info.bot_ext_info
            text_info = row_info.top_ext_info

        info_list.append(RowPlaceSpecs(specs, row_info, bot_conn_y_table, top_conn_y_table,
                                       bext_info, text_info, mid_conn_y_table=mid_conn_y_table))

    return info_list


def _place_mirror(tech_cls: MOSTech, ext_info: RowExtInfo, ycur: int, ignore_vm_sp_le: bool = False
                  ) -> Tuple[int, int]:
    """Extend the current extention such that it can be mirrored"""
    blk_h_pitch = tech_cls.blk_h_pitch

    mirror_ext_w_info: ExtWidthInfo = tech_cls.get_ext_width_info(ext_info, ext_info,
                                                    ignore_vm_sp_le=ignore_vm_sp_le)

    ext_w_cur = ycur // blk_h_pitch
    ext_w_tot = mirror_ext_w_info.get_next_width(2 * ext_w_cur, even=True)
    ext_w_ans = ext_w_tot // 2
    ycur += (ext_w_ans - ext_w_cur) * blk_h_pitch
    return ycur, ext_w_ans


def _place_rows(tr_manager: TrackManager, tech_cls: MOSTech, pspecs_list: Sequence[RowPlaceSpecs],
                tot_height_min: int, tot_height_pitch: int, bot_mirror: bool, top_mirror: bool,
                hm_shift: Union[int, HalfInt] = 0, max_iter: int = 100
                ) -> Tuple[ImmutableList[RowPlaceInfo], List[Tuple[WireGraph, WireGraph]]]:
    """Used by place_rows_compact to place rows after getting RowPlaceSpecs for all rows.

    Parameters
    ----------
    tr_manager : TrackManager
        the track manager of the MOSBase.
    tech_cls : MOSTech
        the technology specific class for drawing layout
    pspecs_list : Sequence[RowPlaceSpecs]
        list of RowPlaceSpecs. See _get_row_place_specs for construction details
    tot_height_min: int
        Minimum cell height, set by e.g. desired heigher metal tracks.
    tot_height_pitch: int
        Quantize the cell height to this dimension. Typically a tile height.
    bot_mirror : bool
        True to satisfy mirror placement constraint on the bottom edge.
    top_mirror : bool
        True to satisfy mirror placement constraint on the top edge.
    hm_shift: Union[int, HalfInt]
        Optional vertical track shift for the bottom (0th) row.
    max_iter:
        Maximum number of iterations to try to fix the cell bottom - active bottom extension
            to fit the bottom tracks.
    """
    grid = tr_manager.grid
    blk_h_pitch = tech_cls.blk_h_pitch
    conn_layer = tech_cls.conn_layer
    hm_layer = conn_layer + 1
    conn_sp_le = grid.get_line_end_space(conn_layer, 1)

    num_rows = len(pspecs_list)
    prev_ext_info: Optional[RowExtInfo] = None
    prev_ext_h = 0
    ytop_prev = 0
    ytop_conn_prev = COORD_MIN
    pinfo_list = []
    prev_wg: Optional[WireGraph] = None
    row_graph_list: List[Tuple[WireGraph, WireGraph]] = []

    for idx, pspecs in enumerate(pspecs_list):
        bot_ext_info = pspecs.bot_ext_info
        top_ext_info = pspecs.top_ext_info
        bot_conn_y_table = pspecs.bot_conn_y_table
        mid_conn_y_table = pspecs.mid_conn_y_table
        top_conn_y_table = pspecs.top_conn_y_table
        row_specs = pspecs.row_specs
        ignore_bot_vm_sp_le = row_specs.ignore_bot_vm_sp_le
        ignore_top_vm_sp_le = row_specs.ignore_top_vm_sp_le

        row_info = pspecs.row_info
        blk_h = row_info.height

        bot_wg: WireGraph = WireGraph.make_wire_graph(hm_layer, tr_manager, row_specs.bot_wires)
        mid_wg: WireGraph = WireGraph.make_wire_graph(hm_layer, tr_manager, row_specs.mid_wires)
        top_wg: WireGraph = WireGraph.make_wire_graph(hm_layer, tr_manager, row_specs.top_wires)
        row_graph_list.append((bot_wg, top_wg))

        if idx == 0:
            # first row, place bottom wires using mirror/shift constraints
            bot_wg.place_compact(hm_layer, tr_manager, bot_mirror=bot_mirror, shift=hm_shift)
        else:
            # subsequent rows, place bottom wires using previous wire graph
            bot_wg.place_compact(hm_layer, tr_manager, prev_wg=prev_wg)

        bnd_table: Dict[str, List[Tuple[HalfInt, int]]] = bot_wg.get_placement_bounds(hm_layer, grid)

        # find Y coordinate of MOS row
        ycur = ytop_prev
        for conn_name, (_, (tr1, w1)) in bnd_table.items():
            # compute ycur so that we can connect to top bottom wire
            vm_vext = grid.get_via_extensions(Direction.LOWER, conn_layer, 1, w1)[0]
            yw = grid.get_wire_bounds(hm_layer, tr1, width=w1)[1]
            ycur = max(ycur, yw + vm_vext - bot_conn_y_table[MOSWireType[conn_name]][1])

        ycur = -(-ycur // blk_h_pitch) * blk_h_pitch
        # make sure extension region is legal
        if idx == 0:
            if bot_mirror:
                ext_w_info = tech_cls.get_ext_width_info(bot_ext_info, bot_ext_info,
                                                         ignore_vm_sp_le=ignore_bot_vm_sp_le)
                ycur, _ = _place_mirror(tech_cls, bot_ext_info, ycur,
                                        ignore_vm_sp_le=ignore_bot_vm_sp_le)
            else:
                ext_w_info = ExtWidthInfo([], 0)
        else:
            ext_w_info = tech_cls.get_ext_width_info(prev_ext_info, bot_ext_info,
                                                     ignore_vm_sp_le=ignore_bot_vm_sp_le)
            cur_bot_ext_h = (ycur - ytop_prev) // blk_h_pitch
            # make sure extension height is valid
            ext_h = ext_w_info.get_next_width(prev_ext_h + cur_bot_ext_h)
            cur_bot_ext_h = ext_h - prev_ext_h
            ycur = ytop_prev + blk_h_pitch * cur_bot_ext_h

        # align bottom wires with placement constraints
        pcons = {wtype.name: ycur + conn_y[1] for wtype, conn_y in bot_conn_y_table.items()}
        bot_wg.align_wires(hm_layer, tr_manager, ytop_prev, ycur + blk_h,
                           top_pcons=PlaceFun(conn_layer, grid, pcons, RoundMode.LESS_EQ))
        ytop_conn_prev_shared = bot_wg.get_shared_conn_y(hm_layer, grid, False)
        ytop_conn_prev = max(ytop_conn_prev, ytop_conn_prev_shared)

        if ytop_conn_prev != COORD_MIN and not ignore_bot_vm_sp_le:
            dy = _calc_vm_dy(grid, row_info, bot_wg, bot_conn_y_table, conn_layer, ycur,
                             ytop_conn_prev, conn_sp_le)
            cnt = 0
            while dy > 0 and cnt < max_iter:
                ycur = -(-(ycur + dy) // blk_h_pitch) * blk_h_pitch
                # need to fix extension height again
                cur_bot_ext_h = (ycur - ytop_prev) // blk_h_pitch
                ext_h = ext_w_info.get_next_width(prev_ext_h + cur_bot_ext_h)
                cur_bot_ext_h = ext_h - prev_ext_h
                ycur = ytop_prev + blk_h_pitch * cur_bot_ext_h
                # re-align bottom wires with placement constraints
                pcons = {wtype.name: ycur + conn_y[1] for wtype, conn_y in bot_conn_y_table.items()}
                bot_wg.align_wires(hm_layer, tr_manager, ytop_prev, ycur + blk_h,
                                   top_pcons=PlaceFun(conn_layer, grid, pcons, RoundMode.LESS_EQ))

                # try again
                dy = _calc_vm_dy(grid, row_info, bot_wg, bot_conn_y_table, conn_layer, ycur,
                                 ytop_conn_prev, conn_sp_le)
                cnt += 1
            if dy > 0:
                raise ValueError('maximum iteration reached, still cannot resolve line-end spacing')

        # get bottom conn_layer Y coordinates
        conn_y_bnds_bot = [COORD_MAX, COORD_MIN]
        for wtype, conn_y in bot_conn_y_table.items():
            if wtype.is_physical:
                conn_y_bnds_bot[0] = min(conn_y_bnds_bot[0], ycur + conn_y[0])
                conn_y_bnds_bot[1] = max(conn_y_bnds_bot[1], ycur + conn_y[1])
        bnd_table = bot_wg.get_placement_bounds(hm_layer, grid)
        conn_y_bnds_bot[0] = _update_y_conn(grid, row_info, conn_layer, ycur, bnd_table,
                                            conn_y_bnds_bot[0], False)
        conn_y_bnds_bot[1] = _update_y_conn(grid, row_info, conn_layer, ycur, bnd_table,
                                            conn_y_bnds_bot[1], True)
        if bot_wg:
            prev_wg = bot_wg

        is_top_row = (idx == num_rows - 1)
        if row_specs.double_gate:
            # place middle wires
            conn_y_bnds_mid = [COORD_MAX, COORD_MIN]
            pcons = {}
            for wtype, conn_y in mid_conn_y_table.items():
                pcons[wtype.name] = ycur + conn_y[0]
                if wtype.is_physical:
                    conn_y_bnds_mid[0] = min(conn_y_bnds_mid[0], ycur + conn_y[0])
                    conn_y_bnds_mid[1] = max(conn_y_bnds_mid[1], ycur + conn_y[1])

            if mid_wg:
                mid_wg.place_compact(hm_layer, tr_manager,
                                    pcons=PlaceFun(conn_layer, grid, pcons, RoundMode.GREATER_EQ),
                                    prev_wg=prev_wg, #top_mirror=top_mirror and is_top_row,)
                                    ytop_conn=max(conn_y_bnds_bot[1], conn_y_bnds_mid[1]))
                prev_wg = mid_wg
            
            # place top wires above the middle wires
            conn_y_bnds_top = [COORD_MAX, COORD_MIN]
            pcons = {}
            for wtype, conn_y in top_conn_y_table.items():
                pcons[wtype.name] = ycur + conn_y[0]
                if wtype.is_physical:
                    conn_y_bnds_top[0] = min(conn_y_bnds_top[0], ycur + conn_y[0])
                    conn_y_bnds_top[1] = max(conn_y_bnds_top[1], ycur + conn_y[1])

            if top_wg:
                top_wg.place_compact(hm_layer, tr_manager,
                                    pcons=PlaceFun(conn_layer, grid, pcons, RoundMode.GREATER_EQ),
                                    prev_wg=prev_wg, #top_mirror=top_mirror and is_top_row,
                                    ytop_conn=max(conn_y_bnds_bot[1], conn_y_bnds_top[1]))
                prev_wg = top_wg
            
            bnd_table = top_wg.get_placement_bounds(hm_layer, grid)
            conn_y_bnds_top[0] = _update_y_conn(grid, row_info, conn_layer, ycur, bnd_table,
                                                conn_y_bnds_top[0], False)
            conn_y_bnds_top[1] = _update_y_conn(grid, row_info, conn_layer, ycur, bnd_table,
                                                conn_y_bnds_top[1], True)
        else:
            # place top wires
            
            conn_y_bnds_top = [COORD_MAX, COORD_MIN]
            pcons = {}
            for wtype, conn_y in top_conn_y_table.items():
                pcons[wtype.name] = ycur + conn_y[0]
                if wtype.is_physical:
                    conn_y_bnds_top[0] = min(conn_y_bnds_top[0], ycur + conn_y[0])
                    conn_y_bnds_top[1] = max(conn_y_bnds_top[1], ycur + conn_y[1])

            if top_wg:
                top_wg.place_compact(hm_layer, tr_manager,
                                    pcons=PlaceFun(conn_layer, grid, pcons, RoundMode.GREATER_EQ),
                                    prev_wg=prev_wg, top_mirror=top_mirror and is_top_row,
                                    ytop_conn=max(conn_y_bnds_bot[1], conn_y_bnds_top[1]))
                if row_info.row_type.is_substrate:
                    top_wg.align_wires(hm_layer, tr_manager, ytop_prev, ycur + blk_h, top_pcons=None)

            # get ytop_conn
            bnd_table = top_wg.get_placement_bounds(hm_layer, grid)
            conn_y_bnds_top[0] = _update_y_conn(grid, row_info, conn_layer, ycur, bnd_table,
                                                conn_y_bnds_top[0], False)
            conn_y_bnds_top[1] = _update_y_conn(grid, row_info, conn_layer, ycur, bnd_table,
                                                conn_y_bnds_top[1], True)

        # compute ytop
        ytop_blk = ycur + blk_h
        ytop = max(ytop_blk, top_wg.upper)
        row_h_cur = -(-(ytop - ytop_prev) // blk_h_pitch) * blk_h_pitch
        ytop = ytop_prev + row_h_cur
        if is_top_row:
            # last row
            # update ytop
            ytop = max(ytop, tot_height_min)
            ytop = -(-ytop // tot_height_pitch) * tot_height_pitch
            # fix extension constraint
            if top_mirror:
                pass_mirror = False
                while not pass_mirror:
                    ytop_delta = ytop - ytop_blk
                    ytop_delta2, cur_top_ext_h = _place_mirror(tech_cls, top_ext_info, ytop_delta,
                                                               ignore_vm_sp_le=ignore_top_vm_sp_le)
                    if ytop_delta2 != ytop - ytop_blk:
                        # need more room for extension region on top, make the row taller
                        ytop += ytop_delta2 - ytop_delta
                        ytop = -(-ytop // tot_height_pitch) * tot_height_pitch
                    else:
                        pass_mirror = True
        cur_top_ext_h = (ytop - ytop_blk) // blk_h_pitch

        # update upper coordinate for top wire graph
        top_wg.set_upper(hm_layer, tr_manager, ytop)
        ybot_conn = min(conn_y_bnds_bot[0], conn_y_bnds_top[0])
        ytop_conn = max(conn_y_bnds_bot[1], conn_y_bnds_top[1])
        pinfo_list.append(RowPlaceInfo(row_info, bot_wg.get_wire_lookup(), top_wg.get_wire_lookup(),
                                       ytop_prev, ytop, ycur, ytop_blk, (ybot_conn, ytop_conn),
                                       mid_wires=mid_wg.get_wire_lookup()))

        # update previous row information
        ytop_prev = ytop
        ytop_conn_prev = ytop_conn
        prev_ext_info = top_ext_info
        prev_ext_h = cur_top_ext_h
        if top_wg:
            prev_wg = top_wg

    return ImmutableList(pinfo_list), row_graph_list


def _calc_vm_dy(grid: RoutingGrid, row_info: MOSRowInfo, bot_wg: WireGraph,
                bot_conn_y_table: Mapping[MOSWireType, Tuple[int, int]],
                vm_layer: int, ycur: int, ytop_conn_prev: int, conn_sp_le: int) -> int:
    hm_layer = vm_layer + 1
    ybot_conn = COORD_MAX
    bnd_table = bot_wg.get_placement_bounds(hm_layer, grid, inc_shared=False)
    for conn_name, ((tr0, w0), _) in bnd_table.items():
        vm_vext = grid.get_via_extensions(Direction.LOWER, vm_layer, 1, w0)[0]
        yw = grid.get_wire_bounds(hm_layer, tr0, width=w0)[0]
        yb_cur = yw - vm_vext
        for conn_yb, conn_yt in row_info.get_all_conn_y(MOSWireType[conn_name]):
            conn_yt_cur = ycur + conn_yt
            wlen = grid.get_next_length(vm_layer, 1, conn_yt_cur - yb_cur)
            ybot_conn = min(ybot_conn, conn_yt_cur - wlen, ycur + conn_yb)

    for wtype, conn_y in bot_conn_y_table.items():
        if wtype.is_physical:
            ybot_conn = min(ybot_conn, ycur + conn_y[0])

    return ytop_conn_prev + conn_sp_le - ybot_conn


def _update_y_conn(grid: RoutingGrid, row_info: MOSRowInfo, conn_layer: int, ycur: int,
                   bnd_table: Mapping[str, List[Tuple[HalfInt, int]]], yval: int,
                   is_top: bool) -> int:
    hm_layer = conn_layer + 1
    sign = 2 * is_top - 1
    fun = max if is_top else min
    for conn_name, wire_info in bnd_table.items():
        tr_idx, tr_w = wire_info[is_top]
        vm_vext = grid.get_via_extensions(Direction.LOWER, conn_layer, 1, tr_w)[0]
        y_wire = grid.get_wire_bounds(hm_layer, tr_idx, width=tr_w)[is_top]
        # make sure legal vm layer length is met for all possible connections
        y_cur = y_wire + sign * vm_vext
        for conn_y in row_info.get_all_conn_y(MOSWireType[conn_name]):
            conn_y_cur = ycur + conn_y[not is_top]
            wlen = grid.get_next_length(conn_layer, 1, abs(y_cur - conn_y_cur))
            yval = fun(yval, conn_y_cur + sign * wlen)

    return yval
