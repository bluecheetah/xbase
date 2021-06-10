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


from typing import Any, Dict, cast, Type, Optional, List, Tuple

from bisect import bisect_left

from bag.design.module import Module
from bag.util.immutable import Param
from bag.util.importlib import import_class
from bag.layout.routing.base import WireArray
from bag.layout.template import TemplateDB, PyLayInstance

from ..enum import MOSWireType

from .placement.data import TilePatternElement, TilePattern
from .base import MOSBase


class GuardRing(MOSBase):
    """A layout generator that adds substrate rows on top and bottom of a MOSBase instance."""

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBase.__init__(self, temp_db, params, **kwargs)
        self._sch_cls: Optional[Type[Module]] = None
        self._core: Optional[MOSBase] = None

    @property
    def core(self) -> MOSBase:
        return self._core

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            cls_name='instance class name.',
            params='parameters for the instance.',
            pmos_gr='pmos guard ring tile name.',
            nmos_gr='nmos guard ring tile name.',
            sep_ncol='tuple of separation between guard ring edge and block.',
            edge_ncol='Number of columns on guard ring edge.  Use 0 for default.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(
            pmos_gr='pgr',
            nmos_gr='ngr',
            sep_ncol=(-1, -1),
            edge_ncol=0,
        )

    def get_schematic_class_inst(self) -> Optional[Type[Module]]:
        return self._sch_cls

    def get_layout_basename(self) -> str:
        cls_name: str = self.params['cls_name']
        cls_name = cls_name.split('.')[-1]
        return cls_name + 'GuardRing'

    def draw_layout(self) -> None:
        params = self.params
        cls_name: str = params['cls_name']
        params: Param = params['params']
        pmos_gr: str = params['pmos_gr']
        nmos_gr: str = params['nmos_gr']
        sep_ncol: Tuple[int, int] = params['sep_ncol']
        edge_ncol: int = params['edge_ncol']

        gen_cls = cast(Type[MOSBase], import_class(cls_name))
        master: MOSBase = self.new_template(gen_cls, params=params)

        _, sup_list = self.draw_guard_ring(master, pmos_gr, nmos_gr, sep_ncol, edge_ncol)
        for tile_idx, (vss_list, vdd_list) in enumerate(sup_list):
            for ridx, warr in enumerate(vss_list):
                self.add_pin(f'VSS_guard_{tile_idx}_{ridx}', warr)
            for ridx, warr in enumerate(vdd_list):
                self.add_pin(f'VDD_guard_{tile_idx}_{ridx}', warr)

    def draw_guard_ring(self, master: MOSBase, pmos_gr: str, nmos_gr: str,
                        sep_ncol: Tuple[int, int], edge_ncol: int
                        ) -> Tuple[PyLayInstance, List[Tuple[List[WireArray], List[WireArray]]]]:
        self._core = master
        self._sch_cls = master.get_schematic_class_inst()
        tinfo_table = master.tile_table

        # construct TilePattern object, and call draw_base()
        bot_pinfo = tinfo_table[self._get_gr_name(master, False)]
        top_pinfo = tinfo_table[self._get_gr_name(master, True)]
        tile_list = [TilePatternElement(bot_pinfo), master.get_tile_pattern_element(),
                     TilePatternElement(top_pinfo, flip=True)]
        self.draw_base((TilePattern(tile_list), tinfo_table))

        # get nmos/pmos guard ring type
        pmos_sub_type = tinfo_table[pmos_gr].get_row_place_info(0).row_info.row_type
        nmos_sub_type = tinfo_table[nmos_gr].get_row_place_info(0).row_info.row_type

        tech_cls = self.tech_cls
        if edge_ncol == 0:
            edge_ncol = tech_cls.gr_edge_col

        sep_l, sep_r = sep_ncol
        if sep_l < 0:
            sep_l = tech_cls.sub_sep_col
        if sep_r < 0:
            sep_r = tech_cls.sub_sep_col
        ncol = master.num_cols + 2 * edge_ncol + sep_l + sep_r
        ntile = master.num_tile_rows + 2
        inst = self.add_tile(master, 1, edge_ncol + sep_l)
        self.set_mos_size(num_cols=ncol, num_tiles=ntile)

        for name in inst.port_names_iter():
            self.reexport(inst.get_port(name))

        sup_list = []
        vdd_vm_list = []
        vss_vm_list = []
        vdd_hm_keys = []
        vss_hm_keys = []
        vdd_hm_dict = {}
        vss_hm_dict = {}
        grid = self.grid
        hm_layer = self.conn_layer + 1
        for tile_idx in range(ntile):
            cur_pinfo = self.get_tile_pinfo(tile_idx)
            vdd_hm_list = []
            vss_hm_list = []
            for ridx in range(cur_pinfo.num_rows):
                row_info = cur_pinfo.get_row_place_info(ridx).row_info
                row_type = row_info.row_type
                if row_type.is_substrate and row_info.guard_ring:
                    tid = self.get_track_id(ridx, MOSWireType.DS, 'guard', tile_idx=tile_idx)
                    sub = self.add_substrate_contact(ridx, 0, tile_idx=tile_idx, seg=ncol)
                    warr = self.connect_to_tracks(sub, tid)
                    coord = grid.track_to_coord(hm_layer, tid.base_index)
                    if row_type.is_pwell:
                        vss_hm_list.append(warr)
                        vss_hm_keys.append(coord)
                        vss_hm_dict[coord] = warr
                    else:
                        vdd_hm_list.append(warr)
                        vdd_hm_keys.append(coord)
                        vdd_hm_dict[coord] = warr
                else:
                    if row_type.is_substrate:
                        sub_type = pmos_sub_type if row_type.is_n_plus else nmos_sub_type
                    else:
                        sub_type = nmos_sub_type if row_type.is_n_plus else pmos_sub_type
                    sub0 = self.add_substrate_contact(ridx, 0, tile_idx=tile_idx, seg=edge_ncol,
                                                      guard_ring=True, sub_type=sub_type)
                    sub1 = self.add_substrate_contact(ridx, ncol, tile_idx=tile_idx, seg=edge_ncol,
                                                      guard_ring=True, flip_lr=True,
                                                      sub_type=sub_type)
                    if sub_type.is_pwell:
                        vss_vm_list.append(sub0)
                        vss_vm_list.append(sub1)
                    else:
                        vdd_vm_list.append(sub0)
                        vdd_vm_list.append(sub1)

            sup_list.append((vss_hm_list, vdd_hm_list))

        self._connect_vm(vss_vm_list, vss_hm_keys, vss_hm_dict)
        self._connect_vm(vdd_vm_list, vdd_hm_keys, vdd_hm_dict)

        self.sch_params = master.sch_params

        return inst, sup_list

    def _connect_vm(self, warr_list: List[WireArray], keys: List[int],
                    table: Dict[int, WireArray]) -> None:
        keys.sort()
        for warr in warr_list:
            idx = bisect_left(keys, warr.middle)
            if idx == 0:
                raise ValueError('Cannot find a lower horizontal wire to connect guard ring edge')
            self.connect_to_track_wires(warr, [table[keys[idx - 1]], table[keys[idx]]])

    def _get_gr_name(self, master: MOSBase, is_top: bool) -> str:
        if is_top:
            tinfo, _, flip = master.get_tile_info(master.num_tile_rows - 1)
            ridx = 0 if flip else tinfo.num_rows - 1
        else:
            tinfo, _, flip = master.get_tile_info(0)
            ridx = tinfo.num_rows - 1 if flip else 0

        mos_type = tinfo.get_row_place_info(ridx).row_info.row_type
        # if mos_type.is_substrate:
        #     raise ValueError('top and bottom row must be transistor row.')
        # return self.params['nmos_gr'] if mos_type.is_n_plus else self.params['pmos_gr']
        if mos_type.is_substrate:
            return self.params['pmos_gr'] if mos_type.is_n_plus else self.params['nmos_gr']
        else:
            return self.params['nmos_gr'] if mos_type.is_n_plus else self.params['pmos_gr']
