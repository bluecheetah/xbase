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

from typing import (
    Tuple, Any, Iterable, List, Optional, Set, Mapping, Dict, Sequence, Union, Callable
)

from dataclasses import dataclass

from networkx import DiGraph, NetworkXUnfeasible
from networkx.algorithms.dag import topological_sort

from pybag.enum import RoundMode, Direction
from pybag.core import COORD_MIN, COORD_MAX

from bag.math import lcm
from bag.util.math import HalfInt
from bag.util.immutable import ImmutableList, ImmutableSortedDict
from bag.layout.routing.base import TrackManager
from bag.layout.routing.grid import RoutingGrid

from .enum import Alignment


class WireLookup:
    def __init__(self, data: Dict[Tuple[str, int], Tuple[HalfInt, int]],
                 ranges: Optional[Dict[str, List[int]]] = None) -> None:
        self._data: ImmutableSortedDict[Tuple[str, int],
                                        Tuple[HalfInt, int]] = ImmutableSortedDict(data)
        if ranges is None:
            self._ranges = {}
            for name, idx in data.keys():
                cur_range = self._ranges.get(name, None)
                if cur_range is None:
                    self._ranges[name] = [idx, idx]
                else:
                    cur_range[0] = min(cur_range[0], idx)
                    cur_range[1] = max(cur_range[1], idx)
        else:
            self._ranges = ranges

    @classmethod
    def from_dict(cls, table: Mapping[Tuple[str, int], Tuple[float, int]]) -> WireLookup:
        data = {key: (HalfInt.convert(val[0]), val[1]) for key, val in table.items()}
        return WireLookup(data)

    def __hash__(self) -> int:
        return hash(self._data)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WireLookup) and self._data == other._data

    def __bool__(self) -> bool:
        return bool(self._data)

    def get_track_info(self, wire_name: str, wire_idx: int) -> Tuple[HalfInt, int]:
        lower, upper = self.get_wire_range(wire_name)

        if wire_idx < 0:
            wire_idx += upper
        if wire_idx < lower or wire_idx >= upper:
            raise ValueError(f'{wire_name}<{wire_idx}> index out of bounds: [{lower}, {upper})')

        return self._data[(wire_name, wire_idx)]

    def get_num_wires(self, wire_name: str) -> int:
        lower, upper = self.get_wire_range(wire_name)
        return upper - lower

    def get_wire_range(self, wire_name: str) -> Tuple[int, int]:
        try:
            lower, upper = self._ranges[wire_name]
            return lower, upper + 1
        except KeyError as err:
            raise KeyError(f'Cannot find wire with basename {wire_name}') from err

    def to_dict(self) -> Mapping[Tuple[str, int], Tuple[float, int]]:
        return {key: [val[0].value, val[1]] for key, val in self._data.items()}

    def get_wire_margin_info(self, grid: RoutingGrid, layer: int, yl: int, yh: int, top_edge: bool,
                             shared: Sequence[str]) -> Tuple[int, List[Tuple[str, int]]]:
        shared_set = _get_shared_set(shared)
        ans = []
        y_conn = yl if top_edge else yh
        for name_tuple, (tidx, width) in self._data.items():
            if name_tuple in shared_set:
                continue

            coord = grid.track_to_coord(layer, tidx)
            margin = yh - coord if top_edge else coord - yl
            ans.append((name_tuple[0], margin))

            via_ext = grid.get_via_extensions(Direction.UPPER, layer, width, 1)[0]
            wl, wu = grid.get_wire_bounds(layer, tidx, width)
            if top_edge:
                y_conn = max(y_conn, wu + via_ext)
            else:
                y_conn = min(y_conn, wl - via_ext)

        y_conn_margin = yh - y_conn if top_edge else y_conn - yl
        return y_conn_margin, ans

    def get_move(self, tr_idx: HalfInt, shared: Sequence[str]) -> WireLookup:
        shared_set = _get_shared_set(shared)
        new_data = {}
        for name_tuple, (tidx, width) in self._data.items():
            if name_tuple in shared_set:
                new_data[name_tuple] = (tidx, width)
            else:
                new_data[name_tuple] = (tidx + tr_idx, width)
        return WireLookup(new_data, ranges=self._ranges)

    def get_move_shared(self, tr_idx: HalfInt, shared: Sequence[str]) -> WireLookup:
        new_data = self._data.to_dict()
        for name in shared:
            basename, idx_list = _parse_cdba_name(name)
            for idx in idx_list:
                key = (name, idx)
                val = new_data.get(key, None)
                if val is not None:
                    new_data[key] = (val[0] + tr_idx, val[1])
        return WireLookup(new_data, ranges=self._ranges)


