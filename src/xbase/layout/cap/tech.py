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
from dataclasses import dataclass

from typing import Any, Mapping, Tuple

import abc

from bag.layout.tech import TechInfo

from ..data import LayoutInfo


@dataclass(eq=True, frozen=True)
class MIMLayInfo:
    """The mim block layout information object."""
    lay_info: LayoutInfo
    pin_bot_y: Tuple[int, int]
    pin_top_y: Tuple[int, int]
    pin_bot_xl: int
    pin_top_xh: int


class MIMTech(abc.ABC):
    """An abstract class for drawing mim cap related layout
    
    Parameters
    ------------------
    tech_info : TechInfo
        the TechInfo object
    """
    def __init__(self, tech_info: TechInfo) -> None:
        self._tech_info = tech_info
        self._mim_config = {}
        for k, v in tech_info.config['mim'].items():
            self._mim_config[k] = v

    @property
    def mim_config(self) -> Mapping[str, Any]:
        return self._mim_config

    # functions getting technology information 
    @abc.abstractmethod
    def get_port_layers(self, mim_type: str) -> Tuple[int, int]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_mim_cap_info(self, bot_layer: int, top_layer: int, unit_width: int, unit_height: int,
                         num_rows: int, num_cols: int, dum_row_b: int, dum_row_t: int, dum_col_l: int, dum_col_r: int,
                         bot_w: int, top_w: int) -> MIMLayInfo:
        raise NotImplementedError

