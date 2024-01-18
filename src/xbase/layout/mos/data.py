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

from typing import Any, Tuple, Optional, Mapping, Sequence

from dataclasses import dataclass, field
from bisect import bisect_left

from bag.util.math import HalfInt
from bag.util.immutable import ImmutableSortedDict, ImmutableList
from bag.layout.routing.base import WireArray, TrackManager

from ..data import LayoutInfo
from ..wires import WireData, WireLookup
from ..enum import MOSType, MOSWireType, MOSPortType, Alignment


@dataclass(eq=True, frozen=True, init=False)
class MOSRowSpecs:
    """specification for a transistor row. Includes unit transistor dimensions and wire info
    for determining track locations on conn_layer + 1"""
    mos_type: MOSType
    width: int
    threshold: str
    bot_wires: WireData
    mid_wires: WireData
    top_wires: WireData
    options: ImmutableSortedDict[str, Any]
    flip: bool
    sub_width: int
    double_gate: bool

    def __init__(self, mos_type: MOSType, width: int, threshold: str,
                 bot_wires: WireData, top_wires: WireData, mid_wires: Optional[WireData] = None,
                 options: Optional[Mapping[str, Any]] = None,
                 flip: bool = False, sub_width: int = 0, double_gate: bool = False) -> None:
        if sub_width == 0 or mos_type.is_substrate:
            sub_width = width

        # work around: this is how you set attributes for frozen data classes
        object.__setattr__(self, 'mos_type', mos_type)
        object.__setattr__(self, 'width', width)
        object.__setattr__(self, 'threshold', threshold)
        object.__setattr__(self, 'bot_wires', bot_wires)
        object.__setattr__(self, 'mid_wires', mid_wires)
        object.__setattr__(self, 'top_wires', top_wires)
        object.__setattr__(self, 'options', ImmutableSortedDict(options))
        object.__setattr__(self, 'flip', flip)
        object.__setattr__(self, 'sub_width', sub_width)
        object.__setattr__(self, 'double_gate', double_gate)

    @classmethod
    def make_row_specs(cls, val: Mapping[str, Any]) -> MOSRowSpecs:
        mos_type = MOSType[val['mos_type']]
        width = val['width']
        threshold = val['threshold']
        bot_wires = val['bot_wires']
        mid_wires = val.get('mid_wires')
        top_wires = val['top_wires']
        options = val.get('options', None)
        flip = val.get('flip', False)
        sub_width = val.get('sub_width', 0)
        double_gate = val.get('double_gate', False)

        if double_gate:
            ds_type = MOSWireType.DS.name
            g_type = MOSWireType.G.name
            g2_type = MOSWireType.G2.name
            bot_wd = WireData.make_wire_data(bot_wires, Alignment.UPPER_COMPACT, g2_type if flip else g_type)
            mid_wd = WireData.make_wire_data(mid_wires, Alignment.CENTER_COMPACT, ds_type)
            top_wd = WireData.make_wire_data(top_wires, Alignment.LOWER_COMPACT, g_type if flip else g2_type)
            return MOSRowSpecs(mos_type, width, threshold, bot_wd, top_wd, mid_wires=mid_wd,
                               options=options, flip=flip, sub_width=sub_width, double_gate=double_gate)
        else:
            ds_type = MOSWireType.DS_GATE.name
            g_type = MOSWireType.G.name
            if flip:
                bot_ptype = ds_type
                top_ptype = g_type
            else:
                bot_ptype = g_type
                top_ptype = ds_type
            bot_wd = WireData.make_wire_data(bot_wires, Alignment.UPPER_COMPACT, bot_ptype)
            mid_wd = WireData.make_wire_data({'data': []}, Alignment.CENTER_COMPACT, bot_ptype)
            top_wd = WireData.make_wire_data(top_wires, Alignment.LOWER_COMPACT, top_ptype)
            return MOSRowSpecs(mos_type, width, threshold, bot_wd, top_wd, mid_wires=mid_wd,
                               options=options, flip=flip, sub_width=sub_width, double_gate=double_gate)

    @property
    def ignore_bot_vm_sp_le(self) -> bool:
        return self.options.get('ignore_bot_vm_sp_le', False)

    @property
    def ignore_top_vm_sp_le(self) -> bool:
        return self.options.get('ignore_top_vm_sp_le', False)