@dataclass(eq=True, frozen=True)
class WireData:
    wire_grps: ImmutableList[Tuple[ImmutableList[Tuple[str, str, str]], Alignment]]
    shared_wires: ImmutableList[str]

    @classmethod
    def make_wire_data(cls, wire_data: Any, alignment: Alignment, ptype_default: str) -> WireData:
        """Construct WireData from given data structure.

        wire_data format:

        WireData = Optional[Union[WireGraph, {data=WireGraph, align=Alignment, shared=List[str]}]]
        WireGraph = Union[WireGroup, List[WireGroup]]
        WireGroup = Union[WireList, {wires=WireList, align=Alignment}]
        WireList = List[Wire]
        Wire = Union[name, (name, placement_type), (name, placement_type, wire_type)]

        Parameters
        ----------
        wire_data : Any
            the wire graph specification data structure.
        alignment : Alignment
            default alignment.
        ptype_default : str
            default placement type.

        Returns
        -------
        wire_data : WireData
            the wire graph specification dataclass.
        """
        if isinstance(wire_data, Mapping):
            actual_data = wire_data['data']
            alignment = Alignment[wire_data.get('align', alignment.name)]
            shared_wires = wire_data.get('shared', [])
        else:
            actual_data = wire_data
            shared_wires = []

        wire_grps = []
        for wire_grp, align in _wire_list_iter(actual_data, alignment):
            wire_list = []
            for winfo in wire_grp:
                if isinstance(winfo, str):
                    name = winfo
                    wtype = ''
                    ptype = ptype_default
                else:
                    name: str = winfo[0]
                    ptype: str = winfo[1]
                    wtype: str = '' if len(winfo) < 3 else winfo[2]
                    if not ptype:
                        ptype = ptype_default
                wire_list.append((name, ptype, wtype))
            wire_grps.append((ImmutableList(wire_list), align))

        return WireData(ImmutableList(wire_grps), ImmutableList(shared_wires))


