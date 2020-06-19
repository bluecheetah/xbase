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

from typing import Any, Optional, Tuple, Union, Mapping, List, Sequence, Dict, Iterable

from pathlib import Path
from bisect import bisect_right

from pybag.enum import RoundMode, Orient2D

from bag.math import lcm
from bag.util.math import HalfInt
from bag.util.immutable import ImmutableList, ImmutableSortedDict, Param, combine_hash
from bag.io.file import read_yaml, write_yaml
from bag.layout.tech import TechInfo
from bag.layout.routing.base import TrackManager, WDictType, SpDictType, TrackID
from bag.layout.routing.grid import RoutingGrid

from ...enum import MOSWireType, Alignment
from ...wires import WireGraph, WireLookup, WireData
from ..data import MOSRowSpecs, RowPlaceInfo, ExtWidthInfo
from ..tech import MOSTech

from .compact import place_rows_compact


class MOSArrayPlaceInfo:
    """A class that stores layout information of a transistor array island.

    This class stores information common to all tiles within the array.

    Parameters
    ----------
    parent_grid : RoutingGrid
        the RoutingGrid object.
    lch : int
        the transistor channel length.
    tr_widths : WDictType
        dictionary from wire types to its width on each layer.
    tr_spaces : SpDictType
        dictionary from wire types to its spaces on each layer.
    top_layer : Optional[int]
        the top layer ID.
    conn_layer : Optional[int]
        the connection layer ID.
    half_space : bool
        True to allow half-track spaces.
    arr_options : Optional[Mapping[str, Any]]
        Process-specific options for the entire array.
    """

    def __init__(self, parent_grid: RoutingGrid, lch: int, tr_widths: WDictType,
                 tr_spaces: SpDictType, *, top_layer: Optional[int] = None,
                 conn_layer: Optional[int] = None, half_space: bool = True,
                 arr_options: Optional[Mapping[str, Any]] = None) -> None:
        arr_options = ImmutableSortedDict(arr_options)
        self._tech_cls: MOSTech = parent_grid.tech_info.get_device_tech('mos', lch=lch,
                                                                        arr_options=arr_options)

        # update routing grid
        if conn_layer is None:
            conn_layer = self._tech_cls.conn_layer
        if top_layer is None:
            top_layer = conn_layer + 1

        tr_specs = self._tech_cls.get_track_specs(conn_layer, top_layer)
        grid: RoutingGrid = parent_grid.get_copy_with(tr_specs=tr_specs)

        # set attributes
        self._tr_manager = TrackManager(grid, tr_widths, tr_spaces, half_space=half_space)
        self._lch = lch
        self._conn_layer = conn_layer
        self._top_layer = top_layer
        self._half_space = half_space
        self._arr_options: Param = arr_options

        # compute hash
        seed = self._lch
        seed = combine_hash(seed, hash(self._tr_manager))
        seed = combine_hash(seed, self._conn_layer)
        seed = combine_hash(seed, self._top_layer)
        seed = combine_hash(seed, self._half_space)
        seed = combine_hash(seed, hash(self._arr_options))
        self._hash = seed

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: Any) -> bool:
        return (isinstance(other, MOSArrayPlaceInfo) and
                self._lch == other._lch and
                self._conn_layer == other._conn_layer and
                self._top_layer == other._top_layer and
                self._half_space == other._half_space and
                self._tr_manager == other._tr_manager and
                self._arr_options == other._arr_options)

    @classmethod
    def get_conn_layer(cls, tech_info: TechInfo, lch: int,
                       arr_options: Optional[Mapping[str, Any]] = None) -> int:
        if arr_options is None:
            arr_options = {}
        return tech_info.get_device_tech('mos', lch=lch, arr_options=arr_options).conn_layer

    @classmethod
    def make_array_info(cls, grid: RoutingGrid, val: Mapping[str, Any]) -> MOSArrayPlaceInfo:
        return MOSArrayPlaceInfo(grid, val['lch'], val['tr_widths'], val['tr_spaces'],
                                 top_layer=val.get('top_layer', None),
                                 conn_layer=val.get('conn_layer', None),
                                 half_space=val.get('half_space', True),
                                 arr_options=val.get('arr_options', None))

    @property
    def grid(self) -> RoutingGrid:
        return self._tr_manager.grid

    @property
    def tr_manager(self) -> TrackManager:
        """TrackManager: The TrackManager object."""
        return self._tr_manager

    @property
    def tech_cls(self) -> MOSTech:
        """MOSTech: The primitive technology object."""
        return self._tech_cls

    @property
    def lch(self) -> int:
        """int: The channel length."""
        return self._lch

    @property
    def top_layer(self) -> int:
        """int: The top layer ID."""
        return self._top_layer

    @property
    def conn_layer(self) -> int:
        """int: The transistor port layer ID."""
        return self._conn_layer

    @property
    def sd_pitch(self) -> int:
        return self._tech_cls.sd_pitch

    @property
    def half_space(self) -> int:
        return self._half_space

    @property
    def arr_options(self) -> Param:
        return self._arr_options

    def get_tile_blk_h(self, half_blk: bool = True) -> int:
        return lcm([self._tr_manager.grid.get_block_size(self._top_layer, half_blk_y=half_blk)[1],
                    self._tech_cls.blk_h_pitch])

    def get_source_track(self, col_idx: int) -> HalfInt:
        return HalfInt(self.grid.coord_to_htr(self.conn_layer, col_idx * self.sd_pitch,
                                              RoundMode.NONE, False))

    def get_source_track_col(self, track_index: HalfInt) -> int:
        return self.coord_to_col(self.grid.track_to_coord(self.conn_layer, track_index))

    def coord_to_col(self, coord: int, round_mode: RoundMode = RoundMode.NONE) -> int:
        q, r = divmod(coord, self.sd_pitch)
        if r != 0:
            if round_mode is RoundMode.NONE:
                raise ValueError(f'Coordinate {coord} is not on a column')
            if round_mode < 0:
                return q
            if round_mode > 0:
                return q + 1
            if r < self.sd_pitch // 2:
                return q
            return q + 1
        if round_mode is RoundMode.LESS:
            return q - 1
        if round_mode is RoundMode.GREATER:
            return q + 1
        return q

    def col_to_coord(self, col: int) -> int:
        return self.sd_pitch * col

    def col_to_track(self, layer: int, col: int,
                     mode: RoundMode = RoundMode.NONE, even: bool = False) -> HalfInt:
        coord = self.col_to_coord(col)
        return self.grid.coord_to_track(layer, coord, mode=mode, even=even)

    def track_to_col(self, layer: int, track_index: HalfInt, mode: RoundMode = RoundMode.NEAREST
                     ) -> int:
        coord = self.grid.track_to_coord(layer, track_index)
        return self.coord_to_col(coord, round_mode=mode)

    def get_column_span(self, vm_layer: int, num_tracks: HalfInt) -> int:
        """Returns the minimum number of columns to fit given number of tracks.

        Parameters
        ----------
        vm_layer : int
            the vertical routing layer ID.
        num_tracks : HalfInt
            number of tracks.
        Returns
        -------
        num_col : int
            number of MOSBase columns.
        """
        return self.coord_to_col(self.grid.track_to_coord(vm_layer, num_tracks),
                                 round_mode=RoundMode.GREATER_EQ)

    def get_block_ncol(self, vm_layer: int, half_blk: bool = False) -> int:
        """Returns the number of columns in a unit block for the given vertical routing layer.

        this is the number of columns of the smallest unit block that you can tile and guarantee
        that the wires on the given vertical layers will stay on grid.

        Parameters
        ----------
        vm_layer : int
            a vertical routing layer ID.
        half_blk : bool
            True to allow half-block size.  Defaults to False.
        """
        grid = self.grid
        top_layer = self.top_layer
        if grid.get_direction(vm_layer) != Orient2D.y:
            raise ValueError(f'layer {vm_layer} is not a vertical routing layer.')
        if vm_layer > top_layer:
            raise ValueError(f'this method only works on layers <= {top_layer}')

        tr_pitch = self.grid.get_track_pitch(vm_layer)
        if half_blk:
            tr_pitch //= 2
        sd_pitch = self.sd_pitch
        return lcm([tr_pitch, sd_pitch]) // sd_pitch

    def round_up_to_block_size(self, vm_layer: int, ncol: int,
                               even_diff: bool = False, half_blk: bool = False) -> int:
        blk_ncol = self.get_block_ncol(vm_layer, half_blk=half_blk)
        new_ncol = -(-ncol // blk_ncol) * blk_ncol
        if even_diff and (new_ncol - ncol) & 1:
            if blk_ncol & 1:
                return new_ncol + blk_ncol
            raise ValueError('Cannot round up to block size by appending even number of columns.')
        return new_ncol


def make_pinfo_compact(arr_info: MOSArrayPlaceInfo, row_specs: Sequence[MOSRowSpecs],
                       bot_mirror: bool, top_mirror: bool, name: str = '', min_height: int = 0,
                       tile_options: Optional[Param] = None, priority: int = 0,
                       wire_graphs: Optional[Dict[int, WireGraph]] = None) -> MOSBasePlaceInfo:
    if tile_options is None:
        tile_options = ImmutableSortedDict()
    if wire_graphs is None:
        wire_graphs = {}

    # set info object
    tr_manager = arr_info.tr_manager
    tmp = place_rows_compact(tr_manager, arr_info.tech_cls, row_specs, min_height,
                             arr_info.get_tile_blk_h(), bot_mirror, top_mirror, tile_options)
    rp_list, rg_list = tmp

    wire_lookup = {}
    for lay, wg in wire_graphs.items():
        wg.align_wires(lay, tr_manager, rp_list[0].yb, rp_list[-1].yt)
        wire_lookup[lay] = wg.get_wire_lookup()

    return MOSBasePlaceInfo(name, arr_info, rp_list, bot_mirror, top_mirror, tile_options,
                            rg_list=rg_list, priority=priority, wire_lookup=wire_lookup)


def make_pinfo_compact_specs(arr_info: MOSArrayPlaceInfo, name: str, specs: Mapping[str, Any]
                             ) -> MOSBasePlaceInfo:
    row_specs: List[Mapping[str, Any]] = specs['row_specs']
    min_height: int = specs.get('min_height', 0)
    options: Mapping[str, Any] = specs.get('options', {})
    bot_mirror: bool = specs.get('bot_mirror', True)
    top_mirror: bool = specs.get('top_mirror', True)
    priority: int = specs.get('priority', 0)
    wire_specs: Mapping[int, Any] = specs.get('wire_specs', {})

    top_layer = arr_info.top_layer
    tr_manager = arr_info.tr_manager
    grid = tr_manager.grid
    wire_graphs = {}
    for layer, wd_specs in wire_specs.items():
        if not grid.is_horizontal(layer):
            raise ValueError('Can only specify horizontal routing layers in wire_specs.')
        if layer > top_layer:
            raise ValueError(f'Cannot specify wires on layer={layer} > top_layer={top_layer}')
        wd = WireData.make_wire_data(wd_specs, Alignment.CENTER_COMPACT, '')
        wg = WireGraph.make_wire_graph(layer, tr_manager, wd)
        wg.place_compact(layer, tr_manager, lower=0)
        min_height = max(min_height, wg.upper)
        wire_graphs[layer] = wg

    rs_list = [MOSRowSpecs.make_row_specs(v) for v in row_specs]
    return make_pinfo_compact(arr_info, rs_list, bot_mirror, top_mirror, name=name,
                              min_height=min_height, tile_options=ImmutableSortedDict(options),
                              priority=priority, wire_graphs=wire_graphs)


class MOSBasePlaceInfo:
    """A class that stores layout information of a single tile in MOSBase.

    Parameters
    ----------
    name : str
        name of this tile.
    arr_info : MOSArrayPlaceInfo
        the transistor array information object.
    rp_list : ImmutableList[RowPlaceInfo]
        list of placement information of each transistor row in this tile.
    bot_mirror : bool
        True to satisfy mirror placement constraint on the bottom edge.
    top_mirror : bool
        True to satisfy mirror placement constraint on the top edge.
    options : Param
        process-specific options for this tile.
    rg_list : Optional[List[Tuple[WireGraph, WireGraph]]]
        list of wire graph objects for each transistor row.
        optional.  Only use for debugging/visualization purposes.
    """

    def __init__(self, name: str, arr_info: MOSArrayPlaceInfo, rp_list: ImmutableList[RowPlaceInfo],
                 bot_mirror: bool, top_mirror: bool, options: Param,
                 rg_list: Optional[List[Tuple[WireGraph, WireGraph]]] = None,
                 priority: int = 0, wire_lookup: Optional[Dict[int, WireLookup]] = None) -> None:
        if not name:
            name = 'unnamed'

        self._name = name
        self._arr_info = arr_info
        self._pinfo_list = rp_list
        self._options = options
        self._bot_mirror = bot_mirror
        self._top_mirror = top_mirror
        self._row_graph_list = rg_list
        self._priority = priority
        self._wire_lookup = ImmutableSortedDict(wire_lookup)

        # compute hash
        seed = hash(self._arr_info)
        seed = combine_hash(seed, hash(self._name))
        seed = combine_hash(seed, hash(self._pinfo_list))
        seed = combine_hash(seed, hash(self._options))
        self._hash = seed

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: Any) -> bool:
        return (isinstance(other, MOSBasePlaceInfo) and
                self._name == other._name and
                self._arr_info == other._arr_info and
                self._pinfo_list == other._pinfo_list and
                self._options == other._options and
                self._wire_lookup == other._wire_lookup)

    @classmethod
    def get_conn_layer(cls, tech_info: TechInfo, lch: int) -> int:
        return MOSArrayPlaceInfo.get_conn_layer(tech_info, lch)

    @classmethod
    def make_place_info(cls, grid: RoutingGrid,
                        val: Union[MOSBasePlaceInfo,
                                   Tuple[Union[MOSBasePlaceInfo, TilePattern], TileInfoTable],
                                   Mapping[str, Any]],
                        name: str = ''
                        ) -> Union[MOSBasePlaceInfo,
                                   Tuple[Union[MOSBasePlaceInfo, TilePattern], TileInfoTable]]:
        if isinstance(val, MOSBasePlaceInfo) or isinstance(val, tuple):
            return val

        root_dir: str = val.get('root_dir', '')
        tile_specs: Mapping[str, Any] = val.get('tile_specs', {})
        if root_dir:
            info_table = TileInfoTable.load(grid, Path(root_dir))
            return info_table.make_place_info(val), info_table
        elif tile_specs:
            info_table = TileInfoTable.make_tiles(grid, tile_specs)
            return info_table.make_place_info(val), info_table
        else:
            # specs for MOSBasePlaceInfo
            arr_info = MOSArrayPlaceInfo.make_array_info(grid, val)
            pinfo = make_pinfo_compact_specs(arr_info, name, val)
            return pinfo

    @property
    def name(self) -> str:
        return self._name

    @property
    def num_rows(self) -> int:
        return len(self._pinfo_list)

    @property
    def height(self) -> int:
        return self._pinfo_list[-1].yt

    @property
    def true_height(self) -> int:
        return self._pinfo_list[-1].yt_blk - self._pinfo_list[0].yb_blk

    @property
    def ext_h_bot(self) -> int:
        tmp = self._pinfo_list[0]
        return tmp.yb_blk - tmp.yb

    @property
    def ext_h_top(self) -> int:
        tmp = self._pinfo_list[-1]
        return tmp.yt - tmp.yt_blk

    @property
    def extend_priority(self) -> int:
        return self._priority

    @property
    def tile_options(self) -> Param:
        return self._options

    @property
    def arr_info(self) -> MOSArrayPlaceInfo:
        return self._arr_info

    @property
    def grid(self) -> RoutingGrid:
        return self._arr_info.grid

    @property
    def tr_manager(self) -> TrackManager:
        return self._arr_info.tr_manager

    @property
    def lch(self) -> int:
        return self._arr_info.lch

    @property
    def top_layer(self) -> int:
        return self._arr_info.top_layer

    @property
    def conn_layer(self) -> int:
        return self._arr_info.conn_layer

    @property
    def tech_cls(self) -> MOSTech:
        return self._arr_info.tech_cls

    @property
    def sd_pitch(self) -> int:
        return self._arr_info.sd_pitch

    @property
    def is_complementary(self) -> bool:
        is_pwell = False
        is_nwell = False
        for pinfo in self._pinfo_list:
            if pinfo.row_info.row_type.is_pwell:
                is_pwell = True
            else:
                is_nwell = True
            if is_pwell and is_nwell:
                return True
        return False

    def get_mirror(self, top_edge: bool) -> bool:
        """Returns True if the specify edge satisfies mirror placement constraint."""
        return (top_edge and self._top_mirror) or ((not top_edge) and self._bot_mirror)

    def get_row_place_info(self, row_idx: int) -> RowPlaceInfo:
        return self._pinfo_list[row_idx]

    def get_hm_track_info(self, hm_layer: int, wire_name: str, wire_idx: int = 0
                          ) -> Tuple[HalfInt, int]:
        return self._wire_lookup[hm_layer].get_track_info(wire_name, wire_idx)

    def get_abut_info(self, rhs: MOSBasePlaceInfo, top_edge: bool, rhs_top_edge: bool,
                      shared: Sequence[str], rhs_shared: Sequence[str]
                      ) -> Tuple[int, ExtWidthInfo, int, int]:
        """Returns the margin needed to abut this tile with the given tile.

        Parameters
        ----------
        rhs : MOSBasePlaceInfo
            the other tile.
        top_edge : bool
            True if rhs is abutting to top edge of this tile.
        rhs_top_edge : bool
            True if we're abutting to top edge of the other tile.
        shared: Sequence[str]
            list of edge wires shared with the other tile.
        rhs_shared : Sequence[str]
            list of edge wires from the other tile shared with this tile.

        Returns
        -------
        margin : int
            the margin in resolution units.
        ext_w_info : ExtWidthInfo
            the ExtWidthInfo object.
        em1 : int
            the existing extension margin (in resolution units).
        em2 : int
            the existing extension margin on the other tile (in resolution units).
        """
        tech_cls = self.tech_cls
        blk_h_pitch = tech_cls.blk_h_pitch

        idx = int(top_edge) * (self.num_rows - 1)
        rhs_idx = int(rhs_top_edge) * (rhs.num_rows - 1)
        rpinfo = self.get_row_place_info(idx)
        rhs_rpinfo = rhs.get_row_place_info(rhs_idx)

        wmargin, einfo1, einfo2 = rpinfo.get_abut_info(rhs_rpinfo, top_edge, rhs_top_edge,
                                                       shared, rhs_shared,
                                                       self.tr_manager, self.conn_layer + 1)

        emargin1 = rpinfo.get_ext_margin(top_edge)
        emargin2 = rhs_rpinfo.get_ext_margin(rhs_top_edge)
        emargin_tot = emargin1 + emargin2
        ext_w_min = -(-(emargin_tot + wmargin) // blk_h_pitch)

        ext_w_info = tech_cls.get_ext_width_info(einfo1, einfo2)
        ext_w = ext_w_info.get_next_width(ext_w_min)
        return blk_h_pitch * ext_w - emargin_tot, ext_w_info, emargin1, emargin2

    def get_source_track(self, col_idx: int) -> HalfInt:
        return self._arr_info.get_source_track(col_idx)

    def get_source_track_col(self, track_index: HalfInt) -> int:
        return self._arr_info.get_source_track_col(track_index)

    def coord_to_col(self, coord: int, round_mode: RoundMode = RoundMode.NONE) -> int:
        return self._arr_info.coord_to_col(coord, round_mode=round_mode)

    def col_to_coord(self, col: int) -> int:
        return self._arr_info.col_to_coord(col)

    def get_column_span(self, vm_layer: int, num_tracks: HalfInt) -> int:
        return self._arr_info.get_column_span(vm_layer, num_tracks)

    def get_block_ncol(self, vm_layer: int) -> int:
        return self._arr_info.get_block_ncol(vm_layer)

    def show_wire_graph(self, row_idx: int, top_or_bot: str = 'bot') -> None:
        if self._row_graph_list is None:
            raise ValueError('WireGraph objects not stored.')

        from networkx.drawing import layout, draw_networkx
        import matplotlib.pyplot as plt

        dir_index = 0 if top_or_bot == 'bot' else 1
        graph = self._row_graph_list[row_idx][dir_index].graph
        pos = layout.kamada_kawai_layout(graph)
        draw_networkx(graph, pos)
        plt.title(f'row: {row_idx}, {top_or_bot} side')
        plt.show()

    def get_extend(self, margin: int, top_edge: bool, ext_w_info: ExtWidthInfo, cur_em: int,
                   other_em: int, shared: Sequence[str], max_iter: int = 1000) -> MOSBasePlaceInfo:
        blk_h_pitch = self.tech_cls.blk_h_pitch
        tot_h_pitch = self.grid.get_block_size(self.top_layer, half_blk_y=True)[1]

        em_tot = cur_em + other_em
        for iter_idx in range(max_iter):
            cur_ext_w = -(-(em_tot + margin) // blk_h_pitch)
            next_ext_w = ext_w_info.get_next_width(cur_ext_w)
            ext_dim = next_ext_w * blk_h_pitch - em_tot
            q, r = divmod(ext_dim, tot_h_pitch)
            if r == 0:
                # we can extension safely and satisfy height quantization
                return self._get_extend_helper(ext_dim, top_edge, shared)
            else:
                # need more margin
                margin = (q + 1) * tot_h_pitch

        raise ValueError('Fail to extend tile with height quantization constraint in '
                         f'{max_iter} iterations')

    def _get_extend_helper(self, delta: int, top_edge: bool, shared: Sequence[str]
                           ) -> MOSBasePlaceInfo:
        tr_pitch = self.grid.get_track_pitch(self.conn_layer + 1)
        new_info_list: List[RowPlaceInfo] = self._pinfo_list.to_list()
        if top_edge:
            new_info_list[-1] = new_info_list[-1].get_extend(tr_pitch, delta, True, shared)
        else:
            new_info_list[0] = new_info_list[0].get_extend(tr_pitch, delta, False, shared)
            for idx in range(1, len(new_info_list)):
                new_info_list[idx] = new_info_list[idx].get_move(tr_pitch, delta)

        return MOSBasePlaceInfo(self._name, self._arr_info, ImmutableList(new_info_list),
                                self._bot_mirror, self._top_mirror, self._options,
                                rg_list=self._row_graph_list, priority=self._priority)


class TilePatternElement:
    """A single element inside a tile pattern.

    A tile pattern element consists of a single tile or a tile pattern repeated multiple times,
    with possible mirroring.

    NOTE: the multiplier parameter is only used to compute num_rows, num_tiles, and height
    properties.  All other methods assumes that the unit element is repeated indefinitely.
    This design choice allows us to use one class to represent both a given element that repeats
    a finite amount, or a dynamically growing repeating tile pattern.
    """

    def __init__(self, info: Union[MOSBasePlaceInfo, TilePattern],
                 mirror: bool = True, flip: bool = False, mult: int = 1) -> None:
        self._info = info
        self._mirror = mirror
        self._flip = flip
        self._mult = mult

        # compute hash
        seed = self._mult
        seed = combine_hash(seed, hash(self._mirror))
        seed = combine_hash(seed, hash(self._flip))
        seed = combine_hash(seed, hash(self._info))
        self._hash = seed

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: Any) -> bool:
        return (isinstance(other, TilePatternElement) and
                self._info == other._info and
                self._mirror == other._mirror and
                self._flip == other._flip and
                self._mult == other._mult)

    def __bool__(self) -> bool:
        return isinstance(self._info, MOSBasePlaceInfo) or bool(self._info)

    @property
    def name(self) -> str:
        if isinstance(self._info, MOSBasePlaceInfo):
            return self._info.name
        return ''

    @property
    def arr_info(self) -> MOSArrayPlaceInfo:
        return self._info.arr_info

    @property
    def num_rows(self) -> int:
        return self._info.num_rows * self._mult

    @property
    def num_tiles(self) -> int:
        return self.num_tiles_unit * self._mult

    @property
    def num_tiles_unit(self) -> int:
        return 1 if isinstance(self._info, MOSBasePlaceInfo) else self._info.num_tiles

    @property
    def height(self) -> int:
        return self._info.height * self._mult

    @property
    def mult(self) -> int:
        return self._mult

    @classmethod
    def make_element(cls, table: Mapping[str, MOSBasePlaceInfo],
                     specs: Union[str, Mapping[str, Any]]) -> TilePatternElement:
        if isinstance(specs, str):
            # A MOSBasePlaceInfo element
            return TilePatternElement(table[specs])

        mirror: bool = specs.get('mirror', True)
        flip: bool = specs.get('flip', False)
        mult: int = specs.get('mult', 1)
        name: str = specs.get('name', '')

        if name:
            # A MOSBasePlaceInfo element
            return TilePatternElement(table[name], mirror=mirror, flip=flip, mult=mult)
        else:
            return TilePatternElement(TilePattern.make_pattern(table, specs['tiles']),
                                      mirror=mirror, flip=flip, mult=mult)

    def get_flip_unit(self, unit_idx: int) -> bool:
        return ((unit_idx & 1) and self._mirror) ^ self._flip

    def num_tiles_to_rows(self, num_tiles: int) -> int:
        if isinstance(self._info, MOSBasePlaceInfo):
            return num_tiles * self._info.num_rows
        elif num_tiles == 0:
            return 0
        else:
            pat_ntile = self._info.num_tiles
            q, r = divmod(num_tiles, pat_ntile)
            ans = q * self._info.num_rows
            flip_pat = self.get_flip_unit(q)
            if flip_pat:
                r = pat_ntile - r
                return ans + self._info.num_rows - self._info.num_tiles_to_rows(r)
            else:
                return ans + self._info.num_tiles_to_rows(r)

    def get_tile_info(self, tile_idx: int) -> Tuple[MOSBasePlaceInfo, int, bool]:
        """Returns the tile information for the given tile index.

        Parameters
        ----------
        tile_idx : int
            the tile index.

        Returns
        -------
        pinfo : MOSBasePlaceInfo
            the tile layout information object.
        y0 : int
            the bottom Y coordinate of the tile.
        flip : bool
            True if this tile is flipped.
        """
        if isinstance(self._info, MOSBasePlaceInfo):
            y0 = tile_idx * self._info.height
            return self._info, y0, self.get_flip_unit(tile_idx)
        else:
            pat_ntile = self._info.num_tiles
            pat_height = self._info.height
            q, r = divmod(tile_idx, pat_ntile)
            flip_pat = self.get_flip_unit(q)
            if flip_pat:
                r = pat_ntile - 1 - r

            ans, y0, flip = self._info.get_tile_info(r)
            if flip_pat:
                y0 = pat_height - y0 - ans.height

            y0 += q * pat_height
            return ans, y0, flip ^ flip_pat

    def get_tile_pinfo(self, tile_idx: int) -> MOSBasePlaceInfo:
        return self.get_tile_info(tile_idx)[0]

    def get_hm_track_info(self, hm_layer: int, wire_name: str, wire_idx: int = 0, *,
                          tile_idx: int = 0) -> Tuple[HalfInt, int]:
        grid = self.arr_info.grid

        pinfo, y0, flip_tile = self.get_tile_info(tile_idx)
        tr_idx, tr_w = pinfo.get_hm_track_info(hm_layer, wire_name, wire_idx)

        if flip_tile:
            y0 += pinfo.height - grid.track_to_coord(hm_layer, tr_idx)
        else:
            y0 += grid.track_to_coord(hm_layer, tr_idx)

        return grid.coord_to_track(hm_layer, y0), tr_w

    def get_hm_track_id(self, hm_layer: int, wire_name: str, wire_idx: int = 0, *,
                        tile_idx: int = 0) -> TrackID:
        tr_idx, tr_w = self.get_hm_track_info(hm_layer, wire_name, wire_idx=wire_idx,
                                              tile_idx=tile_idx)
        return TrackID(hm_layer, tr_idx, width=tr_w, grid=self.arr_info.grid)

    def get_hm_track_index(self, hm_layer: int, wire_name: str, wire_idx: int = 0, *,
                           tile_idx: int = 0) -> HalfInt:
        return self.get_hm_track_info(hm_layer, wire_name, wire_idx=wire_idx, tile_idx=tile_idx)[0]

    def get_track_info(self, row_idx: int, wire_type: Union[MOSWireType, bool], wire_name: str,
                       wire_idx: int = 0, *, tile_idx: int = 0) -> Tuple[HalfInt, int]:
        ainfo = self.arr_info
        grid = ainfo.grid
        hm_layer = ainfo.conn_layer + 1

        wlookup, yoff, sign = self._get_wire_info(row_idx, wire_type, tile_idx)
        tr_idx, tr_w = wlookup.get_track_info(wire_name, wire_idx)

        y0 = yoff + sign * grid.track_to_coord(hm_layer, tr_idx)
        return grid.coord_to_track(hm_layer, y0), tr_w

    def get_track_index(self, row_idx: int, wire_type: Union[MOSWireType, bool], wire_name: str,
                        wire_idx: int = 0, *, tile_idx: int = 0) -> HalfInt:
        return self.get_track_info(row_idx, wire_type, wire_name, wire_idx=wire_idx,
                                   tile_idx=tile_idx)[0]

    def get_track_id(self, row_idx: int, wire_type: Union[MOSWireType, bool], wire_name: str,
                     wire_idx: int = 0, *, tile_idx: int = 0) -> TrackID:
        tr_idx, tr_w = self.get_track_info(row_idx, wire_type, wire_name, wire_idx=wire_idx,
                                           tile_idx=tile_idx)
        arr_info = self.arr_info
        return TrackID(arr_info.conn_layer + 1, tr_idx, width=tr_w, grid=arr_info.grid)

    def get_wire_range(self, row_idx: int, wire_type: Union[MOSWireType, bool], wire_name: str,
                       *, tile_idx: int = 0) -> Tuple[int, int]:
        wlookup = self._get_wire_info(row_idx, wire_type, tile_idx)[0]
        return wlookup.get_wire_range(wire_name)

    def get_num_wires(self, row_idx: int, wire_type: Union[MOSWireType, bool], wire_name: str,
                      *, tile_idx: int = 0) -> int:
        lower, upper = self.get_wire_range(row_idx, wire_type, wire_name, tile_idx=tile_idx)
        return upper - lower

    def get_flat_row_idx_and_flip(self, tile_idx: int, row_idx: int) -> Tuple[int, bool]:
        ans = self.num_tiles_to_rows(tile_idx)
        info, _, flip = self.get_tile_info(tile_idx)
        if flip:
            return ans + info.num_rows - row_idx - 1, flip
        else:
            return ans + row_idx, flip

    def flat_row_to_tile_row(self, flat_row_idx: int) -> Tuple[int, int]:
        if isinstance(self._info, MOSBasePlaceInfo):
            num_rows = self._info.num_rows
            tile_idx, row_idx = divmod(flat_row_idx, num_rows)
            if self.get_flip_unit(tile_idx):
                row_idx = num_rows - 1 - row_idx
            return tile_idx, row_idx
        else:
            pat_nrow = self._info.num_rows
            q, r = divmod(flat_row_idx, pat_nrow)
            flip_pat = self.get_flip_unit(q)
            if flip_pat:
                r = pat_nrow - 1 - r
            tile_idx, row_idx = self._info.flat_row_to_tile_row(r)
            tile_idx += q * self._info.num_tiles
            return tile_idx, row_idx

    def get_sub_pattern_element(self, num_tiles: int, mult: int, mirror: bool, flip: bool,
                                start_idx: int = 0) -> TilePatternElement:
        """Returns a repeated sub-pattern (analogous to substrings).
        """
        start_idx = start_idx % self.num_tiles_unit
        if start_idx == 0:
            return self._get_sub_pattern_element_helper(num_tiles, mult, mirror, flip)

        # self._info must be TilePattern
        num0 = self.num_tiles_unit - start_idx
        if num_tiles <= num0:
            return self._info.get_sub_pattern_element(num_tiles, mult, mirror, flip,
                                                      start_idx=start_idx)

        num1 = num_tiles - num0
        ele_list = [self._info.get_sub_pattern_element(num0, 1, False, False, start_idx=start_idx),
                    self._get_sub_pattern_element_helper(num1, 1, False, False)]
        return TilePatternElement(TilePattern(ele_list), mirror=mirror, flip=flip, mult=mult)

    def get_reverse(self, mult: int) -> TilePatternElement:
        flip_last = self.get_flip_unit(mult - 1)
        return TilePatternElement(self._info, mirror=self._mirror, flip=not flip_last, mult=mult)

    def append_sub_pattern(self, ele_list: List[TilePatternElement], num_tiles: int,
                           flip_element: bool) -> None:
        q, r = divmod(num_tiles, self.num_tiles_unit)
        if flip_element:
            flip_q = self.get_flip_unit(self._mult - 1)
            flip_r = not self.get_flip_unit(self._mult - 1 - q)
        else:
            flip_q = self._flip
            flip_r = self.get_flip_unit(q)

        if q > 0:
            ele_list.append(TilePatternElement(self._info, mirror=self._mirror,
                                               flip=flip_q, mult=q))
        if r > 0:
            self._info.append_sub_pattern(ele_list, r, flip_r)

    def _get_sub_pattern_element_helper(self, num_tiles: int, mult: int, mirror: bool, flip: bool
                                        ) -> TilePatternElement:
        if num_tiles == 0:
            raise ValueError('Must have positive number of tiles.')

        mirror = mirror and (mult > 1)
        q, r = divmod(num_tiles, self.num_tiles_unit)
        q_mirror = self._mirror and (q > 1)
        if r == 0:
            # we have two nested repeated element, see if we can collapse
            if q == 1:
                return TilePatternElement(self._info, mirror=mirror,
                                          flip=flip ^ self._flip, mult=mult)
            elif mult == 1:
                if flip:
                    return self.get_reverse(q)
                else:
                    return TilePatternElement(self._info, mirror=q_mirror,
                                              flip=self._flip, mult=q)
            elif q_mirror == mirror:
                if mirror and flip:
                    flip0 = self._flip ^ (q & 1)
                else:
                    flip0 = self._flip ^ flip
                return TilePatternElement(self._info, mirror=mirror, flip=flip0, mult=q * mult)
            elif mirror or (q & 1):
                # nested tile pattern
                ele_inner = TilePatternElement(self._info, mirror=q_mirror, flip=self._flip,
                                               mult=q)
                return TilePatternElement(TilePattern([ele_inner]), mirror=mirror, flip=flip,
                                          mult=mult)
            else:
                # here if q_mirror = True, mirror = False, q is even
                return TilePatternElement(self._info, mirror=True, flip=self._flip, mult=q * mult)
        else:
            ele_list = []
            if q > 0:
                ele_list.append(TilePatternElement(self._info, mirror=q_mirror,
                                                   flip=self._flip, mult=q))
            flip_last = self.get_flip_unit(q)
            self._info.append_sub_pattern(ele_list, r, flip_last)
            return TilePatternElement(TilePattern(ele_list), mirror=mirror, flip=flip, mult=mult)

    def _get_wire_info(self, row_idx: int, wire_type: Union[MOSWireType, bool], tile_idx: int
                       ) -> Tuple[WireLookup, int, int]:
        if tile_idx < 0:
            raise ValueError(f'tile_idx cannot be negative.')

        pinfo, yb, flip_tile = self.get_tile_info(tile_idx)

        if row_idx < 0:
            row_idx += pinfo.num_rows
            if row_idx < 0:
                raise ValueError(f'Invalid row after wrapping negative: {row_idx}')

        rpinfo = pinfo.get_row_place_info(row_idx)
        if isinstance(wire_type, bool):
            top = wire_type
        else:
            flip_row = rpinfo.row_info.flip
            top = (wire_type.is_gate == flip_row)
        wlookup = rpinfo.top_wires if top else rpinfo.bot_wires

        if flip_tile:
            return wlookup, yb + pinfo.height, -1
        else:
            return wlookup, yb, 1


class TilePattern:
    """A recursive list of tile layout information objects.

    Used to represent repeating/fractal tile patterns in a transistor array.
    """

    def __init__(self, data: List[TilePatternElement]) -> None:
        self._pat_list = ImmutableList(data)
        self._nrow_list: List[int] = [0]
        self._ntile_list: List[int] = [0]
        self._dy_list: List[int] = [0]

        seed = cum_tile = cum_h = cum_row = 0
        for obj in data:
            seed = combine_hash(seed, hash(obj))
            cum_row += obj.num_rows
            cum_tile += obj.num_tiles
            cum_h += obj.height
            self._nrow_list.append(cum_row)
            self._ntile_list.append(cum_tile)
            self._dy_list.append(cum_h)

    def __hash__(self) -> int:
        return hash(self._pat_list)

    def __eq__(self, other: Any) -> bool:
        return (isinstance(other, TilePattern) and
                self._pat_list == other._pat_list)

    def __bool__(self) -> bool:
        return bool(self._pat_list)

    @property
    def arr_info(self) -> MOSArrayPlaceInfo:
        return self._pat_list[0].arr_info

    @property
    def num_rows(self) -> int:
        return self._nrow_list[-1]

    @property
    def num_tiles(self) -> int:
        return self._ntile_list[-1]

    @property
    def height(self) -> int:
        return self._dy_list[-1]

    @classmethod
    def make_pattern(cls, table: Mapping[str, MOSBasePlaceInfo],
                     spec_list: Iterable[Mapping[str, Any]]
                     ) -> TilePattern:
        tile_list = [TilePatternElement.make_element(table, element) for element in spec_list]
        return TilePattern(tile_list)

    def get_element_idx(self, tile_idx: int) -> int:
        return bisect_right(self._ntile_list, tile_idx) - 1

    def num_tiles_to_rows(self, num_tiles: int) -> int:
        if num_tiles == 0:
            return 0

        list_idx = self.get_element_idx(num_tiles - 1)
        tile_offset = self._ntile_list[list_idx]
        ans = self._nrow_list[list_idx]
        obj = self._pat_list[list_idx]
        return ans + obj.num_tiles_to_rows(num_tiles - tile_offset)

    def get_tile_info(self, tile_idx: int) -> Tuple[MOSBasePlaceInfo, int, bool]:
        """Returns the tile information for the given tile index.

        Parameters
        ----------
        tile_idx : int
            the tile index.

        Returns
        -------
        pinfo : MOSBasePlaceInfo
            the tile layout information object.
        y0 : int
            the bottom Y coordinate of the tile.
        flip : bool
            True if this tile is flipped.
        """
        list_idx = self.get_element_idx(tile_idx)
        tile_offset = self._ntile_list[list_idx]
        obj = self._pat_list[list_idx]
        pinfo, y0, flip_tile = obj.get_tile_info(tile_idx - tile_offset)
        return pinfo, y0 + self._dy_list[list_idx], flip_tile

    def get_tile_pinfo(self, tile_idx: int) -> MOSBasePlaceInfo:
        return self.get_tile_info(tile_idx)[0]

    def flat_row_to_tile_row(self, flat_row_idx: int) -> Tuple[int, int]:
        list_idx = bisect_right(self._nrow_list, flat_row_idx) - 1
        row_offset = self._nrow_list[list_idx]
        obj = self._pat_list[list_idx]
        return obj.flat_row_to_tile_row(flat_row_idx - row_offset)

    def get_sub_pattern_element(self, num_tiles: int, mult: int, mirror: bool, flip: bool,
                                start_idx: int = 0) -> TilePatternElement:
        list_idx = self.get_element_idx(start_idx)
        tile_offset = self._ntile_list[list_idx]
        obj = self._pat_list[list_idx]
        start_idx -= tile_offset
        obj_num_tiles_tot = obj.num_tiles
        obj_num = obj_num_tiles_tot - start_idx
        if obj_num >= num_tiles:
            return obj.get_sub_pattern_element(num_tiles, mult, mirror, flip, start_idx=start_idx)
        ele_list = [obj.get_sub_pattern_element(obj_num, 1, False, False, start_idx=start_idx)]
        num_tiles -= obj_num
        for cur_idx in range(list_idx + 1, len(self._pat_list)):
            obj = self._pat_list[cur_idx]
            cur_num_tot = obj.num_tiles
            if cur_num_tot >= num_tiles:
                ele_list.append(obj.get_sub_pattern_element(num_tiles, 1, False, False))
                break
            else:
                ele_list.append(obj.get_sub_pattern_element(cur_num_tot, 1, False, False))
                num_tiles -= cur_num_tot

        return TilePatternElement(TilePattern(ele_list), mirror=mirror, flip=flip, mult=mult)

    def append_sub_pattern(self, ele_list: List[TilePatternElement], num_tiles: int,
                           flip_pattern: bool) -> None:
        if flip_pattern:
            for obj in reversed(self._pat_list):
                cur_num_tiles = obj.num_tiles
                if num_tiles >= cur_num_tiles:
                    num_tiles -= cur_num_tiles
                    ele_list.append(obj.get_reverse(obj.mult))
                else:
                    if num_tiles > 0:
                        obj.append_sub_pattern(ele_list, num_tiles, True)
                    break
        else:
            for obj in self._pat_list:
                cur_num_tiles = obj.num_tiles
                if num_tiles >= cur_num_tiles:
                    num_tiles -= cur_num_tiles
                    ele_list.append(obj)
                else:
                    if num_tiles > 0:
                        obj.append_sub_pattern(ele_list, num_tiles, False)
                    break


class TileInfoTable:
    """A table storing various compatible tiles."""

    _arr_info_fname = 'arr_info'

    def __init__(self, ainfo: MOSArrayPlaceInfo, pinfo_dict: Mapping[str, MOSBasePlaceInfo]
                 ) -> None:
        self._arr_info = ainfo
        self._pinfo_dict = ImmutableSortedDict(pinfo_dict)
        self._hash = combine_hash(hash(self._arr_info), hash(self._pinfo_dict))

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, rhs: TileInfoTable) -> bool:
        return (isinstance(rhs, TileInfoTable) and self._arr_info == rhs._arr_info and
                self._pinfo_dict == rhs._pinfo_dict)

    def __getitem__(self, name: str) -> MOSBasePlaceInfo:
        return self._pinfo_dict[name]

    @property
    def arr_info(self) -> MOSArrayPlaceInfo:
        return self._arr_info

    @classmethod
    def load(cls, grid: RoutingGrid, root_dir: Path) -> TileInfoTable:
        arr_specs = read_yaml(root_dir / f'{cls._arr_info_fname}.yaml')
        ainfo = MOSArrayPlaceInfo.make_array_info(grid, arr_specs)

        table_specs = read_yaml(root_dir / 'specs.yaml')
        pinfo_specs: Mapping[str, Mapping[str, Any]] = table_specs['place_info']

        pinfo_dict: Dict[str, MOSBasePlaceInfo] = {}
        for name in pinfo_specs.keys():
            if name == cls._arr_info_fname:
                raise ValueError(f'Illegal MOSBasePlaceInfo name: {name}')
            pinfo_yaml = read_yaml(root_dir / f'{name}.yaml')

            rp_list_raw: List[Mapping[str, Any]] = pinfo_yaml['rp_list']
            bot_mirror: bool = pinfo_yaml['bot_mirror']
            top_mirror: bool = pinfo_yaml['top_mirror']
            options: Mapping[str, Any] = pinfo_yaml['options']

            rp_list = ImmutableList([RowPlaceInfo.from_dict(val) for val in rp_list_raw])
            pinfo_dict[name] = MOSBasePlaceInfo(name, ainfo, rp_list, bot_mirror, top_mirror,
                                                ImmutableSortedDict(options))

        return TileInfoTable(ainfo, pinfo_dict)

    @classmethod
    def make_tiles_dir(cls, grid: RoutingGrid, root_dir: Union[str, Path]) -> TileInfoTable:
        """Create a new TileInfoTable from spec file."""
        if isinstance(root_dir, str):
            root_dir = Path(root_dir)

        specs: Mapping[str, Any] = read_yaml(root_dir / 'specs.yaml')
        return TileInfoTable.make_tiles(grid, specs)

    @classmethod
    def make_tiles(cls, grid: RoutingGrid, specs: Mapping[str, Any]) -> TileInfoTable:
        """Create a new TileInfoTable from specification dictionary.

        Tile extension rule:

        1. If a tile does not have mirror placement constraint on its edge, and the other one
           does, then the tile with no mirror placement constraint gets extended.

        2. Otherwise, we extend the tile that has lower priority.

        Parameters
        ----------
        grid : RoutingGrid
            the routing grid object.
        specs : Mapping[str, Any]
            tile specifications dictionary.

        Returns
        -------
        table : TileInfoTable
            a table of all created tiles.
        """
        arr_info: Mapping[str, Any] = specs['arr_info']
        place_info: Mapping[str, Mapping[str, Any]] = specs['place_info']
        abut_list: List[Tuple[Tuple[str, int], Tuple[str, int]]] = specs['abut_list']

        ainfo = MOSArrayPlaceInfo.make_array_info(grid, arr_info)
        pinfo_dict: Dict[str, MOSBasePlaceInfo] = {
            name: make_pinfo_compact_specs(ainfo, name, specs)
            for name, specs in place_info.items()
        }

        for val in abut_list:
            if isinstance(val, Mapping):
                (name1, edge_code1), (name2, edge_code2) = val['edges']
                shared1 = val.get('shared1', [])
                shared2 = val.get('shared2', [])
            else:
                (name1, edge_code1), (name2, edge_code2) = val
                shared1 = shared2 = []

            top_edge1 = bool(edge_code1)
            top_edge2 = bool(edge_code2)
            pinfo1 = pinfo_dict[name1]
            pinfo2 = pinfo_dict[name2]
            margin, ext_w_info, em1, em2 = pinfo1.get_abut_info(pinfo2, top_edge1, top_edge2,
                                                                shared1, shared2)
            if margin > 0:
                # decide which tile to extend
                mirror1 = pinfo1.get_mirror(top_edge1)
                mirror2 = pinfo2.get_mirror(top_edge2)
                if mirror1 == mirror2:
                    # use priority to break ties
                    if pinfo1.extend_priority > pinfo2.extend_priority:
                        ext1 = True
                    elif pinfo2.extend_priority > pinfo1.extend_priority:
                        ext1 = False
                    else:
                        raise ValueError('Cannot decide whether to extend tile '
                                         f'{name1} or {name2}, please set the priority property.')
                elif mirror1:
                    ext1 = False
                else:
                    ext1 = True

                if ext1:
                    pinfo_dict[name1] = pinfo1.get_extend(margin, top_edge1, ext_w_info, em1, em2,
                                                          shared1)
                else:
                    pinfo_dict[name2] = pinfo2.get_extend(margin, top_edge2, ext_w_info, em2, em1,
                                                          shared2)

        # check names of tiles are valid
        for name in pinfo_dict.keys():
            if name == cls._arr_info_fname:
                raise ValueError(f'Illegal MOSBasePlaceInfo name: {name}')

        return TileInfoTable(ainfo, pinfo_dict)

    def save(self, root_dir: Path) -> None:
        arr_fname = root_dir / f'{self._arr_info_fname}.yaml'
        _save_arr_info(self._arr_info, arr_fname)
        for name, pinfo in self._pinfo_dict.items():
            _save_place_info(pinfo, root_dir / f'{name}.yaml')

    def make_place_info(self, val: Mapping[str, Any]) -> Union[MOSBasePlaceInfo, TilePattern]:
        name: str = val.get('name', '')
        if name:
            # return MOSBasePlaceInfo
            return self._pinfo_dict[name]
        else:
            # return TilePattern
            return TilePattern.make_pattern(self._pinfo_dict, val['tiles'])

    def make_tile_pattern(self, tiles: Iterable[Mapping[str, Any]]) -> TilePattern:
        return TilePattern.make_pattern(self._pinfo_dict, tiles)


def _save_arr_info(ainfo: MOSArrayPlaceInfo, fname: Path) -> None:
    tr_widths = ainfo.tr_manager.tr_widths
    tr_spaces = ainfo.tr_manager.tr_spaces

    w_dict = {k: v.to_dict() for k, v in tr_widths.items()}
    s_dict = {k: {a: b.value if isinstance(b, HalfInt) else b for a, b in v.items()}
              for k, v in tr_spaces.items()}
    write_yaml(fname, dict(
        lch=ainfo.lch,
        tr_widths=w_dict,
        tr_spaces=s_dict,
        top_layer=ainfo.top_layer,
        conn_layer=ainfo.conn_layer,
        half_space=ainfo.half_space,
        arr_options=ainfo.arr_options.to_yaml(),
    ))


def _save_place_info(pinfo: MOSBasePlaceInfo, fname: Path) -> None:
    write_yaml(fname, dict(
        rp_list=[pinfo.get_row_place_info(idx).to_dict() for idx in range(pinfo.num_rows)],
        bot_mirror=pinfo.get_mirror(False),
        top_mirror=pinfo.get_mirror(True),
        options=pinfo.tile_options.to_dict(),
        priority=pinfo.extend_priority,
    ))
