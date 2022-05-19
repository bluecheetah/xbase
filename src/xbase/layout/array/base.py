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

from typing import Any, Optional, Mapping, List, Union, Type, TypeVar, Tuple, cast

import abc
import copy

from pybag.enum import Orientation
from pybag.core import Transform, BBox, BBoxArray

from bag.util.math import HalfInt
from bag.util.immutable import Param, combine_hash, ImmutableSortedDict
from bag.layout.tech import TechInfo
from bag.layout.routing.base import TrackID, TrackManager, WDictType, SpDictType, WireArray
from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.routing.grid import RoutingGrid, TrackSpec

from ..enum import ExtendMode
from ..wires import WireLookup
from .tech import ArrayTech
from .data import ArrayLayInfo
from .primitives import ArrayUnit

A = TypeVar('A', bound='ArrayPlaceInfo')
T = TypeVar('T', bound='ArrayTech')


class ArrayPlaceInfo:
    def __init__(self, parent_grid: RoutingGrid, wire_specs: Mapping[int, Any],
                 tr_widths: WDictType, tr_spaces: SpDictType, top_layer: int, nx: int, ny: int,
                 tech_cls: T, *, conn_layer: Optional[int] = None,
                 tr_specs: Optional[List[TrackSpec]] = None, half_space: bool = True,
                 ext_mode: ExtendMode = ExtendMode.AREA, **kwargs: Any) -> None:
        self._tech_cls: ArrayTech = tech_cls

        # update routing grid
        if conn_layer is None:
            conn_layer = self._tech_cls.conn_layer
        if tr_specs is None:
            tr_specs = self._tech_cls.get_track_specs(conn_layer, top_layer)

        grid: RoutingGrid = parent_grid.get_copy_with(top_ignore_lay=conn_layer - 1,
                                                      tr_specs=tr_specs)
        self._tr_manager = TrackManager(grid, tr_widths, tr_spaces, half_space=half_space)
        # initialize parameters
        self._conn_layer = conn_layer
        self._top_layer = top_layer
        self._blk_options = Param(kwargs)
        self._nx = nx
        self._ny = ny

        self._wire_specs = wire_specs
        self._ext_mode = ext_mode

        self._w = None
        self._h = None
        self._wlookup = None
        self._blk_info = None
        self._hash = None

        self.commit()

    def commit(self):
        tmp = self._tech_cls.size_unit_block(self._conn_layer, self._top_layer, self._nx, self._ny, self._tr_manager,
                                             self._wire_specs, self._ext_mode, **self._blk_options)
        self._w: int = tmp[0]
        self._h: int = tmp[1]
        self._wlookup: ImmutableSortedDict[int, WireLookup] = ImmutableSortedDict(tmp[2])
        self._blk_info: ArrayLayInfo = tmp[3]

        self._hash = self.compute_hash()

    def compute_hash(self):
        seed = combine_hash(hash(self._tr_manager), self._conn_layer)
        seed = combine_hash(seed, self._top_layer)
        seed = combine_hash(seed, self._nx)
        seed = combine_hash(seed, self._ny)
        seed = combine_hash(seed, self._w)
        seed = combine_hash(seed, self._h)
        seed = combine_hash(seed, hash(self._wlookup))
        seed = combine_hash(seed, hash(self._blk_options))
        return seed

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: Any) -> bool:
        return (isinstance(other, self.__class__) and
                self._tr_manager == other._tr_manager and
                self._conn_layer == other._conn_layer and
                self._top_layer == other._top_layer and
                self._nx == other._nx and
                self._ny == other._ny and
                self._w == other._w and
                self._h == other._h and
                self._wlookup == other._wlookup and
                self._blk_options == other._blk_options)

    @classmethod
    @abc.abstractmethod
    def get_tech_cls(cls, tech_info: TechInfo, **kwargs: Any) -> ArrayTech:
        raise NotImplementedError('Not implemented.')

    @classmethod
    def get_conn_layer(cls, tech_info: TechInfo, **kwargs: Any) -> int:
        return cls.get_tech_cls(tech_info, **kwargs).conn_layer

    @classmethod
    def make_place_info(cls: Type[A], grid: RoutingGrid,
                        val: Union[ArrayPlaceInfo, Mapping[str, Any]]) -> A:
        if isinstance(val, ArrayPlaceInfo):
            return val
        return cls(grid, **val)

    @property
    def grid(self) -> RoutingGrid:
        return self._tr_manager.grid

    @property
    def tr_manager(self) -> TrackManager:
        return self._tr_manager

    @property
    def blk_options(self) -> Param:
        return self._blk_options

    @property
    def tech_cls(self) -> T:
        return self._tech_cls

    @property
    def top_layer(self) -> int:
        return self._top_layer

    @property
    def conn_layer(self) -> int:
        return self._conn_layer

    @property
    def width(self) -> int:
        """Width of a unit cell, in resolution units"""
        return self._w

    @property
    def height(self) -> int:
        """Height of a unit cell, in resolution units"""
        return self._h

    @property
    def nx(self) -> int:
        return self._nx

    @property
    def ny(self) -> int:
        return self._ny

    @property
    def blk_info(self) -> ArrayLayInfo:
        return self._blk_info

    def get_wire_track_info(self, layer: int, wire_name: str, wire_idx: int) -> Tuple[HalfInt, int]:
        return self._wlookup[layer].get_track_info(wire_name, wire_idx)

    def get_sub_place_info(self, nx: Optional[int] = None, ny: Optional[int] = None, top_layer: Optional[int] = None) \
            -> ArrayPlaceInfo:
        ans = copy.copy(self)

        if nx is not None:
            ans._nx = nx
        if ny is not None:
            ans._ny = ny
        if top_layer is not None:
            ans._top_layer = top_layer

        ans.commit()
        return ans