@dataclass(eq=True, frozen=True)
class RowExtInfo:
    """Information about top or bottom boundary of a transistor block.

    This class contains information needed to draw an extension region adjacent to the
    transistor row.
    """
    row_type: MOSType
    threshold: str
    info: ImmutableSortedDict[str, Any]

    @classmethod
    def from_dict(cls, table: Mapping[str, Any]) -> RowExtInfo:
        return RowExtInfo(MOSType[table['row_type']], table['threshold'],
                          ImmutableSortedDict(table['info']))

    def __getitem__(self, item: str) -> Any:
        return self.info[item]

    def get(self, item: str, def_val: Optional[Any] = None) -> Any:
        return self.info.get(item, def_val)

    def copy_with(self, row_type: Optional[MOSType] = None, threshold: Optional[str] = None,
                  **kwargs) -> RowExtInfo:
        if row_type is None:
            row_type = self.row_type
        if threshold is None:
            threshold = self.threshold
        info_dict = self.info.to_dict()
        info_dict.update(kwargs)
        return RowExtInfo(row_type, threshold, ImmutableSortedDict(info_dict))

    def to_dict(self) -> Mapping[str, Any]:
        return dict(
            row_type=self.row_type.name,
            threshold=self.threshold,
            info=self.info.to_yaml(),
        )


@dataclass(eq=True, frozen=True)
class BlkExtInfo:
    """Information about top or bottom boundary of a transistor row"""
    row_type: MOSType
    threshold: str
    guard_ring: bool
    fg_dev: ImmutableList[Tuple[int, MOSType]]
    info: ImmutableSortedDict[str, Any]

    def __getitem__(self, item: str) -> Any:
        return self.info[item]

    def __contains__(self, item: str) -> bool:
        return item in self.info

    @property
    def fg(self) -> int:
        return sum((val[0] for val in self.fg_dev))

    def get(self, item: str, def_val: Optional[Any] = None) -> Any:
        return self.info.get(item, def_val)


@dataclass(eq=True, frozen=True, init=False)
class MOSEdgeInfo:
    """Information about left or right boundary of a transistor row.
    """
    info: ImmutableSortedDict[str, Any]

    def __init__(self, **kwargs: Any) -> None:
        object.__setattr__(self, 'info', ImmutableSortedDict(kwargs))

    def __bool__(self) -> bool:
        return bool(self.info)

    def get(self, item: str, def_val: Optional[Any] = None) -> Any:
        return self.info.get(item, def_val)

    def __getitem__(self, item: str) -> Any:
        return self.info[item]

    def copy_with(self, **kwargs) -> MOSEdgeInfo:
        info_dict = self.info.to_dict()
        info_dict.update(kwargs)
        return MOSEdgeInfo(**info_dict)


