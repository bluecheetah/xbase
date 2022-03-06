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

import abc
import numpy as np
from enum import IntEnum

from typing import Any, Optional, Mapping, cast, Union, Tuple, Sequence

from pybag.core import BBox, Transform
from pybag.enum import MinLenMode, RoundMode, Direction, Orientation

from bag.util.immutable import Param
from bag.layout.template import TemplateDB
from bag.layout.tech import TechInfo
from bag.layout.routing.base import WDictType, SpDictType, WireArray, TrackID
from bag.layout.routing.grid import RoutingGrid, TrackSpec

from ..mos.data import MOSType
from ..enum import ExtendMode
from ..array.base import ArrayPlaceInfo, ArrayBase
from .tech import ResTech


class ResTermType(IntEnum):
    BOT = 0
    TOP = 1
    BULK = 2


class ResBasePlaceInfo(ArrayPlaceInfo):
    def __init__(self, parent_grid: RoutingGrid, wire_specs: Mapping[int, Any],
                 tr_widths: WDictType, tr_spaces: SpDictType, top_layer: int, nx: int, ny: int, *,
                 conn_layer: Optional[int] = None, res_type: str = 'standard', mos_type: str = '',
                 threshold: str = '', tr_specs: Optional[Sequence[TrackSpec]] = None,
                 half_space: bool = True, ext_mode: ExtendMode = ExtendMode.AREA,
                 **kwargs: Any) -> None:
        metal = (res_type == 'metal')
        tech_cls: ResTech = parent_grid.tech_info.get_device_tech('res', metal=metal)
        self._res_config = parent_grid.tech_info.config['res_metal' if metal else 'res']

        if not mos_type:
            mos_type = tech_cls.mos_type_default
        if not threshold:
            threshold = tech_cls.threshold_default
        if 'res_type' in kwargs['unit_specs']['params']:
            res_type = kwargs['unit_specs']['params']['res_type']

        ArrayPlaceInfo.__init__(self, parent_grid, wire_specs, tr_widths, tr_spaces, top_layer,
                                nx, ny, tech_cls, conn_layer=conn_layer, tr_specs=tr_specs,
                                half_space=half_space, ext_mode=ext_mode, res_type=res_type,
                                mos_type=mos_type, threshold=threshold, **kwargs)

        self._res_type = res_type
        self._mos_type = MOSType[mos_type]
        self._threshold = threshold

        self._w_res = tech_cls.get_width(**kwargs)
        self._l_res = tech_cls.get_length(**kwargs)

    def __eq__(self, other: Any) -> bool:
        # noinspection PyProtectedMember
        return (ArrayPlaceInfo.__eq__(self, other) and
                self._res_type == other._res_type and
                self._mos_type == other._mos_type and
                self._threshold == other._threshold)

    @classmethod
    def get_tech_cls(cls, tech_info: TechInfo, **kwargs: Any) -> ResTech:
        res_type = kwargs.get('res_type', 'standard')

        metal = (res_type == 'metal')
        return tech_info.get_device_tech('res', metal=metal)

    @property
    def res_type(self) -> str:
        return self._res_type

    @property
    def mos_type(self) -> MOSType:
        return self._mos_type

    @property
    def threshold(self) -> str:
        return self._threshold

    @property
    def res_config(self) -> Mapping[str, Any]:
        return self._res_config

    @property
    def has_substrate_port(self) -> bool:
        return self._res_config['has_substrate_port']

    @property
    def w_res(self) -> int:
        return self._w_res

    @property
    def l_res(self) -> int:
        return self._l_res