class WireGraph:
    def __init__(self, graph: DiGraph, align_specs: List[Tuple[List[Tuple[str, int]], Alignment]],
                 has_center: bool) -> None:
        self._graph = graph
        self._align_specs = align_specs
        self._has_center = has_center
        self._lower = COORD_MAX
        self._upper = COORD_MIN

    def __bool__(self) -> bool:
        return len(self._graph) != 0

    @classmethod
    def make_wire_graph(cls, layer: int, tr_manager: TrackManager, wire_data: WireData
                        ) -> WireGraph:
        builder = WireGraphBuilder()
        for wire_grp, align in wire_data.wire_grps:
            builder.register_wires(wire_grp, align)

        for wire_name in wire_data.shared_wires:
            builder.register_shared_wire(wire_name)

        ans = builder.get_graph(layer, tr_manager)
        return ans

    @property
    def graph(self) -> DiGraph:
        return self._graph

    @property
    def has_center(self) -> bool:
        return self._has_center

    @property
    def upper(self) -> int:
        return self._upper

    @property
    def lower(self) -> int:
        return self._lower

    @property
    def sinks(self) -> List[Tuple[HalfInt, str]]:
        # NOTE: pycharm typehint bug
        # noinspection PyCallingNonCallable
        return [(attrs['idx'], attrs['wtype'])
                for key, attrs in self._graph.nodes.items() if self._graph.out_degree(key) == 0]

    def get_wire_lookup(self) -> WireLookup:
        return WireLookup({key: (attrs['idx'], attrs['width'])
                           for key, attrs in self._graph.nodes.items()})

    def get_placement_bounds(self, layer: int, grid: RoutingGrid,
                             inc_shared: bool = True) -> Dict[str, List[Tuple[HalfInt, int]]]:
        ans = {}
        for key, attrs in self._graph.nodes.items():
            if attrs['shared'] and not inc_shared:
                continue

            ptype: str = attrs['ptype']
            cur_info = (attrs['idx'], attrs['width'])

            cur_bnds = ans.get(ptype, None)
            if cur_bnds is None:
                ans[ptype] = [cur_info, cur_info]
            else:
                lower, upper = grid.get_wire_bounds(layer, cur_info[0], width=cur_info[1])
                cur_lower = grid.get_wire_bounds(layer, cur_bnds[0][0], width=cur_bnds[0][1])[0]
                cur_upper = grid.get_wire_bounds(layer, cur_bnds[1][0], width=cur_bnds[1][1])[1]
                if lower < cur_lower:
                    cur_bnds[0] = cur_info
                if upper > cur_upper:
                    cur_bnds[1] = cur_info

        return ans

    def get_shared_conn_y(self, layer: int, grid: RoutingGrid, top_edge: bool) -> int:
        ans = COORD_MAX if top_edge else COORD_MIN
        for wire, attrs in self._graph.nodes.items():
            # NOTE: pycharm typehint bug
            # noinspection PyCallingNonCallable
            is_sink = (self._graph.out_degree(wire) == 0)
            if attrs['shared'] and is_sink == top_edge:
                ntr = attrs['width']
                vext = grid.get_via_extensions(Direction.UPPER, layer, ntr, 1)[0]
                wl, wu = grid.get_wire_bounds(layer, attrs['idx'], width=ntr)
                if top_edge:
                    ans = min(ans, wl - vext)
                else:
                    ans = max(ans, wu + vext)
        return ans

    def set_upper(self, layer: int, tr_manager: TrackManager, val: int) -> None:
        grid = tr_manager.grid
        
        tr_last = grid.coord_to_track(layer, val, mode=RoundMode.LESS_EQ)
        new_val = grid.track_to_coord(layer, tr_last)
        if new_val < self._upper:
            raise ValueError(f'set_upper cannot reduce upper bound from {self._upper} to {new_val}')
        self._upper = new_val
        for wire, attrs in self._graph.nodes.items():
            # NOTE: pycharm typehint bug
            # noinspection PyCallingNonCallable
            if attrs['shared'] and self._graph.out_degree(wire) == 0:
                attrs['idx'] = tr_last

    def place_compact(self, layer: int, tr_manager: TrackManager, lower: int = 0,
                      bot_mirror: bool = False, top_mirror: bool = False,
                      shift: Union[int, HalfInt] = 0,
                      pcons: Optional[Callable[[str, int, HalfInt], HalfInt]] = None,
                      prev_wg: Optional[WireGraph] = None, ytop_conn: Optional[int] = None) -> None:
        """Place wires in this WireGraph, trying to be as compact as possible.

        Algorithm:

        1. First, go through all wires in sorted order, and compute placement.
           For source wires, use the following algorithm:

           i.   If it is shared, place at boundary.
           ii.  Otherwise, if bot_mirror is True, place it so that it will be DRC clean
                with itself.
           iii. Finally, if prev_wg is given, make sure it is DRC clean from all the sink wires
                in prev_wg.

        2. After step 1, if we have more than 1 source wires (say A and B), we could still fail
           DRC rules, because we only made sure A next to A is clean and B next to B is clean,
           but we're not guaranteed A next to B is clean.  We check for and fix this violation
           (NOTE: not implemented yet).

        3. Then, we go through all the sink wires, and compute the upper coordinate of this
           WireGraph as follows:

           i.   If the sink wire is shared, record the middle coordinate.
           ii.  Otherwise, if top_mirror is True, set the upper coordinate so that this wire
                will be DRC clean to all other non-shared wires.
           iii. Finally, make sure upper coordinate is greater than or equal to the upper edge of
                this wire.

        4. Finally, we find all shared sink wires, and update so they lie on the boundary.

        Parameters
        ----------
        layer : int
            wire layer ID.
        tr_manager : TrackManager
            the TrackManager object.
        lower : int
            the lower coordinate.
        bot_mirror : bool
            True if the bottom edge should satisfy mirror placement constraint.
        top_mirror : bool
            True if the top edge should satisfy mirror placement constraint.
        shift: Union[int, Halfint]
            shift all wires track index by this amount.
        pcons : Optional[Callable[[str, int, HalfInt], HalfInt]]
            An optional function used to compute track location based on placement constraint.
        prev_wg : Optional[WireGraph]
            The WireGraph object just below this one.
        ytop_conn : Optional[int]
            top Y coordinate of the bottom vertical wire.
        """
        grid = tr_manager.grid
        node_view = self._graph.nodes
        empty_set = set()
        tr0 = grid.coord_to_track(layer, lower)
        prev_sinks: List[Tuple[HalfInt, str]] = [] if prev_wg is None else prev_wg.sinks

        # compute wire placement
        src_list = []
        sink_list = []
        conn_sp_le = grid.get_line_end_space(layer - 1, 1, even=False)
        try:
            for key in topological_sort(self._graph):
                cur_attrs = node_view[key]
                wtype: str = cur_attrs['wtype']
                ptype: str = cur_attrs['ptype']
                tr_w: int = cur_attrs['width']
                shared: bool = cur_attrs['shared']
                even_set: Optional[Set[Tuple[str, int]]] = cur_attrs['even_spaces']
                if even_set is None:
                    even_set = empty_set

                cur_idx = grid.find_next_track(layer, lower, tr_width=tr_w,
                                               half_track=True, mode=RoundMode.GREATER_EQ)
                if pcons is not None:
                    cur_idx = pcons(ptype, tr_w, cur_idx)
                # NOTE: pycharm typehint bug
                # noinspection PyCallingNonCallable
                is_sink = (self._graph.out_degree(key) == 0)
                if is_sink:
                    sink_list.append(key)
                # NOTE: pycharm typehint bug
                # noinspection PyCallingNonCallable
                if self._graph.in_degree(key) == 0:
                    src_list.append(key)
                    if shared:
                        cur_idx = tr0
                    else:
                        for prev_idx, prev_wtype in prev_sinks:
                            min_idx = tr_manager.get_next_track(layer, prev_idx, prev_wtype,
                                                                wtype, up=True)
                            cur_idx = max(cur_idx, min_idx)

                        if bot_mirror:
                            # set root starting index so we satisfy self-mirror constraint
                            sep = tr_manager.get_sep(layer, (wtype, wtype), same_color=True,
                                                     half_space=False)
                            cur_idx = max(cur_idx, sep.div2())

                        cur_idx += shift
                else:
                    if is_sink and shared and ytop_conn is not None:
                        # handle line-end spacing between ytop_conn and wires from above connected
                        # to this shared wire.
                        vext = grid.get_via_extensions(Direction.UPPER, layer, tr_w, 1)[0]
                        min_yl = ytop_conn + conn_sp_le + vext
                        cur_idx = max(cur_idx, grid.find_next_track(layer, min_yl, tr_width=tr_w,
                                                                    mode=RoundMode.GREATER_EQ))
                    for parent in self._graph.predecessors(key):
                        par_attrs = node_view[parent]
                        par_idx: HalfInt = par_attrs['idx']
                        par_type: str = par_attrs['wtype']

                        half_space = parent not in even_set
                        min_idx = tr_manager.get_next_track(layer, par_idx, par_type, wtype,
                                                            half_space=half_space)
                        cur_idx = max(cur_idx, min_idx)

                cur_attrs['idx'] = cur_idx

        except NetworkXUnfeasible:
            raise ValueError('dependency loop detected.  Cannot place wires.')

        if bot_mirror:
            # check that we satisfy bottom edge mirror placement constraint
            # first, get all violations
            num_src = len(src_list)
            violations = []
            move_set = set()
            for ni in range(num_src):
                wire_i = src_list[ni]
                attrs_i = node_view[wire_i]
                if attrs_i['shared']:
                    continue
                idx_i = attrs_i['idx']
                wtype_i = attrs_i['wtype']
                for nj in range(ni + 1, num_src):
                    wire_j = src_list[nj]
                    attrs_j = node_view[wire_j]
                    if attrs_j['shared']:
                        continue
                    idx_j = attrs_i['idx']
                    wtype_j = attrs_j['wtype']

                    sep = tr_manager.get_sep(layer, (wtype_i, wtype_j), same_color=True,
                                             half_space=True)
                    if idx_i + idx_j + 1 < sep:
                        # violation found
                        move_set.add(wire_i)
                        move_set.add(wire_j)
                        violations.append((wire_i, wire_j))

            if violations:
                # TODO: finish implementing this.
                # outline:
                # 1. for each source in violation, get number of tracks it can move up without
                #    changing total size
                # 2. for each violation, if we can move sources in such a way to not change total
                #    size, move them that way
                # 3. otherwise, move in a way to minimize the total size
                raise ValueError('lazy Eric, get to work')

        # compute upper coordinate
        upper = lower
        upper_is_shared = False
        num_sinks = len(sink_list)
        tr_pitch = grid.get_track_pitch(layer)
        for sink_idx, sink in enumerate(sink_list):
            cur_attrs = node_view[sink]
            tr_w: int = cur_attrs['width']
            shared: bool = cur_attrs['shared']
            cur_idx: HalfInt = cur_attrs['idx']

            # update upper most coordinate
            if shared:
                mid_c = grid.track_to_coord(layer, cur_idx)
                if mid_c >= upper:
                    upper = mid_c
                    upper_is_shared = True
            else:
                bnd_c = grid.get_wire_bounds(layer, cur_idx, width=tr_w)[1]
                if top_mirror:
                    wtype: str = cur_attrs['wtype']
                    for comp_sink_idx in range(sink_idx, num_sinks):
                        comp_attrs = node_view[sink_list[comp_sink_idx]]
                        comp_shared: bool = comp_attrs['shared']
                        comp_wtype: str = comp_attrs['wtype']
                        comp_idx: HalfInt = comp_attrs['idx']
                        if not comp_shared:
                            # TODO: pessimistic spacing rule, figure out coloring?
                            sep = tr_manager.get_sep(layer, (wtype, comp_wtype), same_color=True,
                                                     half_space=True)
                            ntr_dbl = sep + cur_idx + comp_idx
                            bnd_c = max(bnd_c, -(-int(ntr_dbl * tr_pitch) // 2))

                if bnd_c > upper:
                    upper = bnd_c
                    upper_is_shared = False

        if not upper_is_shared:
            # if upper coordinate is not set by shared wire, we need to update upper coordinate
            # so it is on track
            upper = grid.track_to_coord(layer, grid.find_next_track(layer, upper, half_track=True,
                                                                    mode=RoundMode.GREATER_EQ))
        self._lower = lower
        self._upper = upper

        # move upper shared wires
        tr_last = grid.coord_to_track(layer, self._upper)
        for wire in sink_list:
            attrs = node_view[wire]
            # NOTE: pycharm typehint bug
            # noinspection PyCallingNonCallable
            if attrs['shared'] and self._graph.out_degree(wire) == 0:
                attrs['idx'] = tr_last

    def align_wires(self, layer: int, tr_manager: TrackManager, lower: int, upper: int,
                    top_pcons: Optional[Callable[[str, int, HalfInt], HalfInt]] = None) -> None:
        grid = tr_manager.grid
        node_view = self._graph.nodes

        for key, attrs in node_view.items():
            attrs['harden'] = False

        # align all wires given area
        middle_idx = grid.coord_to_track(layer, (lower + upper) // 2, mode=RoundMode.NEAREST)
        for wire_list, alignment in self._align_specs:
            if alignment is Alignment.LOWER_COMPACT:
                for wire in wire_list:
                    self._move(layer, tr_manager, lower, upper, wire, top_pcons, True, False)
            elif alignment is Alignment.UPPER_COMPACT:
                for wire in reversed(wire_list):
                    self._move(layer, tr_manager, lower, upper, wire, top_pcons, True, True)
            elif alignment is Alignment.CENTER_COMPACT:
                # check if some wires are hardened already
                hard_idx_list = [idx for idx, wire in enumerate(wire_list)
                                 if node_view[wire]['harden']]
                num_hard = len(hard_idx_list)
                if num_hard > 0:
                    # get "middle" hardened wire, for all wires below, move up,
                    # for all wires above, move down
                    center_idx = hard_idx_list[num_hard // 2]
                    for idx in range(center_idx - 1, -1, -1):
                        self._move(layer, tr_manager, lower, upper, wire_list[idx], top_pcons,
                                   True, True)
                    for idx in range(center_idx + 1, len(wire_list)):
                        self._move(layer, tr_manager, lower, upper, wire_list[idx], top_pcons,
                                   True, False)
                else:
                    # center entire group
                    cur_idx = grid.get_middle_track(node_view[wire_list[0]]['idx'],
                                                    node_view[wire_list[-1]]['idx'])
                    delta = middle_idx - cur_idx
                    # TODO: this is broken, need to fix it.
                    # we need to figure out the maximum delta we can move this group by,
                    # and cap delta by that number.
                    for wire in wire_list:
                        attrs = node_view[wire]
                        attrs['idx'] += delta
                        attrs['harden'] = True
            else:
                raise ValueError(f'Unsupported alignment: {alignment.name}')

        self._lower = lower
        self._upper = upper

    def _move(self, layer: int, tr_manager: TrackManager, lower: int, upper, wire: Tuple[str, int],
              top_pcons: Optional[Callable[[str, int, HalfInt], HalfInt]], harden: bool, up: bool
              ) -> None:
        node_view = self._graph.nodes
        attrs = node_view[wire]

        if not attrs['harden']:
            grid = tr_manager.grid

            wtype: str = attrs['wtype']
            ptype: str = attrs['ptype']
            tr_w: int = attrs['width']
            shared: bool = attrs['shared']
            even_set: Optional[Set[Tuple[str, int]]] = attrs['even_spaces']

            if shared:
                # snap boundary shared wires to edges
                # NOTE: pycharm typehint bug
                # noinspection PyCallingNonCallable
                if self._graph.out_degree(wire) == 0:
                    cur_idx = grid.coord_to_track(layer, upper)
                else:
                    cur_idx = grid.coord_to_track(layer, lower)
                attrs['idx'] = cur_idx
                attrs['harden'] = True
            else:
                if up:
                    cur_idx = grid.find_next_track(layer, upper, tr_width=tr_w, half_track=True,
                                                   mode=RoundMode.LESS_EQ)
                    if top_pcons is not None:
                        cur_idx = top_pcons(ptype, tr_w, cur_idx)
                    node_iter = self._graph.successors(wire)
                    fun = min
                else:
                    cur_idx = grid.find_next_track(layer, lower, tr_width=tr_w, half_track=True,
                                                   mode=RoundMode.GREATER_EQ)
                    node_iter = self._graph.predecessors(wire)
                    fun = max
                for node in node_iter:
                    self._move(layer, tr_manager, lower, upper, node, top_pcons, False, up)
                    node_attrs = node_view[node]
                    node_type: str = node_attrs['wtype']
                    node_idx: HalfInt = node_attrs['idx']
                    if up:
                        eset = node_attrs['even_spaces']
                        half_space = eset is None or wire not in eset
                    else:
                        half_space = even_set is None or node not in even_set
                    next_idx = tr_manager.get_next_track(layer, node_idx, node_type, wtype,
                                                         half_space=half_space, up=not up)

                    cur_idx = fun(cur_idx, next_idx)

                attrs['idx'] = cur_idx
                attrs['harden'] = harden


class WireGraphBuilder:
    def __init__(self) -> None:
        self._graph = DiGraph()
        self._align_specs: List[Tuple[List[Tuple[str, int]], Alignment]] = []
        self._has_center = False

    def register_wires(self, winfo_list: Sequence[Tuple[str, str, str]], alignment: Alignment
                       ) -> None:
        """Adds the given list of wires to the WireGraph.

        Parameters
        ----------
        winfo_list : Sequence[Tuple[str, str, str]]
            list of wires, described by WireList above.
        alignment: Alignment
            alignment of the given wires.
        """
        if winfo_list:
            self._has_center = self._has_center or alignment.is_center

            prev_wire = None
            wire_list: List[Tuple[str, int]] = []
            for name, ptype, wtype in winfo_list:
                basename, idx_range = _parse_cdba_name(name)
                if not wtype:
                    wtype = basename

                for idx in idx_range:
                    wire = (basename, idx)
                    wire_list.append(wire)
                    if wire not in self._graph:
                        # register new wire
                        self._graph.add_node(wire, idx=None, wtype=wtype, ptype=ptype, shared=False,
                                             harden=False, even_spaces=None)
                    if prev_wire is not None:
                        self._graph.add_edge(prev_wire, wire)
                    prev_wire = wire

            if wire_list:
                num_wires = len(wire_list)
                if (alignment.is_center and num_wires & 1 == 0 and
                        self._is_even_symmetric(wire_list)):
                    # make sure middle spacing is even
                    nhalf = num_wires // 2
                    attrs = self._graph.nodes[wire_list[nhalf]]
                    even_spaces: Optional[Set[Tuple[str, int]]] = attrs['even_spaces']
                    if even_spaces is None:
                        attrs['even_spaces'] = {wire_list[nhalf - 1]}
                    else:
                        even_spaces.add(wire_list[nhalf - 1])

                self._align_specs.append((wire_list, alignment))

    def register_shared_wire(self, wire_name: str) -> None:
        basename, idx_range = _parse_cdba_name(wire_name)
        if len(idx_range) > 1:
            raise ValueError('Cannot register bus as shared wires.')

        idx = idx_range[0]
        cur_wire = (basename, idx)
        cur_attrs = self._graph.nodes.get(cur_wire, None)
        if cur_attrs is None:
            raise ValueError(f'Cannot find shared wire: {basename}<{idx}>')
        # NOTE: pycharm typehint bug
        # noinspection PyCallingNonCallable
        if (self._graph.in_degree(cur_wire) == 0) == (self._graph.out_degree(cur_wire) == 0):
            raise ValueError(f'shared wire {basename}<{idx}> is not on the boundary.')

        cur_attrs['shared'] = True

    def get_graph(self, layer: int, tr_manager: TrackManager) -> WireGraph:
        for _, attrs in self._graph.nodes.items():
            attrs['width'] = tr_manager.get_width(layer, attrs['wtype'])
        return WireGraph(self._graph, self._align_specs, self._has_center)

    def _is_even_symmetric(self, wlist: List[Tuple[str, int]]) -> bool:
        num = len(wlist)
        for idx in range(0, num // 2):
            if (self._graph.nodes[wlist[idx]]['wtype'] !=
                    self._graph.nodes[wlist[num - 1 - idx]]['wtype']):
                return False
        return True


@dataclass
class WireSpecs:
    min_size: Tuple[int, int]
    blk_size: Tuple[int, int]
    graph_list: List[Tuple[int, WireGraph]]

    def place_wires(self, tr_manager: TrackManager, w: int, h: int) -> Dict[int, WireLookup]:
        grid = tr_manager.grid

        ans = {}
        for cur_layer, graph in self.graph_list:
            dim = h if grid.is_horizontal(cur_layer) else w
            graph.align_wires(cur_layer, tr_manager, 0, dim)
            ans[cur_layer] = graph.get_wire_lookup()

        return ans

    @classmethod
    def make_wire_specs(cls, conn_layer: int, top_layer: int, tr_manager: TrackManager,
                        wire_specs: Mapping[int, Any], min_size: Tuple[int, int] = (1, 1),
                        blk_pitch: Tuple[int, int] = (1, 1),
                        align_default: Alignment = Alignment.LOWER_COMPACT,
                        ptype_default: str = '') -> WireSpecs:
        """Read wire specifications from a dictionary.

        WireSpec dictionary format:

        WireSpec = Dict[int, WireData]
        WireData = Union[WireGraph, {data=WireGraph, align=Alignment, shared=List[str]}]
        WireGraph = Union[WireGroup, List[WireGroup]]
        WireGroup = Union[WireList, {wires=WireList, align=Alignment}]
        WireList = List[Wire]
        Wire = Union[name, (name, placement_type), (name, placement_type, wire_type)]

        keys of WireSpec is delta layer from conn_layer, so key of 1 is the same as conn_layer + 1.

        Parameters
        ----------
        conn_layer : int
            the connection layer ID.
        top_layer : int
            the top layer, used to compute block quantization.
        tr_manager : TrackManager
            the TrackManager instance.
        wire_specs : Mapping[int, Any]
            the wire specification dictionary to parse.
        min_size : Tuple[int, int]
            minimum width/height.
        blk_pitch : Tuple[int, int]
            width/height quantization on top of routing grid quantization.
        align_default : Alignment
            default alignment enum.
        ptype_default : str
            default placement type.

        Returns
        -------
        wire_specs : WireSpecs
            the wire specification dataclass.
        """
        w_min, h_min = min_size
        blk_w_res, blk_h_res = blk_pitch

        grid = tr_manager.grid

        half_blk_x = half_blk_y = True
        graph_list = []
        for delta_layer, wire_data in wire_specs.items():
            cur_layer = conn_layer + delta_layer
            wd = WireData.make_wire_data(wire_data, align_default, ptype_default)
            cur_graph = WireGraph.make_wire_graph(cur_layer, tr_manager, wd)
            cur_graph.place_compact(cur_layer, tr_manager)
            graph_list.append((cur_layer, cur_graph))
            if grid.is_horizontal(cur_layer):
                half_blk_y = half_blk_y and not cur_graph.has_center
                h_min = max(h_min, cur_graph.upper)
            else:
                half_blk_x = half_blk_x and not cur_graph.has_center
                w_min = max(w_min, cur_graph.upper)

        blk_w, blk_h = grid.get_block_size(top_layer, half_blk_x=half_blk_x, half_blk_y=half_blk_y)
        blk_w = lcm([blk_w, blk_w_res])
        blk_h = lcm([blk_h, blk_h_res])

        w_min = -(-w_min // blk_w) * blk_w
        h_min = -(-h_min // blk_h) * blk_h
        return WireSpecs((w_min, h_min), (blk_w, blk_h), graph_list)


def _parse_cdba_name(name: str) -> Tuple[str, Sequence[int]]:
    if not name:
        raise ValueError(f'Cannot have empty string as wire name.')

    if name[-1] == '>':
        idx = name.find('<')
        if idx < 0:
            raise ValueError(f'Illegal name: {name}')
        basename = name[:idx]
        if ':' in basename:
            raise ValueError(f'Illegal name: {name}')

        range_list = name[idx + 1:-1].split(':')
        num = len(range_list)
        try:
            start = int(range_list[0])
            if num == 1:
                stop = start
                step = 1
            else:
                stop = int(range_list[1])
                if num == 2:
                    step = 2 * (stop > start) - 1
                else:
                    step = int(range_list[2])
        except ValueError:
            raise ValueError(f'Illegal name: {name}')

        num = (stop - start) // step + 1
        return basename, range(start, start + num * step, step)
    else:
        if '<' in name or ':' in name:
            raise ValueError(f'Illegal name: {name}')
        return name, range(0, 1, 1)


def _is_wire_info(obj: Any) -> bool:
    if isinstance(obj, str):
        return True
    if not hasattr(obj, '__len__') or not hasattr(obj, '__iter__'):
        return False
    num = len(obj)
    if num == 2 or num == 3:
        for v in obj:
            if not isinstance(v, str):
                return False
        return True
    else:
        return False


def _wire_list_iter(wgraph: Any, align_default: Alignment) -> Iterable[List[Any], Alignment]:
    """Iterates over wire lists in the given wire graph.

    wgraph format:

    WireGraph = Union[WireGroup, List[WireGroup]]
    WireGroup = Union[WireList, {wires=WireList, align=Alignment}]
    WireList = List[Wire]
    Wire = Union[name, (name, placement_type), (name, placement_type, wire_type)]

    Parameters
    ----------
    wgraph : Any
        the wire graph data structure.
    align_default : Alignment
        default alignment enum.

    Yields
    ------
    wire_list : List[any]
        a list of wires inside the wire graph.
    align : Alignment
        alignment of this list of wires.
    """
    if wgraph:
        if isinstance(wgraph, Mapping):
            # wgraph is a WireGroup with contains alignment information
            yield wgraph['wires'], wgraph.get('align', align_default)
        elif _is_wire_info(wgraph[0]):
            # wgraph is a WireList
            yield wgraph, align_default
        else:
            # actual_data is a list of WireGroups
            for wire_grp in wgraph:
                if isinstance(wire_grp, Mapping):
                    yield wire_grp['wires'], wire_grp.get('align', align_default)
                else:
                    yield wire_grp, align_default


def _get_shared_set(shared: Sequence[str]) -> Set[Tuple[str, int]]:
    shared_set = set()
    for name in shared:
        basename, idx_list = _parse_cdba_name(name)
        for idx in idx_list:
            shared_set.add((name, idx))

    return shared_set