@dataclass(eq=True, frozen=True)
class MOSRowInfo:
    """Information about a transistor row."""
    lch: int
    width: int
    sub_width: int
    row_type: MOSType
    threshold: str
    height: int
    flip: bool
    top_ext_info: RowExtInfo
    bot_ext_info: RowExtInfo
    info: ImmutableSortedDict[str, Any]
    # yt, yb for each connection
    g_conn_y: Tuple[int, int] = (0, 0)
    g_m_conn_y: Tuple[int, int] = (0, 0)
    ds_conn_y: Tuple[int, int] = (0, 0)
    ds_m_conn_y: Tuple[int, int] = (0, 0)
    ds_g_conn_y: Tuple[int, int] = (0, 0)
    sub_conn_y: Tuple[int, int] = (0, 0)
    guard_ring: bool = False
    guard_ring_col: bool = False
    double_gate: bool = False
    g2_conn_y: Tuple[int, int] = (0, 0)
    g2_m_conn_y: Tuple[int, int] = (0, 0)

    @classmethod
    def from_dict(cls, table: Mapping[str, Any]) -> MOSRowInfo:
        row_type = MOSType[table['row_type']]
        top_ext_info = RowExtInfo.from_dict(table['top_ext_info'])
        bot_ext_info = RowExtInfo.from_dict(table['bot_ext_info'])

        return MOSRowInfo(table['lch'], table['width'], table['sub_width'], row_type,
                          table['threshold'], table['height'], table['flip'],
                          top_ext_info, bot_ext_info, ImmutableSortedDict(table['info']),
                          table['g_conn_y'], table['g_m_conn_y'], table['ds_conn_y'],
                          table['ds_m_conn_y'], table['ds_g_conn_y'], table['sub_conn_y'],
                          guard_ring=table.get('guard_ring', False),
                          guard_ring_col=table.get('guard_ring_col', False),
                          double_gate=table.get('double_gate', False),
                          g2_conn_y=table.get('g2_conn_y', (0, 0)),
                          g2_m_conn_y=table.get('g2_m_conn_y', (0, 0)))

    @property
    def bot_conn_types(self) -> Sequence[MOSWireType]:
        """Return sequence of bottom wire connection types.

        index 0 is the default type.
        """
        if self.flip:
            if self.double_gate:
                return MOSWireType.G2, MOSWireType.G2_MATCH
            return MOSWireType.DS_GATE, MOSWireType.DS, MOSWireType.DS_MATCH
        else:
            return MOSWireType.G, MOSWireType.G_MATCH

    @property
    def top_conn_types(self) -> Sequence[MOSWireType]:
        """Return sequence of top wire connection types.

        index 0 is the default type.
        """
        if self.flip:
            return MOSWireType.G, MOSWireType.G_MATCH
        else:
            if self.double_gate:
                return MOSWireType.G2, MOSWireType.G2_MATCH
            return MOSWireType.DS_GATE, MOSWireType.DS, MOSWireType.DS_MATCH

    @property
    def mid_conn_types(self) -> Sequence[MOSWireType]:
        """Return sequence of top wire connection types.

        index 0 is the default type.
        """
        if self.double_gate:
            return MOSWireType.DS_GATE, MOSWireType.DS, MOSWireType.DS_MATCH

        raise RuntimeError("trying to use mid conn, when its not a double gate")

    def get_ext_info(self, top_edge: bool) -> RowExtInfo:
        return self.top_ext_info if top_edge ^ self.flip else self.bot_ext_info

    def get_conn_y(self, wtype: MOSWireType) -> Tuple[int, int]:
        if wtype is MOSWireType.G:
            ans = self.g_conn_y
        elif wtype is MOSWireType.G_MATCH:
            ans = self.g_m_conn_y
        elif wtype is MOSWireType.DS:
            ans = self.ds_conn_y
        elif wtype is MOSWireType.DS_MATCH:
            ans = self.ds_m_conn_y
        elif wtype is MOSWireType.DS_GATE:
            ans = self.ds_g_conn_y
        elif wtype is MOSWireType.G2:
            ans = self.g2_conn_y
        elif wtype is MOSWireType.G2_MATCH:
            ans = self.g2_m_conn_y
        else:
            raise ValueError(f'Unsupported MOSWireType: {wtype.name}')
        if self.flip:
            return self.height - ans[1], self.height - ans[0]
        return ans

    def get_all_conn_y(self, wtype: MOSWireType) -> Sequence[Tuple[int, int]]:
        """get list of all possible Y coordinates the given wire type could connect to"""
        if wtype is MOSWireType.G or wtype is MOSWireType.G_MATCH:
            ans = [self.g_conn_y]
        elif wtype is MOSWireType.G2 or wtype is MOSWireType.G2_MATCH:
            ans = [self.g2_conn_y]
        elif wtype is MOSWireType.DS:
            ans = [self.ds_conn_y]
        elif wtype is MOSWireType.DS_MATCH or wtype is MOSWireType.DS_GATE:
            ans = [self.ds_conn_y, self.ds_g_conn_y]
        else:
            raise ValueError(f'Unsupported MOSWireType: {wtype.name}')
        if self.flip:
            return [(self.height - v1, self.height - v0) for v0, v1 in ans]
        return ans

    def __getitem__(self, name: str) -> Any:
        return self.info[name]

    def to_dict(self) -> Mapping[str, Any]:
        key_list = ['lch', 'width', 'sub_width', 'threshold', 'height', 'flip', 'g_conn_y',
                    'g_m_conn_y', 'ds_conn_y', 'ds_m_conn_y', 'ds_g_conn_y', 'sub_conn_y',
                    'guard_ring', 'double_gate', 'g2_conn_y', 'g2_m_conn_y']
        ans = {key: getattr(self, key) for key in key_list}
        ans['row_type'] = self.row_type.name
        ans['top_ext_info'] = self.top_ext_info.to_dict()
        ans['bot_ext_info'] = self.bot_ext_info.to_dict()
        ans['info'] = self.info.to_yaml()
        return ans