class ResArrayBase(ArrayBase, abc.ABC):
    """An abstract template that draws analog resistors array and connections.

    This template assumes that the resistor array uses 4 routing layers, with
    directions x/y/x/y.  The lower 2 routing layers is used to connect between
    adjacent resistors, and pin will be drawn on the upper 2 routing layers.

    Like for MOSBase, conn_layer should return the top-most layer of the primitive,
    i.e. the pin layer. We can then connect BBoxs or WireArrays to the pins using
    the next layer.
    Unlike BAG2, we assume the conn_layer is BELOW the bottom-most routing layer
    described above (i.e. below the first horizontal resistor routing layer).
    This is to allow for more control of the low level wire placement.
    One effect of this is that resistor primitives can be either WireArrays or BBoxs,
    so classes using ResArrayBase need to be coded for both.
    Primitives must be design with connecting to the above horizontal metal in mind.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        ArrayBase.__init__(self, temp_db, params, **kwargs)

    @property
    def has_substrate_port(self) -> bool:
        return cast(ResTech, self.tech_cls).has_substrate_port

    @property
    def sub_type(self) -> MOSType:
        return cast(ResBasePlaceInfo, self.place_info).mos_type

    def draw_base(self, obj: Union[ResBasePlaceInfo, Mapping[str, Any]]) -> ResBasePlaceInfo:
        if isinstance(obj, ResBasePlaceInfo):
            pinfo = obj
        else:
            pinfo = ResBasePlaceInfo(self.grid, **obj)

        super().draw_base(pinfo)
        return pinfo

    def get_res_bbox(self, row_idx: int, col_idx: int) -> BBox:
        """Returns the bounding box of the given resistor."""
        # TODO: fix this
        x0, y0 = 0, 0  # self._core_offset
        xp, yp = self.place_info.width, self.place_info.height
        x0 += xp * col_idx
        y0 += yp * row_idx
        return BBox(x0, y0, x0 + xp, y0 + yp)

    def _get_transform(self, _xidx, _yidx):
        # Get transform for a given core cell. Useful for transforming ports
        w = self._info.width
        h = self._info.height
        orient = Orientation.R0

        dx = w * _xidx
        dy = h * _yidx

        return Transform(dx, dy, orient)

    def get_res_ports(self, row_idx: int, col_idx: int,
                      top_port_name: str = "PLUS", bot_port_name: str = 'MINUS'
                      ) -> Union[Tuple[WireArray, WireArray], Tuple[BBox, BBox]]:
        """Returns the port of the given resistor.

        Parameters
        ----------
        row_idx : int
            the resistor row index.  0 is the bottom row.
        col_idx : int
            the resistor column index.  0 is the left-most column.
        top_port_name: str
            name of the top port. Defaults to "PLUS"
        bot_port_name: str
            name of the bottom port. Defaults to "MINUS"

        Returns
        -------
        bot_warr : WireArray
            the bottom port as WireArray.
        top_warr : WireArray
            the top port as WireArray.
        """

        return self.get_device_port(col_idx, row_idx, bot_port_name), \
            self.get_device_port(col_idx, row_idx, top_port_name)

    def connect_units(self, warrs: Mapping[int, Mapping[ResTermType, np.ndarray]], x0: int, x1: int, y0: int, y1: int
                      ) -> Tuple[WireArray, WireArray]:
        """Connect all unit resistors to have parallel connection from x0 to x1 and series from y0 to y1.
        Returns bottom and top vm_layer WireArrays."""
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1

        prev_vm: Optional[WireArray] = None
        bot_vm: Optional[WireArray] = None
        top_vm: Optional[WireArray] = None
        for yidx in range(y0, y1):
            # parallel connections
            self.connect_wires(warrs[hm_layer][ResTermType.BOT][x0:x1, yidx].tolist())
            self.connect_wires(warrs[hm_layer][ResTermType.TOP][x0:x1, yidx].tolist())

            _bot_vm = self.connect_wires(warrs[vm_layer][ResTermType.BOT][x0:x1, yidx].tolist())[0]
            _top_vm = self.connect_wires(warrs[vm_layer][ResTermType.TOP][x0:x1, yidx].tolist())[0]

            # series connections
            if yidx == y0:
                bot_vm = _bot_vm
            else:
                self.connect_wires([_bot_vm, prev_vm])

            if yidx == y1 - 1:
                top_vm = _top_vm
            else:
                prev_vm = _top_vm

        return bot_vm, top_vm

    def connect_dummies(self, warrs: Mapping[int, Mapping[ResTermType, np.ndarray]],
                        bulk_warrs: Mapping[int, Union[WireArray, Sequence[WireArray]]]) -> None:
        """Connect all the dummy resistors for the case where dummies are on the periphery."""
        nx = self.place_info.nx
        ny = self.place_info.ny
        nx_dum = self.params['nx_dum']
        ny_dum = self.params['ny_dum']

        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1

        for yidx in range(ny):
            for xidx in range(nx):
                # connect PLUS and MINUS of dummy units to supply connections
                if xidx < nx_dum or xidx >= (nx - nx_dum) or yidx < nx_dum or yidx >= (ny - ny_dum):
                    self.connect_to_track_wires(warrs[vm_layer][ResTermType.BOT][xidx, yidx],
                                                bulk_warrs[hm_layer][yidx])
                    self.connect_to_track_wires(warrs[vm_layer][ResTermType.TOP][xidx, yidx],
                                                bulk_warrs[hm_layer][yidx + 1])

    def connect_bulk_xm(self, warrs: Mapping[int, Sequence[Union[WireArray, Sequence[WireArray]]]]
                        ) -> Tuple[WireArray, WireArray]:
        """Connect all bulk connections to supply on xm_layer"""
        # connect bulk vm_layer wires to xm_layer
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        xm_layer = vm_layer + 1
        top_layer = self.place_info.top_layer
        assert top_layer >= xm_layer, f'top_layer={top_layer} must be greater than {xm_layer}.'
        w_sup_xm = self.tr_manager.get_width(xm_layer, 'sup')

        xm_tidx0 = self.grid.coord_to_track(xm_layer, 0, RoundMode.NEAREST)
        xm_tid0 = TrackID(xm_layer, xm_tidx0, w_sup_xm)
        bot_xm = self.connect_to_tracks(warrs[vm_layer][0], xm_tid0)
        xm_tidx1 = self.grid.coord_to_track(xm_layer, self.place_info.ny * self.place_info.height, RoundMode.NEAREST)
        xm_tid1 = TrackID(xm_layer, xm_tidx1, w_sup_xm)
        top_xm = self.connect_to_tracks(warrs[vm_layer][1], xm_tid1)

        # Add pins
        sup_name = 'VDD' if cast(ResBasePlaceInfo, self.place_info).res_config['sub_type_default'] == 'ntap' else 'VSS'
        self.add_pin(sup_name, [bot_xm, top_xm])
        return bot_xm, top_xm

    def connect_hm_vm(self, sig_type: str = 'sig') -> Tuple[Mapping[int, Mapping[ResTermType, np.ndarray]],
                                                            Mapping[int, Union[WireArray, Sequence[WireArray]]]]:
        """Connect all resistor ports on hm_layer and vm_layer. BULK ports are shorted.
        Returns:
            1. terms:
                 hm_layer:
                   ResTermType.BOT: numpy array of all top hm_layer wires
                   ResTermType.TOP: numpy array of all top vm_layer wires
                 vm_layer:
                   ResTermType.BOT: numpy array of all bottom hm_layer wires
                   ResTermType.TOP: numpy array of all bottom vm_layer wires
            2. bulk_warrs:
                 hm_layer: WireArray with num >= 1 of all hm_layer bulk wires
                 vm_layer: [bottom vm_layer WireArray with num >= 1, top vm_layer WireArray with num >= 1]
        """
        nx = self.place_info.nx
        ny = self.place_info.ny

        conn_layer = self.place_info.conn_layer
        prim_lp = self.grid.tech_info.get_lay_purp_list(conn_layer)[0]
        hm_layer = conn_layer + 1
        vm_layer = hm_layer + 1
        w_sup_hm = self.tr_manager.get_width(hm_layer, 'sup')
        w_sup_vm = self.tr_manager.get_width(vm_layer, 'sup')
        w_sig_hm = self.tr_manager.get_width(hm_layer, sig_type)
        w_sig_vm = self.tr_manager.get_width(vm_layer, sig_type)

        bulk_warrs = {}
        # Use numpy 2D arrays to support index slicing in self.connect_units() and easy conversion to list for passing
        # to self.connect_wires(), self.connect_to_tracks(), etc.
        terms = {
            hm_layer: {
                ResTermType.BOT: np.empty((nx, ny), WireArray),
                ResTermType.TOP: np.empty((nx, ny), WireArray),
            },
            vm_layer: {
                ResTermType.BOT: np.empty((nx, ny), WireArray),
                ResTermType.TOP: np.empty((nx, ny), WireArray),
            },
        }

        # get hm_layer wires for supply connections
        unit_h = self.place_info.height
        hm_warr_list = []
        for yidx in range(ny + 1):
            hm_tidx = self.grid.coord_to_track(hm_layer, unit_h * yidx, RoundMode.NEAREST)
            hm_warr_list.append(self.add_wires(hm_layer, hm_tidx, self.bound_box.xl, self.bound_box.xh, width=w_sup_hm))

        # connect from conn_layer to hm_layer and vm_layer
        for yidx in range(ny):
            # get hm_layer wires for signal connections
            if yidx & 1:
                top = 'MINUS'
                bot = 'PLUS'
            else:
                top = 'PLUS'
                bot = 'MINUS'

            bbox_bot = self.get_device_port(0, yidx, bot)
            hm_idx0 = self.grid.coord_to_track(hm_layer, bbox_bot.yl, RoundMode.NEAREST)
            hm_tid0 = TrackID(hm_layer, hm_idx0, w_sig_hm)

            bbox_top = self.get_device_port(0, yidx, top)
            hm_idx1 = self.grid.coord_to_track(hm_layer, bbox_top.yh, RoundMode.NEAREST)
            hm_tid1 = TrackID(hm_layer, hm_idx1, w_sig_hm)

            for xidx in range(nx):
                # connect PLUS and MINUS of every resistor unit to hm_layer signal wires
                hm_warr0 = self.connect_bbox_to_tracks(Direction.LOWER, prim_lp, self.get_device_port(xidx, yidx, bot),
                                                       hm_tid0, min_len_mode=MinLenMode.MIDDLE)
                terms[hm_layer][ResTermType.BOT][xidx, yidx] = hm_warr0

                hm_warr1 = self.connect_bbox_to_tracks(Direction.LOWER, prim_lp, self.get_device_port(xidx, yidx, top),
                                                       hm_tid1, min_len_mode=MinLenMode.MIDDLE)
                terms[hm_layer][ResTermType.TOP][xidx, yidx] = hm_warr1

                # connect to vm_layer signal wires
                vm_idx = self.grid.coord_to_track(vm_layer, hm_warr0.middle, RoundMode.NEAREST)
                vm_tid = TrackID(vm_layer, vm_idx, w_sig_vm)
                vm_warr0 = self.connect_to_tracks(hm_warr0, vm_tid, min_len_mode=MinLenMode.MIDDLE)
                terms[vm_layer][ResTermType.BOT][xidx, yidx] = vm_warr0
                vm_warr1 = self.connect_to_tracks(hm_warr1, vm_tid, min_len_mode=MinLenMode.MIDDLE)
                terms[vm_layer][ResTermType.TOP][xidx, yidx] = vm_warr1

                # connect BULK of every resistor unit, if it exists
                if self.has_substrate_port:
                    bulk_bbox = self.get_device_port(xidx, yidx, 'BULK')
                    self.connect_bbox_to_track_wires(Direction.LOWER, prim_lp, bulk_bbox, hm_warr_list[yidx])
                    self.connect_bbox_to_track_wires(Direction.LOWER, prim_lp, bulk_bbox, hm_warr_list[yidx + 1])

        # connect bottom and top hm_layer supply wires to vm_layer supply wires
        vm_tidx0 = self.grid.coord_to_track(vm_layer, 0, RoundMode.NEAREST)
        vm_tidx1 = self.grid.coord_to_track(vm_layer, self.place_info.width, RoundMode.NEAREST)
        vm_tid = TrackID(vm_layer, vm_tidx0, w_sup_vm, nx + 1, vm_tidx1 - vm_tidx0)
        bot_vm = self.connect_to_tracks(hm_warr_list[0], vm_tid, min_len_mode=MinLenMode.MIDDLE)
        top_vm = self.connect_to_tracks(hm_warr_list[-1], vm_tid, min_len_mode=MinLenMode.MIDDLE)
        self.connect_to_track_wires(hm_warr_list, [bot_vm[0], top_vm[0], bot_vm[-1], top_vm[-1]])

        bulk_warrs[hm_layer] = self.connect_wires(hm_warr_list)[0]
        bulk_warrs[vm_layer] = [bot_vm, top_vm]

        return terms, bulk_warrs

    def connect_port_hm(self, port: Union[WireArray, BBox,
                                          Sequence[WireArray, BBox]], adjust: int = 0
                        ) -> Union[WireArray, Sequence[WireArray]]:
        """Connects a single or list of resistor port from conn_layer to hm_layer
        By default, hm wire will be (nearest) centered to the port. If
        the port needs to be moved, use the adjust option.

        Parameters:
        ----------------------
        port: Union[WireArray, BBox, Sequence[WireArray, BBox]]
            Port in question, on conn_layer
            If a sequence of ports is passed in, function is called on each one

        adjust: int
            If given, this parameter is passed to get_next_track to get
            the track id `adjust` tracks away.

        Returns the WireArray or list of WireArrays on hm_layer
        """
        if isinstance(port, Sequence):
            return [self.connect_port_hm(p, adjust) for p in port]

        conn_layer = self.place_info.conn_layer
        prim_lp = self.grid.tech_info.get_lay_purp_list(conn_layer)[0]
        hm_layer = conn_layer + 1
        w_sig_hm = self.tr_manager.get_width(hm_layer, 'sig')

        wire_bbox: BBox = port if isinstance(port, BBox) else port.bound_box
        bbox_ym = wire_bbox.ym
        near_tidx = self.grid.coord_to_track(hm_layer, bbox_ym, RoundMode.NEAREST)
        if adjust:
            near_tidx = self.tr_manager.get_next_track(hm_layer, near_tidx, 'sig', 'sig', up=adjust)
        port_tid = TrackID(hm_layer, near_tidx, w_sig_hm)
        if isinstance(port, BBox):
            port_hm = self.connect_bbox_to_tracks(Direction.LOWER, prim_lp, wire_bbox, port_tid)
        else:
            port_hm = self.connect_to_tracks(port, port_tid)

        return port_hm
