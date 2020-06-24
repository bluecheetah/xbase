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

from typing import Any, Optional, Dict, Type, Tuple, cast, List, Mapping

import abc

from pybag.core import BBox, Transform
from pybag.enum import Orientation

from bag.util.immutable import Param, ImmutableList
from bag.util.importlib import import_class
from bag.design.module import Module
from bag.layout.routing.grid import RoutingGrid
from bag.layout.data import TemplateEdgeInfo
from bag.layout.template import TemplateDB, TemplateBase
from bag.layout.core import PyLayInstance

from ..data import draw_layout_in_template
from ..exception import ODImplantEnclosureError

from .tech import MOSTech
from .util import MOSUsedArray
from .data import (
    MOSEdgeInfo, RowExtInfo, BlkExtInfo, MOSRowInfo, RowPlaceInfo
)
from .base import MOSBase, MOSBasePlaceInfo
from .primitives import MOSSpace, MOSExt, MOSEnd, MOSRowEdge, MOSCorner, MOSExtEdge, MOSExtGR


class MOSBaseWrapper(TemplateBase, abc.ABC):

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self._core: Optional[MOSBase] = None
        self._xform: Transform = Transform()

    @property
    def core(self) -> MOSBase:
        return self._core

    @property
    def core_xform(self) -> Transform:
        return self._xform

    def get_schematic_class_inst(self) -> Optional[Type[Module]]:
        return self._core.get_schematic_class_inst()

    def draw_boundaries(self, master: MOSBase, top_layer: int, *,
                        half_blk_x: bool = True, half_blk_y: bool = True) -> PyLayInstance:
        self._core = master

        tech_cls = master.tech_cls
        bbox = master.bound_box
        used_arr = master.used_array

        w_blk, h_blk = self.grid.get_block_size(top_layer,
                                                half_blk_x=half_blk_x, half_blk_y=half_blk_y)

        w_master = bbox.w
        h_master = bbox.h
        w_edge = tech_cls.get_edge_width(w_master, w_blk)
        base_end_info = tech_cls.get_mos_base_end_info(master.place_info, h_blk)

        # get top/bottom boundary delta/height
        num_tiles = used_arr.num_tiles
        idx_bot = int(used_arr.get_flip_tile(0))
        idx_top = int(not used_arr.get_flip_tile(num_tiles - 1))
        dy_bot = base_end_info.h_blk[idx_bot]
        dy_top = base_end_info.h_blk[idx_top]
        h_end_bot = base_end_info.h_mos_end[idx_bot]
        h_end_top = base_end_info.h_mos_end[idx_top]

        self._xform = Transform(w_edge, dy_bot)
        inst = self.add_instance(master, inst_name='X0', xform=self._xform)

        my_used_arr = used_arr.get_copy()
        sd_pitch = tech_cls.sd_pitch
        w_tot = w_edge * 2 + w_master
        h_tot = dy_bot + dy_top + h_master
        self._fill_space(master.grid, tech_cls, w_edge, my_used_arr, sd_pitch, w_tot, h_tot,
                         dy_bot, h_end_bot, h_end_top)

        self.set_size_from_bound_box(top_layer, BBox(0, 0, w_tot, h_tot))
        return inst

    def _fill_space(self, grid: RoutingGrid, tech_cls: MOSTech, w_edge: int, used_arr: MOSUsedArray,
                    sd_pitch: int, w_tot: int, h_tot: int, dy: int, h_end_bot: int, h_end_top: int
                    ) -> None:
        lch = tech_cls.lch
        arr_options = tech_cls.arr_options

        dx = w_edge
        num_tiles = used_arr.num_tiles
        num_cols = used_arr.num_cols
        last_flat_row_idx = used_arr.num_flat_rows - 1

        # add space blocks
        for tile_idx in range(num_tiles):
            pinfo = used_arr.get_tile_pinfo(tile_idx)
            for row_idx in range(pinfo.num_rows):
                for (start, end), cur_left, cur_right in used_arr.get_complement(tile_idx, row_idx,
                                                                                 0, num_cols):
                    seg = end - start
                    self._add_mos_space(pinfo, used_arr, sd_pitch, dx, dy, tile_idx, row_idx,
                                        start, seg, cur_left, cur_right)

        # draw edges and extensions
        for tile_idx in range(num_tiles):
            pinfo, tile_yb, flip_tile = used_arr.get_tile_info(tile_idx)
            if flip_tile:
                row_range = range(pinfo.num_rows - 1, -1, -1)
            else:
                row_range = range(pinfo.num_rows)

            tile_h = pinfo.height
            tile_last_row = row_range.stop - row_range.step
            for row_idx in row_range:
                flat_row_idx = used_arr.get_flat_row_idx_and_flip(tile_idx, row_idx)[0]
                row_info, y_edge, orient_edge = MOSBase.get_mos_row_info(pinfo, tile_yb,
                                                                         flip_tile, row_idx)
                # draw row edges
                rpinfo = pinfo.get_row_place_info(row_idx)
                self._add_row_edges(w_edge, w_tot, y_edge + dy, orient_edge, row_info,
                                    used_arr.get_edge_info(flat_row_idx, 0),
                                    used_arr.get_edge_info(flat_row_idx, num_cols),
                                    f'XR{flat_row_idx}', arr_options)

                if flat_row_idx != last_flat_row_idx:
                    # draw extensions between rows
                    be_bot = used_arr.get_top_info(flat_row_idx)
                    be_top = used_arr.get_bottom_info(flat_row_idx + 1)

                    # get bottom Y coordinate
                    yb_ext = self._get_row_yblk(rpinfo, flip_tile, tile_yb, tile_h)[1]

                    if row_idx == tile_last_row:
                        tmp = used_arr.get_tile_info(tile_idx + 1)
                        next_pinfo, next_tile_yb, next_flip_tile = tmp
                        next_row_idx = next_pinfo.num_rows - 1 if next_flip_tile else 0
                    else:
                        next_pinfo = pinfo
                        next_tile_yb = tile_yb
                        next_flip_tile = flip_tile
                        next_row_idx = row_idx + row_range.step

                    next_rpinfo = next_pinfo.get_row_place_info(next_row_idx)
                    next_ri = next_rpinfo.row_info
                    yt_ext = self._get_row_yblk(next_rpinfo, next_flip_tile, next_tile_yb,
                                                next_pinfo.height)[0]

                    ext_h = yt_ext - yb_ext
                    if row_info.flip == flip_tile:
                        re_bot = row_info.top_ext_info
                    else:
                        re_bot = row_info.bot_ext_info
                    if next_ri.flip == next_flip_tile:
                        re_top = next_ri.bot_ext_info
                    else:
                        re_top = next_ri.top_ext_info
                    self._add_ext_row(grid, tech_cls, lch, num_cols, re_bot, re_top, be_bot,
                                      be_top, dx, yb_ext + dy, ext_h, w_edge, w_tot,
                                      f'XR{flat_row_idx}')

        # draw ends
        pinfo, _, flip_tile = used_arr.get_tile_info(0)
        flat_row_idx = pinfo.num_rows - 1 if flip_tile else 0
        ri = pinfo.get_row_place_info(flat_row_idx).row_info
        re = ri.bot_ext_info if ri.flip == flip_tile else ri.top_ext_info
        be = self._add_mos_end(grid, lch, dx, 0, Orientation.R0, h_end_bot, re, num_cols, 'BE',
                               arr_options)
        pinfo, _, flip_tile = used_arr.get_tile_info(num_tiles - 1)
        flat_row_idx = 0 if flip_tile else pinfo.num_rows - 1
        ri = pinfo.get_row_place_info(flat_row_idx).row_info
        re = ri.top_ext_info if ri.flip == flip_tile else ri.bot_ext_info
        te = self._add_mos_end(grid, lch, dx, h_tot, Orientation.MX, h_end_top, re, num_cols, 'TE',
                               arr_options)
        # draw corners
        cb = self.new_template(MOSCorner,
                               params=dict(lch=lch, einfo=be, blk_w=w_edge, blk_h=h_end_bot,
                                           arr_options=arr_options))
        ct = self.new_template(MOSCorner,
                               params=dict(lch=lch, einfo=te, blk_w=w_edge, blk_h=h_end_top,
                                           arr_options=arr_options))
        self.add_instance(cb, inst_name='XCLL')
        self.add_instance(cb, inst_name='XCLR', xform=Transform(w_tot, 0, Orientation.MY))
        self.add_instance(ct, inst_name='XCUL', xform=Transform(0, h_tot, Orientation.MX))
        self.add_instance(ct, inst_name='XCUR', xform=Transform(w_tot, h_tot, Orientation.R180))

        # override cell boundary
        pr_xl, pr_yb = cb.corner
        pr_xr, pr_yt = ct.corner
        pr_xr = w_tot - pr_xr
        pr_yt = h_tot - pr_yt
        self.add_cell_boundary(BBox(pr_xl, pr_yb, pr_xr, pr_yt))

        # set edge parameters
        self.edge_info = TemplateEdgeInfo(cb.left_edge, cb.bottom_edge,
                                          ct.left_edge, ct.bottom_edge)

    @classmethod
    def _get_row_yblk(cls, rpinfo: RowPlaceInfo, flip_tile: bool, tile_yb: int, tile_h: int
                      ) -> Tuple[int, int]:
        if flip_tile:
            offset = tile_yb + tile_h
            return offset - rpinfo.yt_blk, offset - rpinfo.yb_blk
        else:
            offset = tile_yb
            return rpinfo.yb_blk + offset, rpinfo.yt_blk + offset

    def _add_mos_end(self, mos_grid: RoutingGrid, lch: int, dx: int, y: int, orient: Orientation,
                     blk_h: int, einfo: RowExtInfo, fg: int, prefix: str,
                     arr_options: Mapping[str, Any]) -> MOSEdgeInfo:
        master = self.new_template(MOSEnd, params=dict(
            lch=lch, blk_h=blk_h, num_cols=fg, einfo=einfo, arr_options=arr_options,
        ), grid=mos_grid)
        self.add_instance(master, inst_name=prefix, xform=Transform(dx, y, orient))
        return master.edge_info

    def _add_mos_space(self, pinfo: MOSBasePlaceInfo, used_arr: MOSUsedArray, sd_pitch: int,
                       dx: int, dy: int, tile_idx: int, row_idx: int,
                       start: int, seg: int, left: MOSEdgeInfo, right: MOSEdgeInfo) -> None:
        params = dict(
            row_info=pinfo.get_row_place_info(row_idx).row_info,
            num_cols=seg,
            left_info=left,
            right_info=right,
            arr_options=pinfo.arr_info.arr_options,
        )
        try:
            master = self.new_template(MOSSpace, params=params, grid=pinfo.grid)
        except ODImplantEnclosureError as err:
            raise ValueError('Not enough space for OD-implant enclosure.\n'
                             f'Error on tile {tile_idx}, row {row_idx}, '
                             f'column [{start}, {start + seg})') from err

        y0, orient = MOSBase.register_device(used_arr, tile_idx, row_idx, start, seg, False,
                                             master.left_info, master.right_info, master.top_info,
                                             master.bottom_info, None)

        x0 = sd_pitch * start
        self.add_instance(master, inst_name=f'XT{tile_idx}R{row_idx}C{start}',
                          xform=Transform(x0 + dx, y0 + dy, orient))

    def _add_row_edges(self, w_edge: int, w_tot: int, y: int, orient: Orientation,
                       row_info: MOSRowInfo, left_info: MOSEdgeInfo, right_info: MOSEdgeInfo,
                       prefix: str, arr_options: Mapping[str, Any]) -> None:
        left_master = self.new_template(MOSRowEdge, params=dict(
            blk_w=w_edge, rinfo=row_info, einfo=left_info, arr_options=arr_options))
        right_master = self.new_template(MOSRowEdge, params=dict(
            blk_w=w_edge, rinfo=row_info, einfo=right_info, arr_options=arr_options))
        self.add_instance(left_master, inst_name=f'{prefix}EGL', xform=Transform(0, y, orient))
        self.add_instance(right_master, inst_name=f'{prefix}EGR',
                          xform=Transform(w_tot, y, orient.flip_lr()))

    def _add_ext_row(self, grid: RoutingGrid, tech: MOSTech, lch: int, fg: int, re_bot: RowExtInfo,
                     re_top: RowExtInfo, be_bot: List[BlkExtInfo], be_top: List[BlkExtInfo],
                     dx: int, y0: int, ext_h: int, w_edge: int, w_tot: int, prefix: str) -> None:
        arr_options = tech.arr_options

        cut_mode, bot_exty, top_exty = tech.get_extension_regions(re_bot, re_top, ext_h)
        if cut_mode.num_cut == 2 and bot_exty == top_exty == 0:
            if be_bot[0].guard_ring and be_bot[0].fg_dev[0][1] is be_top[0].fg_dev[0][1]:
                # this is extension within a guard ring
                if len(be_bot) > 1:
                    fg_edge = be_bot[0].fg
                    fg_gr = fg_edge + be_bot[1].fg_dev[0][0]
                else:
                    fg_edge = be_top[0].fg
                    fg_gr = fg_edge + be_top[1].fg_dev[0][0]

                ext_dx = fg_gr * tech.sd_pitch
                ext_params = dict(lch=lch, num_cols=fg - 2 * fg_gr, height=ext_h, bot_info=re_bot,
                                  top_info=re_top, gr_info=(fg_edge, fg_gr),
                                  arr_options=arr_options)
                ext_master = self.new_template(MOSExt, params=ext_params, grid=grid)

                # add guard ring
                gr_params = dict(lch=lch, num_cols=fg_gr, edge_cols=fg_edge, height=ext_h,
                                 bot_info=re_bot, top_info=re_top, sub_type=be_bot[0].fg_dev[0][1],
                                 einfo=ext_master.edge_info, arr_options=arr_options)
                gr_master = self.new_template(MOSExtGR, params=gr_params, grid=grid)
                edge_info = gr_master.edge_info

                self.add_instance(gr_master, inst_name=f'{prefix}EXGRL', xform=Transform(dx, y0))
                self.add_instance(gr_master, inst_name=f'{prefix}EXGRR',
                                  xform=Transform(w_tot - dx, y0, Orientation.MY))
            else:
                ext_dx = 0
                ext_params = dict(lch=lch, num_cols=fg, height=ext_h, bot_info=re_bot,
                                  top_info=re_top, gr_info=(0, 0), arr_options=arr_options)
                ext_master = self.new_template(MOSExt, params=ext_params, grid=grid)
                edge_info = ext_master.edge_info

            self.add_instance(ext_master, inst_name=f'{prefix}EX', xform=Transform(dx + ext_dx, y0))
            edge_master = self.new_template(MOSExtEdge, params=dict(
                lch=lch, blk_w=w_edge, einfo=edge_info, arr_options=arr_options))
            self.add_instance(edge_master, inst_name=f'{prefix}EXEDGEL', xform=Transform(0, y0))
            self.add_instance(edge_master, inst_name=f'{prefix}EXEDGER',
                              xform=Transform(w_tot, y0, Orientation.MY))
        else:
            # draw extension geometries
            info = tech.get_ext_geometries(re_bot, re_top, ImmutableList(be_bot),
                                           ImmutableList(be_top), cut_mode, bot_exty, top_exty,
                                           dx, y0, w_edge)
            draw_layout_in_template(self, info, set_bbox=False)