class ArrayBase(TemplateBase, abc.ABC):
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)
        self._info: Optional[ArrayPlaceInfo] = None
        self._unit: Optional[ArrayUnit] = None

    @property
    def tech_cls(self) -> ArrayTech:
        return self._info.tech_cls

    @property
    def place_info(self) -> Optional[ArrayPlaceInfo]:
        return self._info

    @property
    def conn_layer(self) -> int:
        return self._info.conn_layer

    @property
    def tr_manager(self) -> TrackManager:
        return self._info.tr_manager

    @property
    def nx(self) -> int:
        return self._info.nx

    @property
    def ny(self) -> int:
        return self._info.ny

    def draw_base(self, info: ArrayPlaceInfo) -> ArrayUnit:
        self._info = info
        self.grid = info.grid

        self._unit = master = self.new_template(ArrayUnit, params=dict(desc=self.tech_cls.desc,
                                                                       blk_info=info.blk_info))

        nxo = info.nx // 2
        nxe = info.nx - nxo
        nyo = info.ny // 2
        nye = info.ny - nyo
        spx = 2 * info.width
        spy = 2 * info.height
        self.add_instance(master, inst_name='XLL', xform=Transform(0, 0),
                          nx=nxe, ny=nye, spx=spx, spy=spy)
        if nxo > 0:
            self.add_instance(master, inst_name='XLR', xform=Transform(spx, 0, Orientation.MY),
                              nx=nxo, ny=nye, spx=spx, spy=spy)
        if nyo > 0:
            self.add_instance(master, inst_name='XUL', xform=Transform(0, spy, Orientation.MX),
                              nx=nxe, ny=nyo, spx=spx, spy=spy)
            if nxo > 0:
                self.add_instance(master, inst_name='XUR',
                                  xform=Transform(spx, spy, Orientation.R180),
                                  nx=nxo, ny=nyo, spx=spx, spy=spy)

        bbox = BBox(0, 0, info.nx * info.width, info.ny * info.height)
        self.set_size_from_bound_box(info.top_layer, bbox)
        return master

    def get_track_info(self, wire_name: str, wire_idx: int = 0, layer: Optional[int] = None
                       ) -> Tuple[HalfInt, int]:
        if layer is None:
            layer = self.conn_layer + 1
        return self._info.get_wire_track_info(layer, wire_name, wire_idx)

    def get_track_id(self, wire_name: str, wire_idx: int = 0, layer: Optional[int] = None
                     ) -> TrackID:
        if layer is None:
            layer = self.conn_layer + 1
        idx, w = self.get_track_info(wire_name, wire_idx=wire_idx, layer=layer)
        return TrackID(layer, idx, width=w, grid=self.grid)

    def get_track_index(self, wire_name: str, wire_idx: int = 0, layer: Optional[int] = None
                        ) -> HalfInt:
        return self.get_track_info(wire_name, wire_idx=wire_idx, layer=layer)[0]

    def get_device_port(self, xidx: int, yidx: int, name: str) -> Union[WireArray, BBox, BBoxArray]:
        w = self._info.width
        h = self._info.height
        orient = Orientation.R0

        dx = w * xidx
        dy = h * yidx
        if (xidx & 1) != 0:
            dx += w
            orient = orient.flip_lr()
        if (yidx & 1) != 0:
            dy += h
            orient = orient.flip_ud()

        xform = Transform(dx, dy, orient)
        pins = self._unit.get_port(name).get_pins()
        nx = len(pins)
        if nx == 1:
            return pins[0].get_transform(xform)
        else:
            if isinstance(pins[0], WireArray):
                # Combine into 1 WireArray with num > 1 if possible
                pins = self.connect_wires(pins[0])
                return pins[0].get_transform(xform)
            else:  # List of BBox
                pins = [cast(BBox, bbox) for bbox in pins]
                yl = pins[0].yl
                yh = pins[0].yh
                w = pins[0].w
                spx = pins[1].xm - pins[0].xm
                for pidx, pin in enumerate(pins[1:]):
                    if not (pin.yl == yl and pin.yh == yh and pin.w == w):
                        # cannot be combined into BBoxArray if yl, yh, w are not same
                        return pins[0].get_transform(xform)
                    if pidx != nx - 2:
                        if pins[pidx + 2].xm - pin.xm != spx:
                            # cannot be combined into BBoxArray if spx is not same
                            return pins[0].get_transform(xform)
                return BBoxArray(pins[0], nx, spx=spx).get_transform(xform)

    def add_tile(self, master: ArrayBase, row_idx: int, col_idx: int, *,
                 flip_lr: bool = False, flip_ud: bool = False, commit: bool = True) -> PyLayInstance:
        self._row_check(row_idx, master.ny, flip_ud)
        self._col_check(col_idx, master.nx, flip_lr)

        unit_h, unit_w = self._info.height, self._info.width

        y0 = row_idx * unit_h
        x0 = col_idx * unit_w

        if flip_ud:
            orient = Orientation.MX
            y0 += unit_h
        else:
            orient = Orientation.R0

        if flip_lr:
            orient = orient.flip_lr()
            x0 += unit_w

        return self.add_instance(master, inst_name=f'XR{row_idx}C{col_idx}',
                                 xform=Transform(x0, y0, orient), commit=commit)

    def _row_check(self, row_idx: int, num_rows: int, flip: bool):
        if flip:
            row_bot, row_top = row_idx - num_rows + 1, row_idx
        else:
            row_bot, row_top = row_idx, row_idx + num_rows - 1
        if row_bot < 0:
            raise ValueError(f"Bottom row {row_bot} cannot be less than 0")
        if row_top >= self.ny:
            raise ValueError(f"Top row {row_top} cannot be greater than or equal to ny {self.ny}")

    def _col_check(self, col_idx: int, num_cols: int, flip: bool):
        if flip:
            col_left, col_right = col_idx - num_cols + 1, col_idx
        else:
            col_left, col_right = col_idx, col_idx + num_cols - 1
        if col_left < 0:
            raise ValueError(f"left col {col_left} cannot be less than 0")
        if col_right > self.nx:
            raise ValueError(f"right col {col_right} cannot be greater than or equal to nx {self.nx}")