@dataclass(eq=True, frozen=True)
class MOSPorts:
    g: WireArray
    d: WireArray
    s: WireArray
    shorted_ports: ImmutableList[MOSPortType]
    m: Optional[WireArray] = None
    g2: Optional[WireArray] = None

    @property
    def num_s(self) -> int:
        return self.s.track_id.num

    @property
    def num_d(self) -> int:
        return self.d.track_id.num

    @property
    def num_g(self) -> int:
        return self.g.track_id.num

    @property
    def g0(self) -> WireArray:
        return self.g[0::2]

    @property
    def g1(self) -> WireArray:
        return self.g[1::2]

    def __getitem__(self, item: MOSPortType) -> WireArray:
        if item is MOSPortType.G:
            return self.g
        if item is MOSPortType.D:
            return self.d
        return self.s


@dataclass(eq=True, frozen=True)
class NAND2Ports:
    g0: Sequence[WireArray]
    g1: Sequence[WireArray]
    d: WireArray
    s: WireArray
    m: Optional[WireArray]


@dataclass(eq=True, frozen=True)
class RowPlaceInfo:
    """Information about a transistor row, placement data included.
    (yb_blk, yt_blk) describe the y dimensions of the block, i.e. the MOS row.
    (yb, yt) describe the y dimensions of the block plus any edge extensions.
    """
    row_info: MOSRowInfo
    bot_wires: WireLookup = field(compare=False)
    top_wires: WireLookup = field(compare=False)
    yb: int
    yt: int
    yb_blk: int
    yt_blk: int
    y_conn: Tuple[int, int]
    mid_wires: Optional[WireLookup] = None

    @classmethod
    def from_dict(cls, table: Mapping[str, Any]) -> RowPlaceInfo:
        row_info: Mapping[str, Any] = table['row_info']
        bot_wires: Mapping[Tuple[str, int], Tuple[float, int]] = table['bot_wires']
        top_wires: Mapping[Tuple[str, int], Tuple[float, int]] = table['top_wires']
        yb: int = table['yb']
        yt: int = table['yt']
        yb_blk: int = table['yb_blk']
        yt_blk: int = table['yt_blk']
        y_conn: Tuple[int, int] = tuple(table['y_conn'])
        mid_wires: Optional[Mapping[Tuple[str, int], Tuple[float, int]]] = table.get('mid_wires', {})

        return RowPlaceInfo(MOSRowInfo.from_dict(row_info), WireLookup.from_dict(bot_wires),
                            WireLookup.from_dict(top_wires), yb, yt, yb_blk, yt_blk, y_conn,
                            WireLookup.from_dict(mid_wires))

    def to_dict(self) -> Mapping[str, Any]:
        return dict(
            row_info=self.row_info.to_dict(),
            bot_wires=self.bot_wires.to_dict(),
            top_wires=self.top_wires.to_dict(),
            yb=self.yb,
            yt=self.yt,
            yb_blk=self.yb_blk,
            yt_blk=self.yt_blk,
            y_conn=self.y_conn,
            mid_wires=self.mid_wires.to_dict()
        )

    def get_extend(self, tr_pitch, delta: int, top_edge: bool, shared: Sequence[str]
                   ) -> RowPlaceInfo:
        """Returns a copy of self, with either the top or bottom edge of the bound box
        extended delta in the y direction.
        Uses tr_pitch to quantize delta for shifting the tracks.
        `shared` lists tracks shared with block abut on the extending edge.
        When top_edge==True, the top edge is shifted by delta and the top tracks are shifted.
        When top_edge==False, the top edge is shifted by delta, the active area is shifted by delta,
            and the tracks are shifted by delta. This maintains alignment with y=0.
        """
        tr_shift = HalfInt((2 * delta) // tr_pitch)
        if top_edge:
            top_wires = self.top_wires.get_move_shared(tr_shift, shared)
            return RowPlaceInfo(self.row_info, self.bot_wires, top_wires, self.yb,
                                self.yt + delta, self.yb_blk, self.yt_blk, self.y_conn,
                                mid_wires=self.mid_wires)
        else:
            return RowPlaceInfo(self.row_info, self.bot_wires.get_move(tr_shift, shared),
                                self.top_wires.get_move(tr_shift, []), self.yb, self.yt + delta,
                                self.yb_blk + delta, self.yt_blk + delta,
                                (self.y_conn[0] + delta, self.y_conn[1] + delta),
                                mid_wires=self.mid_wires.get_move(tr_shift, []))

    def get_move(self, tr_pitch: int, delta: int) -> RowPlaceInfo:
        """Returns a copy of self, shifted delta in the y direction.
        Uses tr_pitch to quantize delta for shifting the tracks.
        """
        tr_shift = HalfInt((2 * delta) // tr_pitch)
        el = []
        return RowPlaceInfo(self.row_info, self.bot_wires.get_move(tr_shift, el),
                            self.top_wires.get_move(tr_shift, el), self.yb + delta, self.yt + delta,
                            self.yb_blk + delta, self.yt_blk + delta,
                            (self.y_conn[0] + delta, self.y_conn[1] + delta),
                            mid_wires=self.mid_wires.get_move(tr_shift, el))

    def get_ext_margin(self, top_edge: bool) -> int:
        return self.yt - self.yt_blk if top_edge else self.yb_blk - self.yb

    def get_abut_info(self, rhs: RowPlaceInfo, top_edge: bool, rhs_top_edge: bool,
                      shared: Sequence[str], rhs_shared: Sequence[str],
                      tr_manager: TrackManager, layer: int) -> Tuple[int, RowExtInfo, RowExtInfo]:
        """Returns the margin needed to abut this row with the given row.

        Parameters
        ----------
        rhs : RowPlaceInfo
            the other row.
        top_edge : bool
            True if rhs is abutting to top edge of this row.
        rhs_top_edge : bool
            True if we're abutting to top edge of the other row.
        shared: Sequence[str]
            list of edge wires shared with the other tile.
        rhs_shared : Sequence[str]
            list of edge wires from the other tile shared with this tile.
        tr_manager : TrackManager
            the TrackManager object
        layer : int
            layer ID of the wires.

        Returns
        -------
        margin : int
            the margin in resolution units.
        einfo1 : RowExtInfo
            the row extension information object of this RowPlaceInfo.
        einfo2 : RowExtInfo
            the row extension information object of the other RowPlaceInfo.
        """
        grid = tr_manager.grid

        # get margin needed between wires
        if top_edge:
            wires = self.top_wires if self.top_wires else self.bot_wires
            conn_margin = self.yt - self.y_conn[1]
        else:
            wires = self.bot_wires if self.bot_wires else self.top_wires
            conn_margin = self.y_conn[0] - self.yb

        if rhs_top_edge:
            rhs_wires = rhs.top_wires if rhs.top_wires else rhs.bot_wires
            rhs_conn_margin = rhs.yt - rhs.y_conn[1]
        else:
            rhs_wires = rhs.bot_wires if rhs.bot_wires else rhs.top_wires
            rhs_conn_margin = rhs.y_conn[0] - rhs.yb

        conn_m, wire_m = wires.get_wire_margin_info(grid, layer, self.yb, self.yt, top_edge, shared)
        rhs_conn_m, rhs_wire_m = rhs_wires.get_wire_margin_info(grid, layer, rhs.yb, rhs.yt,
                                                                rhs_top_edge, rhs_shared)
        conn_margin = min(conn_margin, conn_m)
        rhs_conn_margin = min(rhs_conn_margin, rhs_conn_m)

        pitch = grid.get_track_pitch(layer)
        wire_margin = 0
        for name1, margin1 in wire_m:
            for name2, margin2 in rhs_wire_m:
                tot_space = int(pitch * tr_manager.get_sep(layer, (name1, name2)))
                wire_margin = max(wire_margin, tot_space - margin1 - margin2)

        conn_sp_le = grid.get_line_end_space(layer - 1, 1)
        wire_margin = max(wire_margin, conn_sp_le - conn_margin - rhs_conn_margin)
        return (wire_margin, self.row_info.get_ext_info(top_edge),
                rhs.row_info.get_ext_info(rhs_top_edge))


@dataclass(eq=True, frozen=True)
class MOSBaseEndInfo:
    h_mos_end: Tuple[int, int]
    h_blk: Tuple[int, int]


@dataclass(eq=True, frozen=True)
class MOSLayInfo:
    """The transistor block layout information object."""
    lay_info: LayoutInfo
    left_info: MOSEdgeInfo
    right_info: MOSEdgeInfo
    top_info: BlkExtInfo
    bottom_info: BlkExtInfo
    g_info: Tuple[int, int, int]
    d_info: Tuple[int, int, int]
    s_info: Tuple[int, int, int]
    shorted_ports: ImmutableList[MOSPortType]
    m_info: Optional[Tuple[int, int, int]] = None


@dataclass(eq=True, frozen=True)
class ExtEndLayInfo:
    """The extension block layout information object."""
    lay_info: LayoutInfo
    edge_info: MOSEdgeInfo


@dataclass(eq=True, frozen=True)
class MOSAbutInfo:
    row_flat: int
    col: int
    edgel: MOSEdgeInfo
    edger: MOSEdgeInfo


class ExtWidthInfo:
    def __init__(self, discrete_w_list: Sequence[int], w_min: int, step_size: int = 1):
        self._discrete_widths = discrete_w_list
        self._wmin = w_min
        self._step = step_size

    def is_valid(self, w: int) -> bool:
        if w >= self._wmin:
            return (w - self._wmin) % self._step == 0
        else:
            idx = bisect_left(self._discrete_widths, w)
            return idx != len(self._discrete_widths) and self._discrete_widths[idx] == w

    def get_next_width(self, w: int, even: bool = False) -> int:
        if w >= self._wmin:
            diff = w - self._wmin
            q, r = divmod(diff, self._step)
            ans = self._wmin + (q + (r != 0)) * self._step
            if even and ans & 1 == 1:
                if self._step & 1 == 0:
                    raise ValueError('Error: impossible to achieve even extension width.  '
                                     'See developer.')
                return ans + self._step
            return ans
        else:
            idx = bisect_left(self._discrete_widths, w)
            disc_len = len(self._discrete_widths)
            if idx == disc_len:
                if even:
                    return self.get_next_width(self._wmin, even=True)
                else:
                    return self._wmin
            else:
                ans = self._discrete_widths[idx]
                if even:
                    while ans & 1 == 1:
                        idx += 1
                        if idx == disc_len:
                            return self.get_next_width(self._wmin, even=True)
                        ans = self._discrete_widths[idx]
                return ans
