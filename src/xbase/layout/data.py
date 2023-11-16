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

from typing import Tuple, Iterable, Union, Any, Optional, Mapping

from dataclasses import dataclass

from pybag.core import BBox, Transform, BBoxCollection

from bag.util.math import HalfInt
from bag.util.immutable import ImmutableSortedDict, ImmutableList
from bag.layout.routing.base import WireArray, TrackID
from bag.layout.routing.grid import RoutingGrid
from bag.layout.template import TemplateBase


@dataclass(eq=True, frozen=True)
class WireArrayInfo:
    layer: int
    track: HalfInt
    lower: int
    upper: int
    width: int
    num: int
    pitch: Union[int, HalfInt]

    def to_warr(self, grid: RoutingGrid) -> WireArray:
        return WireArray(TrackID(self.layer, self.track,
                                 width=self.width, num=self.num, pitch=self.pitch, grid=grid),
                         self.lower, self.upper)


@dataclass(eq=True, frozen=True)
class ViaInfo:
    via_type: str
    xc: int
    yc: int
    w: int
    h: int
    enc1: Tuple[int, int, int, int] = (0, 0, 0, 0)
    enc2: Tuple[int, int, int, int] = (0, 0, 0, 0)
    vnx: int = 1
    vny: int = 1
    vspx: int = 0
    vspy: int = 0
    nx: int = 1
    ny: int = 1
    spx: int = 0
    spy: int = 0
    priority: int = 0


@dataclass(eq=True, frozen=True)
class InstInfo:
    """The primitive instance information object."""
    lib_name: str
    cell_name: str
    xform: Optional[Transform] = None
    nx: int = 1
    ny: int = 1
    spx: int = 0
    spy: int = 0
    params: Optional[Mapping[str, Any]] = None
    commit: bool = True


@dataclass(eq=True, frozen=True)
class LayoutInfo:
    """The layout information object."""
    rect_dict: ImmutableSortedDict[Tuple[str, str], BBoxCollection]
    warr_list: ImmutableList[WireArrayInfo]
    via_list: ImmutableList[ViaInfo]
    inst_list: ImmutableList[InstInfo]
    bound_box: BBox


class LayoutInfoBuilder:
    def __init__(self):
        self._lp_dict = {}
        self._via_list = []
        self._warr_list = []
        self._inst_list = []

    def add_rect_arr(self, key: Tuple[str, str], box: BBox,
                     nx: int = 1, ny: int = 1, spx: int = 0, spy: int = 0) -> None:
        r_list = self._lp_dict.get(key, None)
        if r_list is None:
            r_list = self._lp_dict[key] = BBoxCollection()
        r_list.add_rect_arr(box, nx=nx, ny=ny, spx=spx, spy=spy)

    def add_warr(self, layer: int, track: HalfInt, lower: int, upper: int, width: int,
                 num: int = 1, pitch: Union[int, HalfInt] = 0) -> None:
        self._warr_list.append(WireArrayInfo(layer, track, lower, upper, width,
                                             num=num, pitch=pitch))

    def add_via(self, vinfo: ViaInfo) -> None:
        self._via_list.append(vinfo)

    def add_rect_iter(self, key: Tuple[str, str], rect_iter: Iterable[BBox]
                      ) -> None:
        r_list = self._lp_dict.get(key, None)
        if r_list is None:
            r_list = self._lp_dict[key] = BBoxCollection()
        for box in rect_iter:
            r_list.add_rect_arr(box)

    def add_instance_primitive(self, lib_name: str, cell_name: str, *, xform: Optional[Transform] = None,
                               nx: int = 1, ny: int = 1, spx: int = 0, spy: int = 0,
                               params: Optional[Mapping[str, Any]] = None, commit: bool = True) -> None:
        self._inst_list.append(InstInfo(lib_name, cell_name, xform, nx, ny, spx, spy, params, commit))

    def get_info(self, bnd_box: BBox) -> LayoutInfo:
        return LayoutInfo(ImmutableSortedDict(self._lp_dict), ImmutableList(self._warr_list),
                          ImmutableList(self._via_list), ImmutableList(self._inst_list), bnd_box)


def draw_layout_in_template(template: TemplateBase, lay_info: LayoutInfo,
                            set_bbox: bool = True) -> None:
    for lay_purp, box_col in lay_info.rect_dict.items():
        template.add_bbox_collection(lay_purp, box_col)

    for winfo in lay_info.warr_list:
        template.add_wires(winfo.layer, winfo.track, winfo.lower, winfo.upper,
                           width=winfo.width, num=winfo.num, pitch=winfo.pitch)

    for vinfo in lay_info.via_list:
        template.add_via_primitive(vinfo.via_type, Transform(vinfo.xc, vinfo.yc), vinfo.w,
                                   vinfo.h, num_rows=vinfo.vny, num_cols=vinfo.vnx,
                                   sp_rows=vinfo.vspy, sp_cols=vinfo.vspx, enc1=vinfo.enc1,
                                   enc2=vinfo.enc2, nx=vinfo.nx, ny=vinfo.ny, spx=vinfo.spx,
                                   spy=vinfo.spy, priority=vinfo.priority)

    for inst_info in lay_info.inst_list:
        template.add_instance_primitive(inst_info.lib_name, inst_info.cell_name, xform=inst_info.xform,
                                        nx=inst_info.nx, ny=inst_info.ny, spx=inst_info.spx, spy=inst_info.spy,
                                        params=inst_info.params, commit=inst_info.commit)

    if set_bbox:
        template.prim_bound_box = lay_info.bound_box


@dataclass(eq=True, frozen=True)
class CornerLayInfo:
    """The corner layout information object."""
    lay_info: LayoutInfo
    corner: Tuple[int, int]
    edgel: ImmutableSortedDict[str, Any]
    edgeb: ImmutableSortedDict[str, Any]
