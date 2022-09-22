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

"""This module defines abstract analog mim cap template classes.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from typing import TYPE_CHECKING, Tuple, Optional, Dict, Any, List, Mapping

import abc
import math
import bisect

from bag.math import lcm
from bag.util.immutable import Param, ImmutableList
from bag.layout.tech import TechInfo
from bag.layout.routing.grid import TrackSpec

from ..data import LayoutInfo, LayoutInfoBuilder

if TYPE_CHECKING:
    from .base import MOSBasePlaceInfo


@dataclass(eq=True, frozen=True)
class MIMLayInfo:
    """The transistor block layout information object."""
    lay_info: LayoutInfo
    pin_bot_yl: int
    pin_bot_yh: int
    pin_top_yl: int
    pin_top_yh: int
    pin_bot_xh: int


class MIMTech(abc.ABC):
    """An abstract class for drawing mim cap related layout
    
    Parameters
    ------------------
    tech_info : TechInfo
        the TechInfo object
    bot_layer :
    top_layer :

    """
    def __init__(self, tech_info: TechInfo, ) -> None:
        self._tech_info = tech_info
        self._mim_config = {}
        for k, v in tech_info.config['mim'].items():
            self._mim_config[k] = v
        
        self._resolution = int(tech_info.config['resolution'])

    @property
    def mim_config(self) -> Dict[str, Any]:
        return self._mim_config

    @property
    def resolution(self) -> int:
        return self._resolution

    # functions getting technology information 
    @abc.abstractmethod
    def get_mim_cap_info(self, top_layer: int,
                         bot_layer: int, width_total: int,
                         width: int, height: int, array: bool,
                         unit_width: Optional[int],
                         unit_height: Optional[int]) -> MIMLayInfo:
        raise NotImplementedError('Not implemented')