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

    @property
    def mim_config(self) -> Dict[str, Any]:
        return self._mim_config

    # functions getting technology information 
    @abc.abstractmethod
    def get_mim_cap_info(self, top_layer: int,
                         bot_layer: int, width_total: int,
                         width: int, height: int, array: bool,
                         unit_width: Optional[int],
                         unit_height: Optional[int]) -> MIMLayInfo:
        raise NotImplementedError('Not implemented')
