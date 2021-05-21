# BSD 3-Clause License
#
# Copyright (c) 2018, Regents of the University of California
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""This module defines programmable series / parallel combination of resistor units for characterization."""

from typing import Mapping, Any, Optional, Type, cast

from bag.util.immutable import Param
from bag.design.module import Module
from bag.layout.template import TemplateDB
from bag.layout.routing.base import TrackID, WireArray

from pybag.enum import RoundMode, MinLenMode, Direction

from .base import ResBasePlaceInfo, ResArrayBase
from ...schematic.res_char import xbase__res_char


class ResChar(ResArrayBase):
    """Programmable series / parallel combination of unit resistors"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        ResArrayBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return xbase__res_char

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            pinfo='The ResBasePlaceInfo object.',
        )

    def draw_layout(self) -> None:
        pinfo = cast(ResBasePlaceInfo, ResBasePlaceInfo.make_place_info(self.grid, self.params['pinfo']))
        self.draw_base(pinfo)

        # Draw routing of unit resistors
        self._route_main()

        # Supply connections
        self._draw_supplies()

        self.sch_params = dict(
            unit_params=dict(
                w=pinfo.w_res,
                l=pinfo.l_res,
                intent=pinfo.res_type,
            ),
            nser=pinfo.ny,
            npar=pinfo.nx,
            sub_type=pinfo.res_config['sub_type_default'],
        )

    def _route_main(self) -> None:
        """Connect all the unit resistors"""
        nx = self.place_info.nx
        ny = self.place_info.ny

        conn_layer = self.place_info.conn_layer
        prim_lp = self.grid.tech_info.get_lay_purp_list(conn_layer)[0]
        hm_layer = conn_layer + 1
        vm_layer = hm_layer + 1
        xm_layer = vm_layer + 1
        top_layer = self.place_info.top_layer
        assert top_layer == xm_layer, f'Supports only top_layer={xm_layer} for now.'
        w_sig_hm = self.tr_manager.get_width(hm_layer, 'sig')
        w_sig_vm = self.tr_manager.get_width(vm_layer, 'sig')
        w_sig_xm = self.tr_manager.get_width(xm_layer, 'sig')

        prev_vm: Optional[WireArray] = None
        for yidx in range(ny):
            # get hm_layer wires for this row
            if yidx & 1:
                top = 'MINUS'
                bot = 'PLUS'
            else:
                top = 'PLUS'
                bot = 'MINUS'
            bbox0_bot = self.get_device_port(0, yidx, bot)
            hm_idx0 = self.grid.coord_to_track(hm_layer, bbox0_bot.ym, RoundMode.NEAREST)
            _xl = bbox0_bot.xl
            _xh = bbox0_bot.xh + (nx - 1) * self.place_info.width
            hm_warr0 = self.add_wires(hm_layer, hm_idx0, _xl, _xh, width=w_sig_hm)
            bbox0_top = self.get_device_port(0, yidx, top)
            hm_idx1 = self.grid.coord_to_track(hm_layer, bbox0_top.ym, RoundMode.NEAREST)
            hm_warr1 = self.add_wires(hm_layer, hm_idx1, _xl, _xh, width=w_sig_hm)

            for xidx in range(nx):
                # connect all conn_layer pins to hm_layer wires
                bbox_bot = self.get_device_port(xidx, yidx, bot)
                self.connect_bbox_to_track_wires(Direction.LOWER, prim_lp, bbox_bot, hm_warr0)
                bbox_top = self.get_device_port(xidx, yidx, top)
                self.connect_bbox_to_track_wires(Direction.LOWER, prim_lp, bbox_top, hm_warr1)

            # connect to vm_layer wires
            vm_idx0 = self.grid.coord_to_track(vm_layer, bbox0_bot.xm, RoundMode.NEAREST)
            vm_idx1 = self.grid.coord_to_track(vm_layer, bbox0_bot.xm + self.place_info.width, RoundMode.NEAREST)
            vm_tid = TrackID(vm_layer, vm_idx0, w_sig_vm, nx, vm_idx1 - vm_idx0)
            bot_vm = self.connect_to_tracks(hm_warr0, vm_tid, min_len_mode=MinLenMode.MIDDLE)
            top_vm = self.connect_to_tracks(hm_warr1, vm_tid, min_len_mode=MinLenMode.MIDDLE)

            # connect to xm_layer wires
            if yidx == 0:
                xm_idx = self.grid.coord_to_track(xm_layer, bbox0_bot.ym, RoundMode.NEAREST)
                minus = self.connect_to_tracks(bot_vm, TrackID(xm_layer, xm_idx, w_sig_xm),
                                               min_len_mode=MinLenMode.MIDDLE)
                self.add_pin('minus', minus)
            else:
                self.connect_wires([bot_vm, prev_vm])

            if yidx == ny - 1:
                xm_idx = self.grid.coord_to_track(xm_layer, bbox0_top.ym, RoundMode.NEAREST)
                plus = self.connect_to_tracks(top_vm, TrackID(xm_layer, xm_idx, w_sig_xm),
                                              min_len_mode=MinLenMode.MIDDLE)
                self.add_pin('plus', plus)
            else:
                prev_vm = top_vm

    def _draw_supplies(self) -> None:
        """Connect supplies of all the unit resistors, if bulk connection exists"""
        if not self.has_substrate_port:
            return
        nx = self.place_info.nx
        ny = self.place_info.ny

        conn_layer = self.place_info.conn_layer
        prim_lp = self.grid.tech_info.get_lay_purp_list(conn_layer)[0]
        hm_layer = conn_layer + 1
        w_sup_hm = self.tr_manager.get_width(hm_layer, 'sup')

        # get hm_layer wires
        unit_h = self.place_info.height
        hm_warr_list = []
        for yidx in range(ny + 1):
            hm_tidx = self.grid.coord_to_track(hm_layer, unit_h * yidx, RoundMode.NEAREST)
            hm_warr_list.append(self.add_wires(hm_layer, hm_tidx, self.bound_box.xl, self.bound_box.xh, width=w_sup_hm))

        # connect from conn_layer to hm_layer
        for yidx in range(ny):
            for xidx in range(nx):
                bulk_bbox = self.get_device_port(xidx, yidx, 'BULK')
                self.connect_bbox_to_track_wires(Direction.LOWER, prim_lp, bulk_bbox, hm_warr_list[yidx])
                self.connect_bbox_to_track_wires(Direction.LOWER, prim_lp, bulk_bbox, hm_warr_list[yidx + 1])

        # connect bottom and top hm_layer wires to xm_layer
        vm_layer = hm_layer + 1
        w_sup_vm = self.tr_manager.get_width(vm_layer, 'sup')

        vm_tidx0 = self.grid.coord_to_track(vm_layer, 0, RoundMode.NEAREST)
        vm_tidx1 = self.grid.coord_to_track(vm_layer, self.place_info.width, RoundMode.NEAREST)
        vm_tid = TrackID(vm_layer, vm_tidx0, w_sup_vm, nx + 1, vm_tidx1 - vm_tidx0)
        bot_vm = self.connect_to_tracks(hm_warr_list[0], vm_tid, min_len_mode=MinLenMode.MIDDLE)
        top_vm = self.connect_to_tracks(hm_warr_list[-1], vm_tid, min_len_mode=MinLenMode.MIDDLE)

        xm_layer = vm_layer + 1
        top_layer = self.place_info.top_layer
        assert top_layer == xm_layer, f'Supports only top_layer={xm_layer} for now.'
        w_sup_xm = self.tr_manager.get_width(xm_layer, 'sup')

        xm_tidx0 = self.grid.coord_to_track(xm_layer, 0, RoundMode.NEAREST)
        xm_tid0 = TrackID(xm_layer, xm_tidx0, w_sup_xm)
        bot_xm = self.connect_to_tracks(bot_vm, xm_tid0)
        xm_tidx1 = self.grid.coord_to_track(xm_layer, ny * unit_h, RoundMode.NEAREST)
        xm_tid1 = TrackID(xm_layer, xm_tidx1, w_sup_xm)
        top_xm = self.connect_to_tracks(top_vm, xm_tid1)

        # Add pins
        sup_name = 'VDD' if cast(ResBasePlaceInfo, self.place_info).res_config['sub_type_default'] == 'ntap' else 'VSS'
        self.add_pin(sup_name, [bot_xm, top_xm])
