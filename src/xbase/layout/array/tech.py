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

"""This module defines a technology base class for generating device arrays
"""

from __future__ import annotations

from typing import Tuple, Any, List, Mapping, Optional, Dict

import abc

from pybag.core import COORD_MAX

from bag.util.math import HalfInt
from bag.util.immutable import ImmutableSortedDict
from bag.util.search import BinaryIterator
from bag.layout.tech import TechInfo
from bag.layout.routing.base import TrackManager
from bag.layout.routing.grid import TrackSpec

from ..enum import Alignment, ExtendMode
from ..wires import WireSpecs, WireLookup
from ..data import LayoutInfo, CornerLayInfo
from .data import ArrayLayInfo, ArrayEndInfo

WireDictType = ImmutableSortedDict[Tuple[str, int], Tuple[HalfInt, str]]


class ArrayTech(abc.ABC):
    def __init__(self, tech_info: TechInfo, dev_name: str, **kwargs: Any) -> None:
        self._tech_info = tech_info
        kwargs['dev_name'] = dev_name
        self._kwargs = kwargs

    @property
    @abc.abstractmethod
    def min_size(self) -> Tuple[int, int]:
        return 1, 1

    @property
    @abc.abstractmethod
    def blk_pitch(self) -> Tuple[int, int]:
        return 1, 1

    @property
    @abc.abstractmethod
    def conn_layer(self) -> int:
        return 1

    @abc.abstractmethod
    def get_track_specs(self, conn_layer: int, top_layer: int) -> List[TrackSpec]:
        raise NotImplementedError('Not implemented.')

    @abc.abstractmethod
    def get_edge_width(self, info: ImmutableSortedDict[str, Any], arr_dim: int, blk_pitch: int
                       ) -> int:
        raise NotImplementedError('Not implemented.')

    @abc.abstractmethod
    def get_end_height(self, info: ImmutableSortedDict[str, Any], arr_dim: int, blk_pitch: int
                       ) -> int:
        raise NotImplementedError('Not implemented.')

    @abc.abstractmethod
    def get_blk_info(self, conn_layer: int, w: int, h: int, nx: int, ny: int, **kwargs: Any
                     ) -> Optional[ArrayLayInfo]:
        raise NotImplementedError('Not implemented.')

    @abc.abstractmethod
    def get_edge_info(self, w: int, h: int, info: ImmutableSortedDict[str, Any], **kwargs: Any
                      ) -> LayoutInfo:
        raise NotImplementedError('Not implemented.')

    @abc.abstractmethod
    def get_end_info(self, w: int, h: int, info: ImmutableSortedDict[str, Any], **kwargs: Any
                     ) -> ArrayEndInfo:
        raise NotImplementedError('Not implemented.')

    @abc.abstractmethod
    def get_corner_info(self, w: int, h: int, info: ImmutableSortedDict[str, Any], **kwargs: Any
                        ) -> CornerLayInfo:
        raise NotImplementedError('Not implemented.')

    @property
    def desc(self) -> str:
        name = self.__class__.__name__
        try:
            idx = name.find('Tech')
            return name[:idx]
        except ValueError:
            return 'Array'

    @property
    def tech_info(self) -> TechInfo:
        return self._tech_info

    @property
    def tech_kwargs(self) -> Mapping[str, Any]:
        return self._kwargs

    def size_unit_block(self, conn_layer: int, top_layer: int, nx: int, ny: int,
                        tr_manager: TrackManager, wire_specs: Mapping[int, Any], mode: ExtendMode,
                        max_ext: int = 1000, **kwargs: Any
                        ) -> Tuple[int, int, Dict[int, WireLookup], ArrayLayInfo]:
        wire_specs = WireSpecs.make_wire_specs(conn_layer, top_layer, tr_manager, wire_specs,
                                               min_size=self.min_size, blk_pitch=self.blk_pitch,
                                               align_default=Alignment.CENTER_COMPACT)

        blk_info: Optional[ArrayLayInfo] = None
        w_min, h_min = wire_specs.min_size
        blk_w, blk_h = wire_specs.blk_size
        w = w_min
        h = h_min
        opt_area = COORD_MAX ** 2

        def helper_fun(w_test: int, h_test: int, binfo: Optional[ArrayLayInfo],
                       wc: int, hc: int, opt_a: int, iterator: BinaryIterator
                       ) -> Tuple[Optional[ArrayLayInfo], int, int, int]:
            cur_area = w_test * h_test
            if cur_area >= opt_a:
                # this point can't beat current optimum
                iterator.down()
                return binfo, wc, hc, opt_a
            else:
                cur_info = self.get_blk_info(conn_layer, w_test, h_test, nx, ny, **kwargs)
                if cur_info is None:
                    iterator.up()
                    return binfo, wc, hc, opt_a
                else:
                    # found new optimum
                    iterator.down()
                    return cur_info, w_test, h_test, cur_area

        if mode is ExtendMode.AREA:
            # extend in both direction
            # linear search in height, binary search in width
            # in this way, for same area, use height as tie breaker
            for h_cur in range(h_min, h_min + max_ext * blk_h, blk_h):
                if w_min * h_cur >= opt_area:
                    # terminate linear search
                    break
                bin_iter = BinaryIterator(w_min, w_min + max_ext * blk_w, step=blk_w)
                while bin_iter.has_next():
                    w_cur = bin_iter.get_next()
                    blk_info, w, h, opt_area = helper_fun(w_cur, h_cur, blk_info, w, h, opt_area,
                                                          bin_iter)
        elif mode is ExtendMode.X:
            h_cur = h_min
            bin_iter = BinaryIterator(w_min, w_min + max_ext * blk_w, step=blk_w)
            while bin_iter.has_next():
                w_cur = bin_iter.get_next()
                blk_info, w, h, opt_area = helper_fun(w_cur, h_cur, blk_info, w, h, opt_area,
                                                      bin_iter)
        else:
            w_cur = w_min
            bin_iter = BinaryIterator(h_min, h_min + max_ext * blk_h, step=blk_h)
            while bin_iter.has_next():
                h_cur = bin_iter.get_next()
                blk_info, w, h, opt_area = helper_fun(w_cur, h_cur, blk_info, w, h, opt_area,
                                                      bin_iter)

        if blk_info is None:
            raise ValueError(f'Failed to find legal resistor unit block size '
                             f'with max_ext={max_ext}')

        return w, h, wire_specs.place_wires(tr_manager, w, h), blk_info