class GenericWrapper(MOSBaseWrapper):
    """A MOSArrayWrapper that works with any given generator class."""

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBaseWrapper.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            cls_name='wrapped class name.',
            params='parameters for the wrapped class.',
            export_hidden='True to export hidden pins.',
            half_blk_x='Defaults to True.  True to allow half-block width.',
            half_blk_y='Defaults to True.  True to allow half-block height.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(export_hidden=False, half_blk_x=True, half_blk_y=True)

    def get_layout_basename(self) -> str:
        cls_name: str = self.params.get('cls_name', '')
        if cls_name:
            cls_name = cls_name.split('.')[-1]
            if cls_name.endswith('Core'):
                return cls_name[:-4]
            return cls_name + 'Wrap'
        else:
            # if sub-class of GenericWrapper does not have cls_name parameter,
            # use default base name
            return super(GenericWrapper, self).get_layout_basename()

    def draw_layout(self):
        params = self.params
        cls_name: str = params['cls_name']
        dut_params: Param = params['params']
        export_hidden: bool = params['export_hidden']
        half_blk_x: bool = params['half_blk_x']
        half_blk_y: bool = params['half_blk_y']

        gen_cls = cast(Type[MOSBase], import_class(cls_name))
        master = self.new_template(gen_cls, params=dut_params)

        self.wrap_mos_base(master, export_hidden, half_blk_x=half_blk_x, half_blk_y=half_blk_y)

    def wrap_mos_base(self, master: MOSBase, export_hidden: bool, half_blk_x: bool = True,
                      half_blk_y: bool = True) -> None:
        grid = self.grid
        top_layer = master.top_layer

        inst = self.draw_boundaries(master, top_layer, half_blk_x=half_blk_x, half_blk_y=half_blk_y)

        def private_port_check(lay_id: int) -> bool:
            if lay_id <= top_layer and not grid.is_horizontal(lay_id):
                print(f'WARNING: ports on private layer {lay_id} detected, '
                      f'converting to primitive ports.')
                return True
            return False

        # re-export pins
        for name in inst.port_names_iter():
            if not master.get_port(name).hidden or export_hidden:
                self.reexport(inst.get_primitive_port(name, private_port_check))

        # pass out schematic parameters
        self.sch_params = master.sch_params
