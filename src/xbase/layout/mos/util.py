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

from typing import Dict, Tuple, Optional, List, Iterable, Union

from pybag.core import PyDisjointIntervals

from bag.util.math import HalfInt
from bag.util.immutable import ImmutableList
from bag.layout.routing.base import TrackID

from ..enum import MOSWireType
from .data import MOSEdgeInfo, BlkExtInfo, MOSAbutInfo
from .placement.data import MOSBasePlaceInfo, TilePattern, TilePatternElement

MOSInfoType = Tuple[Tuple[int, int], Optional[MOSEdgeInfo], Optional[MOSEdgeInfo],
                    BlkExtInfo, BlkExtInfo]


class MOSUsedArray:
    """A data structure that keeps track of used transistors in MOSBase.

    This class is used to automatically fill empty spaces, and also get
    left/right/top/bottom layout information needed to create space blocks
    and extension rows.  Both tiles and columns are added dynamically.

    Parameters
    ----------
    obj : Union[MOSBasePlaceInfo, TilePattern]
        the repeating tile pattern.
    mirror : bool
        True to mirror every other TilePattern.
    flip : bool
        True to flip all tile orientations.
    copy : Optional[MOSUsedArray]
        internal parameter used to perform efficient copying of MOSUsedArray.
    """

    default_edge_info = MOSEdgeInfo()

    def __init__(self, obj: Union[TilePatternElement, MOSBasePlaceInfo, TilePattern],
                 mirror: bool = True, flip: bool = False, copy: Optional[MOSUsedArray] = None
                 ) -> None:
        if copy is None:
            if isinstance(obj, TilePatternElement):
                self._element = obj
            else:
                self._element = TilePatternElement(obj, mirror=mirror, flip=flip)

            if self._element:
                tmp = [PyDisjointIntervals()
                       for _ in range(self._element.get_tile_pinfo(0).num_rows)]
                self._intvs: List[PyDisjointIntervals] = tmp
                self._num_tiles: int = 1
            else:
                self._intvs: List[PyDisjointIntervals] = []
                self._num_tiles: int = 0

            self._end_flags: Dict[Tuple[int, int], MOSEdgeInfo] = {}
            self._num_cols: int = 0
        else:
            self._element: TilePatternElement = copy._element
            self._intvs: List[PyDisjointIntervals] = [intv.get_copy() for intv in copy._intvs]
            self._num_tiles = copy._num_tiles
            self._end_flags: Dict[Tuple[int, int], MOSEdgeInfo] = copy._end_flags.copy()
            self._num_cols: int = copy._num_cols

    @classmethod
    def get_interval(cls, col_idx: int, seg: int, flip_lr: bool) -> Tuple[int, int]:
        return col_idx - flip_lr * seg, col_idx + (1 - flip_lr) * seg

    @property
    def tile_pattern_element(self) -> TilePatternElement:
        return self._element

    @property
    def num_flat_rows(self) -> int:
        """int: Total number of rows."""
        return len(self._intvs)

    @property
    def num_tiles(self) -> int:
        return self._num_tiles

    @property
    def num_cols(self) -> int:
        """int: Number of columns."""
        return self._num_cols

    @property
    def height(self) -> int:
        return self._element.get_tile_info(self._num_tiles)[1]

    @num_cols.setter
    def num_cols(self, val: int) -> None:
        if self._num_cols > val:
            raise ValueError(f'Trying to set number of columns to {val}, '
                             f'but used {self._num_cols}.')

        self._num_cols = max(self._num_cols, val)

    def get_copy(self) -> MOSUsedArray:
        return MOSUsedArray(TilePattern([]), copy=self)

    def get_tile_pattern_element(self, mult: int, mirror: bool, flip: bool) -> TilePatternElement:
        return self._element.get_sub_pattern_element(self._num_tiles, mult, mirror, flip)

    def get_tile_subpattern(self, start_idx: int, stop_idx: int, mult: int, mirror: bool,
                            flip: bool) -> TilePatternElement:
        return self._element.get_sub_pattern_element(stop_idx - start_idx, mult, mirror, flip,
                                                     start_idx=start_idx)

    def get_tile_info(self, tile_idx: int) -> Tuple[MOSBasePlaceInfo, int, bool]:
        return self._element.get_tile_info(tile_idx)

    def get_tile_pinfo(self, tile_idx: int) -> MOSBasePlaceInfo:
        return self._element.get_tile_pinfo(tile_idx)

    def get_flip_tile(self, tile_idx: int) -> bool:
        return self._element.get_tile_info(tile_idx)[2]

    def get_num_wires(self, row_idx: int, wire_type: Union[MOSWireType, bool], wire_name: str,
                      *, tile_idx: int = 0) -> int:
        return self._element.get_num_wires(row_idx, wire_type, wire_name, tile_idx=tile_idx)

    def get_track_info(self, row_idx: int, wire_type: Union[MOSWireType, bool], wire_name: str,
                       wire_idx: int = 0, *, tile_idx: int = 0) -> Tuple[HalfInt, int]:
        return self._element.get_track_info(row_idx, wire_type, wire_name, wire_idx=wire_idx,
                                            tile_idx=tile_idx)

    def get_track_index(self, row_idx: int, wire_type: Union[MOSWireType, bool], wire_name: str,
                        wire_idx: int = 0, *, tile_idx: int = 0) -> HalfInt:
        return self._element.get_track_index(row_idx, wire_type, wire_name, wire_idx=wire_idx,
                                             tile_idx=tile_idx)

    def get_track_id(self, row_idx: int, wire_type: Union[MOSWireType, bool], wire_name: str,
                     wire_idx: int = 0, *, tile_idx: int = 0) -> TrackID:
        return self._element.get_track_id(row_idx, wire_type, wire_name, wire_idx=wire_idx,
                                          tile_idx=tile_idx)

    def get_hm_track_info(self, hm_layer: int, wire_name: str, wire_idx: int = 0, *,
                          tile_idx: int = 0) -> Tuple[HalfInt, int]:
        return self._element.get_hm_track_info(hm_layer, wire_name, wire_idx=wire_idx,
                                               tile_idx=tile_idx)

    def get_hm_track_id(self, hm_layer: int, wire_name: str, wire_idx: int = 0, *,
                        tile_idx: int = 0) -> TrackID:
        return self._element.get_hm_track_id(hm_layer, wire_name, wire_idx=wire_idx,
                                             tile_idx=tile_idx)

    def get_hm_track_index(self, hm_layer: int, wire_name: str, wire_idx: int = 0, *,
                           tile_idx: int = 0) -> HalfInt:
        return self._element.get_hm_track_index(hm_layer, wire_name, wire_idx=wire_idx,
                                                tile_idx=tile_idx)

    def flat_row_to_tile_row(self, flat_row_idx: int) -> Tuple[int, int]:
        return self._element.flat_row_to_tile_row(flat_row_idx)

    def get_flat_row_idx_and_flip(self, tile_idx: int, row_idx: int) -> Tuple[int, bool]:
        return self._element.get_flat_row_idx_and_flip(tile_idx, row_idx)

    def get_edge_info(self, flat_row_idx: int, col_idx: int) -> MOSEdgeInfo:
        return self._end_flags.get((flat_row_idx, col_idx), self.default_edge_info)

    def get_bottom_info(self, flat_row_idx: int) -> List[BlkExtInfo]:
        return self._get_ext_list_helper(flat_row_idx, 0)

    def get_top_info(self, flat_row_idx: int) -> List[BlkExtInfo]:
        return self._get_ext_list_helper(flat_row_idx, 1)

    def set_num_tiles(self, val: int) -> None:
        if self._num_tiles > val:
            raise ValueError(f'Trying to set number of tiles to {val}, '
                             f'but used {self._num_tiles}.')
        elif val > self._num_tiles:
            # make sure we contain an integer number of tiles
            self._num_tiles = val
            inc = self._element.num_tiles_to_rows(val) - self.num_flat_rows
            self._intvs.extend((PyDisjointIntervals() for _ in range(inc)))

    def add_mos(self, tile_idx: int, row_idx: int, col_idx: int, seg: int,
                flip_lr: bool, flip_ud: bool, left: Optional[MOSEdgeInfo],
                right: Optional[MOSEdgeInfo], top: BlkExtInfo, bottom: BlkExtInfo,
                abut_list: Optional[List[MOSAbutInfo]]) -> None:
        """Add a new interval to this data structure.

        Parameters
        ----------
        tile_idx: int
            the tile index.
        row_idx : int
            the row index.
        col_idx : int
            the column index.
        seg : int
            the interval length.
        flip_lr : bool
            True to flip left-right.
        flip_ud : bool
            True to flip up-down.
        left : Optional[MOSEdgeInfo]
            left edge info, before flip.
        right : Optional[MOSEdgeInfo]
            right edge info, before flip.
        top : BlkExtInfo
            top edge info, before flip.
        bottom : BlkExtInfo
            bottom edge info, before flip.
        abut_list : Optional[List[MOSAbutInfo]]
            list to store abutting transistor edges.

        Returns
        -------
        success : bool
            True if the given interval is successfully added.  False if it
            overlaps with existing blocks.
        """
        flat_row_idx, flip_tile = self._element.get_flat_row_idx_and_flip(tile_idx, row_idx)

        if tile_idx >= self._num_tiles:
            self.set_num_tiles(tile_idx + 1)

        self.add_mos_raw(flat_row_idx, flip_tile, col_idx, seg, flip_lr, flip_ud,
                         left, right, top, bottom, abut_list)

    def add_mos_raw(self, flat_row_idx: int, flip_tile: bool, col_idx: int, seg: int,
                    flip_lr: bool, flip_ud: bool, left: Optional[MOSEdgeInfo],
                    right: Optional[MOSEdgeInfo], top: BlkExtInfo, bottom: BlkExtInfo,
                    abut_list: Optional[List[MOSAbutInfo]]) -> None:
        intv = self.get_interval(col_idx, seg, flip_lr)

        flip_ud_mos = flip_tile ^ flip_ud
        if flip_ud_mos:
            val = (top, bottom)
        else:
            val = (bottom, top)

        ans = self._intvs[flat_row_idx].add(intv, val=val, merge=False, abut=True)
        if not ans:
            raise ValueError(f'Failed to add transistor in flat row {flat_row_idx}, '
                             f'columns [{intv[0]}, {intv[1]})')

        if flip_lr:
            self._add_edge_info((flat_row_idx, intv[0]), right, True, abut_list)
            self._add_edge_info((flat_row_idx, intv[1]), left, False, abut_list)
        else:
            self._add_edge_info((flat_row_idx, intv[0]), left, True, abut_list)
            self._add_edge_info((flat_row_idx, intv[1]), right, False, abut_list)

        self._num_cols = max(self._num_cols, intv[1])

    def add_tiles(self, tile_idx: int, col_idx: int, used_arr: MOSUsedArray,
                  flip_lr: bool, abut_list: List[MOSAbutInfo]) -> None:
        flip_base_tile = self._element.get_tile_info(tile_idx)[2]
        inst_tile0_flipped = used_arr.get_tile_info(0)[2]

        flip_ud = flip_base_tile ^ inst_tile0_flipped
        inst_num_rows = used_arr.num_flat_rows
        if flip_ud:
            row_idx_offset = self._element.num_tiles_to_rows(tile_idx + 1) - 1
            if row_idx_offset - inst_num_rows + 1 < 0:
                # we dipped below first row
                raise ValueError('Cannot add tiles below the first tile.')
            max_num_tiles = tile_idx + 1
        else:
            row_idx_offset = self._element.num_tiles_to_rows(tile_idx)
            max_num_tiles = tile_idx + used_arr.num_tiles

        # check that tiles are compatible
        tile_sign = 1 - 2 * int(flip_ud)
        for inst_tile_idx in range(used_arr.num_tiles):
            my_tile_idx = tile_idx + tile_sign * inst_tile_idx
            inst_pinfo = used_arr.get_tile_pinfo(inst_tile_idx)
            my_pinfo = self._element.get_tile_pinfo(my_tile_idx)
            if inst_pinfo != my_pinfo:
                raise ValueError(f'Expect tile type {my_pinfo.name} at index {my_tile_idx}, '
                                 f'but instance has tile type {inst_pinfo.name}')

        if max_num_tiles > self._num_tiles:
            self.set_num_tiles(max_num_tiles)

        scale = 1 - 2 * flip_ud
        for inst_flat_row_idx in range(inst_num_rows):
            my_flat_row_idx = row_idx_offset + scale * inst_flat_row_idx
            cur_tile, cur_row = self._element.flat_row_to_tile_row(my_flat_row_idx)
            cur_flip_tile = self._element.get_tile_info(cur_tile)[2]
            for (start, stop), linfo, rinfo, tinfo, binfo in used_arr.info_iter(inst_flat_row_idx):
                col_anchor = col_idx + (1 - 2 * flip_lr) * start
                seg = stop - start
                self.add_mos_raw(my_flat_row_idx, cur_flip_tile, col_anchor, seg, flip_lr, flip_ud,
                                 linfo, rinfo, tinfo, binfo, abut_list)

    def intv_iter(self, flat_row_idx: int) -> Iterable[Tuple[int, int]]:
        return self._intvs[flat_row_idx].intervals()

    def info_iter(self, flat_row_idx: int) -> Iterable[MOSInfoType]:
        for (start, stop), (binfo, tinfo) in self._intvs[flat_row_idx].items():
            linfo = self._end_flags.get((flat_row_idx, start), None)
            rinfo = self._end_flags.get((flat_row_idx, stop), None)
            yield (start, stop), linfo, rinfo, tinfo, binfo

    def get_complement(self, tile_idx: int, row_idx: int, start: int, stop: int
                       ) -> ImmutableList[Tuple[Tuple[int, int], MOSEdgeInfo, MOSEdgeInfo]]:
        """Returns a list of unused column intervals within the given interval.

        Parameters
        ----------
        tile_idx : int
            th tile index.
        row_idx : int
            the row index.
        start : int
            the starting column, inclusive.
        stop : int
            the ending column, exclusive.

        Returns
        -------
        ans : ImmutableList[Tuple[Tuple[int, int], MOSEdgeInfo, MOSEdgeInfo]]
            a list of unused column intervals and the associated left/right edge info.
        """
        flat_ridx = self._element.get_flat_row_idx_and_flip(tile_idx, row_idx)[0]
        compl_intv = self._intvs[flat_ridx].get_complement((start, stop))
        return ImmutableList([(intv, self._end_flags.get((flat_ridx, intv[0]),
                                                         self.default_edge_info),
                               self._end_flags.get((flat_ridx, intv[1]),
                                                   self.default_edge_info))
                              for intv in compl_intv])

    def _get_ext_list_helper(self, flat_row_idx: int, val_idx: int) -> List[BlkExtInfo]:
        return [val[val_idx] for val in self._intvs[flat_row_idx].values()]

    def _add_edge_info(self, key: Tuple[int, int], info: Optional[MOSEdgeInfo], is_right: bool,
                       abut_list: Optional[List[MOSAbutInfo]]) -> None:
        cur_edge = self._end_flags.pop(key, None)
        if cur_edge is None:
            self._end_flags[key] = info
        elif abut_list is not None and info is not None:
            if is_right:
                abut_list.append(MOSAbutInfo(key[0], key[1], cur_edge, info))
            else:
                abut_list.append(MOSAbutInfo(key[0], key[1], info, cur_edge))
