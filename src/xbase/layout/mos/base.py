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

from __future__ import annotations

from typing import Any, Optional, Tuple, List, Dict, Union

import abc
from dataclasses import dataclass

from pybag.core import BBox, Transform
from pybag.enum import Orientation, RoundMode, Direction, Orient2D, MinLenMode

from bag.util.math import HalfInt
from bag.util.immutable import Param
from bag.layout.core import PyLayInstance
from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.routing.base import TrackManager, TrackID, WireArray

from ..enum import MOSAbutMode, MOSWireType, SubPortMode

from .data import MOSRowInfo, MOSPorts, MOSEdgeInfo, BlkExtInfo, MOSAbutInfo, NAND2Ports
from .tech import MOSTech
from .util import MOSUsedArray
from .placement.data import (
    MOSBasePlaceInfo, MOSArrayPlaceInfo, TilePattern, TilePatternElement, TileInfoTable
)
from .primitives import MOSConn, MOSTap, MOSAbut


@dataclass
class SupplyColumnInfo:
    ncol: int
    top_layer: int
    tr_info: List[Tuple[int, HalfInt]]


class MOSBase(TemplateBase, abc.ABC):
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        # noinspection PyTypeChecker
        self._arr_info: MOSArrayPlaceInfo = None
        # noinspection PyTypeChecker
        self._tinfo_table: TileInfoTable = None
        # noinspection PyTypeChecker
        self._used_arr: MOSUsedArray = None

    @property
    def used_array(self) -> MOSUsedArray:
        """MOSUsedArray: the transistor usage map object."""
        return self._used_arr

    @property
    def num_cols(self) -> int:
        """int: number of transistors."""
        return self._used_arr.num_cols

    @property
    def num_rows(self) -> int:
        """int: Total number of transistor rows."""
        return self._used_arr.num_flat_rows

    @property
    def num_tile_rows(self) -> int:
        """int: Number of tiles"""
        return self._used_arr.num_tiles

    @property
    def tile_size(self) -> Tuple[int, int]:
        """Tuple[int, int]: Tuple of (num_cols, num_tiles)."""
        used_array = self._used_arr
        return used_array.num_cols, used_array.num_tiles

    @property
    def place_info(self) -> MOSBasePlaceInfo:
        """MOSBasePlaceInfo: The tile 0 layout information object."""
        return self._used_arr.get_tile_info(0)[0]

    @property
    def draw_base_info(self) -> Tuple[TilePatternElement, TileInfoTable]:
        return self._used_arr.tile_pattern_element, self._tinfo_table

    @property
    def flipped(self) -> bool:
        """bool: True if tile 0 is flipped."""
        return self._used_arr.get_tile_info(0)[2]

    @property
    def arr_info(self) -> MOSArrayPlaceInfo:
        return self._arr_info

    @property
    def tile_table(self) -> TileInfoTable:
        return self._tinfo_table

    @property
    def tech_cls(self) -> MOSTech:
        """MOSTech: the primitive technology information object."""
        return self._arr_info.tech_cls

    @property
    def top_layer(self) -> int:
        """int: the ID of transistor port layer."""
        return self._arr_info.top_layer

    @property
    def conn_layer(self) -> int:
        """int: the ID of transistor port layer."""
        return self._arr_info.conn_layer

    @property
    def tr_manager(self) -> TrackManager:
        """TrackManager: the track manager object."""
        return self._arr_info.tr_manager

    @property
    def sd_pitch(self) -> int:
        """int: the source-drain pitch."""
        return self._arr_info.sd_pitch

    @property
    def min_sep_col(self) -> int:
        """int: column separation needed between transistors."""
        return self.tech_cls.min_sep_col

    @property
    def sub_sep_col(self) -> int:
        """int: column separation needed between transistor/substrate and substrate/substrate.

        This is guaranteed to be even.
        """
        return self.tech_cls.sub_sep_col

    @property
    def min_sub_col(self) -> int:
        """int: Minimum number of fingers for substrate contact."""
        return self.tech_cls.min_sub_col

    @property
    def can_short_adj_tracks(self) -> bool:
        """bool: True if you can short adjacent transistor ports using hm_layer."""
        return self.tech_cls.can_short_adj_tracks(self.conn_layer)

    def draw_base(self, obj: Union[MOSBasePlaceInfo,
                                   TilePatternElement,
                                   Tuple[Union[MOSBasePlaceInfo, TilePattern,
                                               TilePatternElement], TileInfoTable]],
                  flip_tile: bool = False, mirror: bool = True) -> None:
        if isinstance(obj, tuple):
            tile_info, tinfo_table = obj
        else:
            tile_info = obj
            tinfo_table = TileInfoTable(obj.arr_info, {obj.name: obj})

        self._tinfo_table = tinfo_table
        self._arr_info = tile_info.arr_info
        self.grid = self._arr_info.tr_manager.grid
        self._used_arr = MOSUsedArray(tile_info, mirror=mirror, flip=flip_tile)

    def get_tile_pattern_element(self, mult: int = 1, mirror: bool = True, flip: bool = False
                                 ) -> TilePatternElement:
        if not self.finalized:
            raise ValueError('This method only works on finalized instances.')
        return self._used_arr.get_tile_pattern_element(mult, mirror, flip)

    def get_tile_subpattern(self, start_idx: int, stop_idx: int, mult: int = 1, mirror: bool = True,
                            flip: bool = False) -> TilePatternElement:
        return self._used_arr.get_tile_subpattern(start_idx, stop_idx, mult, mirror, flip)

    def get_draw_base_sub_pattern(self, start_idx: int, stop_idx: int, mirror: bool = True,
                                  flip: bool = False) -> Tuple[TilePatternElement, TileInfoTable]:
        tpe = self.get_tile_subpattern(start_idx, stop_idx, mirror=mirror, flip=flip)
        return tpe, self._tinfo_table

    def get_hm_sp_le_sep_col(self, ntr: int = 1) -> int:
        """Get number of columns needed to satisfy hm_layer line-end spacing.

        This is a convenient wrapper around RoutingGrid.get_line_end_sep_tracks().  See
        documentation for that method for more details.
        """
        hm_layer = self.conn_layer + 1
        return self.grid.get_line_end_sep_tracks(Direction.UPPER, hm_layer, ntr, 1,
                                                 half_space=False).dbl_value // 2

    def get_tile_info(self, tile_idx: int) -> Tuple[MOSBasePlaceInfo, int, bool]:
        tile_idx = self._tile_check(tile_idx)
        return self._used_arr.get_tile_info(tile_idx)

    def get_tile_pinfo(self, tile_idx: int) -> MOSBasePlaceInfo:
        tile_idx = self._tile_check(tile_idx)
        return self._used_arr.get_tile_pinfo(tile_idx)

    def get_num_wires(self, row_idx: int, wire_type: Union[MOSWireType, bool], wire_name: str,
                      *, tile_idx: int = 0) -> int:
        return self._used_arr.get_num_wires(row_idx, wire_type, wire_name, tile_idx=tile_idx)

    def get_track_info(self, row_idx: int, wire_type: Union[MOSWireType, bool], wire_name: str,
                       wire_idx: int = 0, *, tile_idx: int = 0) -> Tuple[HalfInt, int]:
        tile_idx = self._tile_check(tile_idx)
        return self._used_arr.get_track_info(row_idx, wire_type, wire_name,
                                             wire_idx=wire_idx, tile_idx=tile_idx)

    def get_track_index(self, row_idx: int, wire_type: Union[MOSWireType, bool], wire_name: str,
                        wire_idx: int = 0, *, tile_idx: int = 0) -> HalfInt:
        tile_idx = self._tile_check(tile_idx)
        return self._used_arr.get_track_index(row_idx, wire_type, wire_name,
                                              wire_idx=wire_idx, tile_idx=tile_idx)

    def get_track_id(self, row_idx: int, wire_type: Union[MOSWireType, bool], wire_name: str,
                     wire_idx: int = 0, *, tile_idx: int = 0) -> TrackID:
        """Get the TrackID of the specified hm_layer routing track.

        Parameters
        ----------
        row_idx : int
            the transistor row index.
        wire_type : Union[MOSWireType, bool]
            wire type used to determined where to look for the specified wire.  In an unflipped
            row, gate type means search in the bottom wire group, and drain/source type
            means search in the top wire group.

            If a bool is given, then True means the top wires, False, means the bottom wires.
        wire_name : str
            the wire name.
        wire_idx : int
            the wire index.
        tile_idx : int
            the tile index.

        Returns
        -------
        track_id : TrackID
            the TrackID representing the specified hm_layer routing track.
        """
        tile_idx = self._tile_check(tile_idx)
        return self._used_arr.get_track_id(row_idx, wire_type, wire_name,
                                           wire_idx=wire_idx, tile_idx=tile_idx)

    def get_hm_track_info(self, hm_layer: int, wire_name: str, wire_idx: int = 0, *,
                          tile_idx: int = 0) -> Tuple[HalfInt, int]:
        tile_idx = self._tile_check(tile_idx)
        return self._used_arr.get_hm_track_info(hm_layer, wire_name, wire_idx=wire_idx,
                                                tile_idx=tile_idx)

    def get_hm_track_id(self, hm_layer: int, wire_name: str, wire_idx: int = 0, *,
                        tile_idx: int = 0) -> TrackID:
        tile_idx = self._tile_check(tile_idx)
        return self._used_arr.get_hm_track_id(hm_layer, wire_name, wire_idx=wire_idx,
                                              tile_idx=tile_idx)

    def get_hm_track_index(self, hm_layer: int, wire_name: str, wire_idx: int = 0, *,
                           tile_idx: int = 0) -> HalfInt:
        tile_idx = self._tile_check(tile_idx)
        return self._used_arr.get_hm_track_index(hm_layer, wire_name, wire_idx=wire_idx,
                                                 tile_idx=tile_idx)

    def get_row_info(self, row_idx: int, tile_idx: int = 0) -> MOSRowInfo:
        pinfo = self.get_tile_pinfo(tile_idx)
        row_idx = _row_check(pinfo, row_idx)
        return pinfo.get_row_place_info(row_idx).row_info

    def set_mos_size(self, num_cols: int = 0, num_tiles: int = 0) -> None:
        if not self.size_defined:
            ainfo = self._arr_info
            used_arr = self._used_arr

            if num_cols > 0:
                used_arr.num_cols = num_cols
            if num_tiles > 0:
                used_arr.set_num_tiles(num_tiles)

            width = used_arr.num_cols * ainfo.sd_pitch
            height = used_arr.height
            self.set_size_from_bound_box(ainfo.top_layer, BBox(0, 0, width, height))
        else:
            raise ValueError('Cannot change tile_size once it is set.')

    def add_tile(self, master: MOSBase, tile_idx: int, col_idx: int, *,
                 flip_lr: bool = False, commit: bool = True) -> PyLayInstance:
        tile_idx = self._tile_check(tile_idx)

        abut_list = []
        try:
            self._used_arr.add_tiles(tile_idx, col_idx, master.used_array, flip_lr, abut_list)
        except ValueError as err:
            msg = (f'Error adding {master.get_layout_basename()} to tile '
                   f'{tile_idx}, column {col_idx}, flip_lr = {flip_lr}')
            raise ValueError(msg) from err

        pinfo, y0, flip_tile = self.get_tile_info(tile_idx)

        self._handle_abutment(abut_list)
        if flip_tile ^ master.flipped:
            orient = Orientation.MX
            y0 += pinfo.height
        else:
            orient = Orientation.R0

        if flip_lr:
            orient = orient.flip_lr()

        x0 = col_idx * self.sd_pitch
        return self.add_instance(master, inst_name=f'XT{tile_idx}C{col_idx}',
                                 xform=Transform(x0, y0, orient), commit=commit)

    def add_mos(self, row_idx: int, col_idx: int, seg: int, *, tile_idx: int = 0, w: int = 0,
                g_on_s: bool = False, stack: int = 1, flip_lr: bool = False,
                **kwargs: Any) -> MOSPorts:
        if seg <= 0:
            raise ValueError('Cannot draw non-positive segments.')

        pinfo = self.get_tile_pinfo(tile_idx)
        row_idx = _row_check(pinfo, row_idx)
        rpinfo = pinfo.get_row_place_info(row_idx)
        row_info = rpinfo.row_info
        row_type = row_info.row_type
        w_max = row_info.width

        if row_type.is_substrate:
            raise ValueError('Cannot draw transistors in substrate row.')
        if w == 0:
            w = w_max
        elif w > w_max:
            raise ValueError(f'Cannot create transistor with w > {w_max}')

        conn_layer = pinfo.conn_layer

        fg = seg * stack

        # create connection master
        params = dict(
            row_info=row_info,
            conn_layer=conn_layer,
            seg=seg,
            w=w,
            stack=stack,
            g_on_s=g_on_s,
            options=kwargs,
            arr_options=self.arr_info.arr_options,
        )
        master = self.new_template(MOSConn, params=params)

        abut_list = []
        y0, orient = self.register_device(self._used_arr, tile_idx, row_idx,
                                          col_idx, fg, flip_lr,
                                          master.left_info, master.right_info,
                                          master.top_info, master.bottom_info, abut_list)
        self._handle_abutment(abut_list)

        # compute instance transform
        x0 = col_idx * self.sd_pitch
        inst = self.add_instance(master, inst_name=f'XT{tile_idx}R{row_idx}C{col_idx}',
                                 xform=Transform(x0, y0, orient))

        # construct port object
        m_pin = inst.get_pin('m') if inst.has_port('m') else None
        return MOSPorts(inst.get_pin('g'), inst.get_pin('d'), inst.get_pin('s'),
                        master.shorted_ports, m=m_pin)

    def add_nand2(self, row_idx: int, col_idx: int, seg: int, *, tile_idx: int = 0, w: int = 0,
                  stack: int = 1, flip_lr: bool = False, export_mid: bool = False,
                  other: bool = False) -> NAND2Ports:
        if export_mid and other:
            raise ValueError('No mid to export for complementary NAND2 devices')

        stack_mos = (2 - bool(export_mid or other)) * stack
        seg_mos = (1 + bool(other)) * seg
        g_on_s = bool(stack & 1)
        ports = self.add_mos(row_idx, col_idx, seg_mos, tile_idx=tile_idx, w=w, stack=stack_mos,
                             flip_lr=flip_lr, g_on_s=g_on_s, sep_g=True)
        if export_mid:
            m = ports.d
            s = ports.s[0::2]
            d = ports.s[1::2]
        else:
            m = None
            s = ports.s
            d = ports.d

        g0 = []
        g1 = []
        modulus = 2 * stack
        r_min = (stack + 1) // 2
        r_max = modulus - r_min - ((stack & 1) ^ 1)
        for idx, warr in enumerate(ports.g.warr_iter()):
            r_cur = idx % modulus
            if r_min <= r_cur <= r_max:
                g1.append(warr)
            else:
                g0.append(warr)

        return NAND2Ports(g0, g1, d, s, m)

    def get_supply_column_info(self, top_layer: int, tile_idx: int = 0) -> SupplyColumnInfo:
        grid = self.grid
        ainfo = self._arr_info
        tr_manager = ainfo.tr_manager

        pinfo = self.get_tile_pinfo(tile_idx)
        same_col_sub: bool = pinfo.tile_options.get('same_col_sub', False)
        if same_col_sub:
            raise ValueError('add_supply_column() currently does not support same_col_sub = True')
        if not pinfo.is_complementary:
            raise ValueError('Currently only works on complementary tiles.')

        if top_layer <= self.conn_layer:
            raise ValueError(f'top_layer must be at least {self.conn_layer + 1}')
        if grid.get_direction(top_layer) == Orient2D.x:
            top_vm_layer = top_layer - 1
        else:
            top_vm_layer = top_layer

        # get total number of columns
        num_col = self.get_tap_ncol() + self.sub_sep_col
        tr_info_list = []
        for vm_lay in range(self.conn_layer + 2, top_vm_layer + 1, 2):
            blk_ncol = ainfo.get_block_ncol(vm_lay)
            tr_w = tr_manager.get_width(vm_lay, 'sup')
            tr_sep = tr_manager.get_sep(vm_lay, ('sup', 'sup'), half_space=False)
            ntr = 3 * tr_sep
            cur_ncol = -(-ainfo.get_column_span(vm_lay, ntr) // blk_ncol) * blk_ncol
            num_col = max(num_col, cur_ncol)
            tr_info_list.append((tr_w, tr_sep))

        # make sure we can draw substrate contact
        num_col += (num_col & 1)
        return SupplyColumnInfo(ncol=num_col, top_layer=top_layer, tr_info=tr_info_list)

    def add_supply_column(self, sup_info: SupplyColumnInfo, col_idx: int,
                          vdd_table: Dict[int, List[WireArray]],
                          vss_table: Dict[int, List[WireArray]],
                          ridx_p: int = -1, ridx_n: int = 0, tile_idx: int = 0,
                          flip_lr: bool = False, extend_vdd: bool = True,
                          extend_vss: bool = True, min_len_mode: MinLenMode = MinLenMode.NONE,
                          **kwargs: Any) -> None:
        grid = self.grid
        ainfo = self._arr_info
        tr_manager = ainfo.tr_manager
        conn_layer = self.conn_layer

        sub_sep = self.sub_sep_col
        sub_sep2 = -(-sub_sep // 2)

        ncol = sup_info.ncol
        seg_dbl = ncol - sub_sep * 2
        seg = seg_dbl // 2
        vdd_list = []
        vss_list = []
        if flip_lr:
            xh = ainfo.col_to_coord(col_idx)
            xl = ainfo.col_to_coord(col_idx - ncol)
            self.add_tap(col_idx - sub_sep2, vdd_list, vss_list, seg=seg,
                         tile_idx=tile_idx, flip_lr=True, **kwargs)
        else:
            xl = ainfo.col_to_coord(col_idx)
            xh = ainfo.col_to_coord(col_idx + ncol)
            self.add_tap(col_idx + sub_sep2, vdd_list, vss_list, seg=seg,
                         tile_idx=tile_idx, flip_lr=False, **kwargs)

        vss_tid = self.get_track_id(ridx_n, False, 'sup', wire_idx=0, tile_idx=tile_idx)
        vdd_tid = self.get_track_id(ridx_p, True, 'sup', wire_idx=0, tile_idx=tile_idx)
        vss = self.connect_to_tracks(vss_list, vss_tid, track_lower=xl, track_upper=xh)
        vdd = self.connect_to_tracks(vdd_list, vdd_tid, track_lower=xl, track_upper=xh)
        hm_layer = vss_tid.layer_id
        vss_y = grid.track_to_coord(hm_layer, vss_tid.base_index)
        vdd_y = grid.track_to_coord(hm_layer, vdd_tid.base_index)
        yl = min(vss_y, vdd_y)
        yh = max(vss_y, vdd_y)
        vdd_table[conn_layer].extend(vdd_list)
        vss_table[conn_layer].extend(vss_list)
        vdd_table[hm_layer].append(vdd)
        vss_table[hm_layer].append(vss)
        xmid = (xl + xh) // 2
        for lay_delta in range(2, sup_info.top_layer - conn_layer + 1):
            cur_layer = conn_layer + lay_delta
            if lay_delta % 2 == 0:
                # vertical layer
                tr_w, tr_d = sup_info.tr_info[lay_delta // 2 - 1]
                tr_d2 = tr_d / 2
                vss_tidx = grid.coord_to_track(cur_layer, xmid, mode=RoundMode.LESS_EQ) - tr_d2
                vdd_tidx = grid.coord_to_track(cur_layer, xmid, mode=RoundMode.GREATER_EQ) + tr_d2
                if flip_lr:
                    tmp = vdd_tidx
                    vdd_tidx = vss_tidx
                    vss_tidx = tmp
                if extend_vdd:
                    vdd_tl = yl
                    vdd_th = yh
                    vdd_mlm = MinLenMode.NONE
                else:
                    vdd_tl = vdd_th = None
                    vdd_mlm = min_len_mode
                if extend_vss:
                    vss_tl = yl
                    vss_th = yh
                    vss_mlm = MinLenMode.NONE
                else:
                    vss_tl = vss_th = None
                    vss_mlm = min_len_mode
            else:
                tr_w = tr_manager.get_width(cur_layer, 'sup')
                vss_tidx = grid.coord_to_track(cur_layer, vss_y, mode=RoundMode.GREATER_EQ)
                vdd_tidx = grid.coord_to_track(cur_layer, vdd_y, mode=RoundMode.LESS_EQ)
                vdd_tl = vss_tl = xl
                vdd_th = vss_th = xh
                vdd_mlm = vss_mlm = MinLenMode.NONE

            vss_tid = TrackID(cur_layer, vss_tidx, width=tr_w)
            vdd_tid = TrackID(cur_layer, vdd_tidx, width=tr_w)
            vss = self.connect_to_tracks(vss, vss_tid, track_lower=vss_tl, track_upper=vss_th,
                                         min_len_mode=vss_mlm)
            vdd = self.connect_to_tracks(vdd, vdd_tid, track_lower=vdd_tl, track_upper=vdd_th,
                                         min_len_mode=vdd_mlm)
            vdd_table[cur_layer].append(vdd)
            vss_table[cur_layer].append(vss)

    def add_tap(self, col_idx: int, vdd_list: List[WireArray], vss_list: List[WireArray], *,
                seg: int = 0, tile_idx: int = 0, flip_lr: bool = False, **kwargs: Any) -> int:
        """Add substrate contacts in all transistor rows in the given tile.

        This method will automatically add substrate contact in all transistor rows at the
        given column, and avoid checker-board implant DRC error for you.

        NOTE: substrate contacts won't be drawn in substrate only rows.

        Parameters
        ----------
        col_idx : int
            the anchor column index.
        vdd_list : List[WireArray]
            all supply conn_layer ports will be appended to this list.
        vss_list : List[WireArray]
            all ground conn_layer ports will be appended to this list.
        seg : int
            number of substrate contact segments.
        tile_idx : int
            tile index.
        flip_lr : bool
            True to flip left-and-right.
        **kwargs : Any
            keyword arguments for `add_substrate_contact()` method.

        Returns
        -------
        tap_ncol : int
            number of columns used

        """
        pinfo = self.get_tile_pinfo(tile_idx)

        if seg <= 0:
            seg = self.min_sub_col

        tap_ncol = self.get_tap_ncol(seg=seg, tile_idx=tile_idx)
        if tap_ncol > seg:
            # substrate in different columns
            if flip_lr:
                ncol = col_idx
                pcol = col_idx - tap_ncol + seg
            else:
                ncol = col_idx
                pcol = col_idx + tap_ncol - seg
        else:
            ncol = pcol = col_idx

        num_rows = pinfo.num_rows

        for ridx in range(num_rows):
            row_type = pinfo.get_row_place_info(ridx).row_info.row_type
            if not row_type.is_substrate:
                if row_type.is_pwell:
                    vss_list.append(self.add_substrate_contact(ridx, ncol, tile_idx=tile_idx,
                                                               seg=seg, flip_lr=flip_lr, **kwargs))
                else:
                    vdd_list.append(self.add_substrate_contact(ridx, pcol, tile_idx=tile_idx,
                                                               seg=seg, flip_lr=flip_lr, **kwargs))

        return tap_ncol

    def get_tap_ncol(self, seg: int = 0, tile_idx: int = 0) -> int:
        pinfo = self.get_tile_pinfo(tile_idx)
        tech = self.tech_cls
        if seg <= 0:
            seg = tech.min_sub_col

        same_col_sub: bool = pinfo.tile_options.get('same_col_sub', False)
        if same_col_sub or not pinfo.is_complementary:
            return seg
        else:
            return 2 * seg + tech.sub_sep_col

    def add_substrate_contact(self, row_idx: int, col_idx: int, *, tile_idx: int = 0, seg: int = 0,
                              flip_lr: bool = False, port_mode: SubPortMode = SubPortMode.EVEN,
                              **kwargs: Any) -> WireArray:
        if seg <= 0:
            seg = self.min_sub_col

        tile_idx = self._tile_check(tile_idx)
        pinfo = self.get_tile_pinfo(tile_idx)
        row_idx = _row_check(pinfo, row_idx)
        rpinfo = pinfo.get_row_place_info(row_idx)
        row_info = rpinfo.row_info
        conn_layer = self.conn_layer

        # create connection master
        params = dict(
            row_info=row_info,
            conn_layer=conn_layer,
            seg=seg,
            options=kwargs,
            arr_options=self.arr_info.arr_options,
        )
        master = self.new_template(MOSTap, params=params)

        abut_list = []
        y0, orient = self.register_device(self._used_arr, tile_idx, row_idx,
                                          col_idx, seg, flip_lr,
                                          master.left_info, master.right_info,
                                          master.top_info, master.bottom_info, abut_list)
        self._handle_abutment(abut_list)

        # compute instance transform
        x0 = col_idx * self.sd_pitch

        inst = self.add_instance(master, inst_name=f'XT{tile_idx}R{row_idx}C{col_idx}',
                                 xform=Transform(x0, y0, orient))
        warr = inst.get_pin('sup')
        if port_mode is SubPortMode.BOTH:
            return warr
        elif port_mode is SubPortMode.EVEN:
            return warr[0::2]
        else:
            return warr[1::2]

    def _tile_check(self, tile_idx: int) -> int:
        if tile_idx < 0:
            if self.size_defined:
                tile_idx += self._used_arr.num_tiles
                if tile_idx < 0:
                    raise ValueError(f'Invalid tile row after wrapping negative: {tile_idx}')
            else:
                raise ValueError(f'Negative tile_idx used before calling set_mos_size()')

        return tile_idx

    def _handle_abutment(self, abut_list: List[MOSAbutInfo]) -> None:
        abut_mode = self.tech_cls.abut_mode
        if abut_mode is MOSAbutMode.NONE:
            return

        if abut_mode is MOSAbutMode.OVERLAY:
            used_arr = self._used_arr
            arr_options = self.arr_info.arr_options
            for info in abut_list:
                tile_idx, row_idx = used_arr.flat_row_to_tile_row(info.row_flat)
                pinfo, tile_yb, flip_tile = self.get_tile_info(tile_idx)
                row_info, y0, orient = self.get_mos_row_info(pinfo, tile_yb, flip_tile, row_idx)
                x0 = info.col * self.sd_pitch
                params = dict(row_info=row_info, edgel=info.edgel, edger=info.edger,
                              arr_options=arr_options)
                master = self.new_template(MOSAbut, params=params)
                self.add_instance(master, inst_name=f'XA{tile_idx}R{row_idx}C{info.col}',
                                  xform=Transform(x0, y0, orient))
        else:
            raise RuntimeError(f'MOSAbutMode {abut_mode} not implemented yet.')

    @classmethod
    def get_mos_row_info(cls, pinfo: MOSBasePlaceInfo, tile_yb: int, flip_tile: bool,
                         row_idx: int) -> Tuple[MOSRowInfo, int, Orientation]:
        rpinfo = pinfo.get_row_place_info(row_idx)
        row_info = rpinfo.row_info

        # get edge/ext information, orientation
        flip_ud = flip_tile != row_info.flip
        if flip_ud:
            orient = Orientation.MX
        else:
            orient = Orientation.R0

        # get Y coordinate within row
        if row_info.flip:
            y0 = rpinfo.yt_blk
        else:
            y0 = rpinfo.yb_blk
        # get absolute Y coordinate
        if flip_tile:
            y0 = tile_yb + pinfo.height - y0
        else:
            y0 += tile_yb

        return row_info, y0, orient

    @classmethod
    def register_device(cls, used_arr: MOSUsedArray, tile_idx: int,
                        row_idx: int, col_idx: int, seg: int, flip_lr: bool,
                        linfo: MOSEdgeInfo, rinfo: MOSEdgeInfo, tinfo: BlkExtInfo,
                        binfo: BlkExtInfo, abut_list: Optional[List[MOSAbutInfo]]
                        ) -> Tuple[int, Orientation]:
        # Y coordinate and orientation
        pinfo, tile_yb, flip_tile = used_arr.get_tile_info(tile_idx)
        row_info, y0, orient = cls.get_mos_row_info(pinfo, tile_yb, flip_tile, row_idx)
        if flip_lr:
            orient = orient.flip_lr()
        used_arr.add_mos(tile_idx, row_idx, col_idx, seg, flip_lr, row_info.flip,
                         linfo, rinfo, tinfo, binfo, abut_list)
        return y0, orient


def _row_check(pinfo: MOSBasePlaceInfo, row_idx: int) -> int:
    if row_idx < 0:
        row_idx += pinfo.num_rows
        if row_idx < 0:
            raise ValueError(f'Invalid row after wrapping negative: {row_idx}')

    return row_idx
