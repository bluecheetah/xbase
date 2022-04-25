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

from typing import Union

from enum import Enum, Flag, auto, IntEnum


class MOSType(Enum):
    nch = 0
    ptap = 1
    pch = 2
    ntap = 3

    @property
    def is_substrate(self) -> bool:
        return self is MOSType.ptap or self is MOSType.ntap

    @property
    def is_pwell(self) -> bool:
        return self is MOSType.nch or self is MOSType.ptap

    @property
    def sub_type(self) -> MOSType:
        return MOSType.ptap if self is MOSType.nch or self is MOSType.ptap else MOSType.ntap

    @property
    def is_n_plus(self) -> bool:
        return self is MOSType.ntap or self is MOSType.nch

    def is_same_implant(self, other: MOSType) -> bool:
        return self.is_n_plus == other.is_n_plus


class SubPortMode(Enum):
    EVEN = 0
    ODD = 1
    BOTH = 2


class MOSCutMode(Flag):
    BOT = auto()
    TOP = auto()
    MID = auto()
    BOTH = BOT | TOP

    @property
    def num_cut(self) -> int:
        if not self:
            return 0
        if self is MOSCutMode.BOTH:
            return 2
        return 1


# Note: make this IntEnum so it is sortable by ImmutableSortedDict.
class MOSWireType(IntEnum):
    """
    These describe the placements of tracks above the conn_layer, relative to 
    the conn_layer ports.

    G: tracks directly over gate connection
    G_MATCH: tracks south of gate connection to match / reduce gate parasitics
    DS: tracks directly over drain / source connection
    DS_GATE: track over drain/source, overlapping with gate if possible
    DS_MATCH: tracks north of drain/source conn to match / reduce parasitics
    G2: for double gate transistors, tracks directly over the 2nd gate
    G2_MATCH: similar to G_MATCH for double gate transistors

    For flipped transistors, G will be at the top, DS / G2 will be at the bottom.
    For not flipped transistors, G will be at the bottom, DS / G2 will be at the top.

    """
    G = 0
    G_MATCH = 1
    DS = 2
    DS_GATE = 3
    DS_MATCH = 4
    G2 = 5
    G2_MATCH = 6

    @property
    def is_gate(self) -> bool:
        return self is MOSWireType.G or self is MOSWireType.G_MATCH

    @property
    def is_gate2(self) -> bool:
        return self is MOSWireType.G2 or self is MOSWireType.G2_MATCH

    @property
    def is_physical(self) -> bool:
        return not (self is MOSWireType.G_MATCH or self is MOSWireType.DS_MATCH
                    or self is MOSWireType.G2_MATCH)


class MOSPortType(Enum):
    G = 0
    D = 1
    S = 2


class MOSAbutMode(Enum):
    NONE = 0
    OVERLAY = 1
    UPDATE = 2


class Alignment(Enum):
    LOWER_COMPACT = 0
    CENTER_COMPACT = 1
    UPPER_COMPACT = 2

    @property
    def is_center(self) -> bool:
        return self is Alignment.CENTER_COMPACT


class ExtendMode(Enum):
    X = 0
    Y = 1
    AREA = 2


class DeviceType(Enum):
    MOS = 0
    RES = 1
    DIODE = 2


class CornerType(Enum):
    BOTTOM_LEFT = 0
    BOTTOM_RIGHT = 1
    TOP_LEFT = 2
    TOP_RIGHT = 3
    BL = 0
    BR = 1
    TL = 2
    TR = 3

    @property
    def is_bottom(self) -> bool:
        return self.value & 2 == 0

    @property
    def is_left(self) -> bool:
        return self.value & 1 == 0

    @classmethod
    def convert(cls, val: Union[int, str]) -> CornerType:
        if isinstance(val, str):
            return CornerType[val]
        else:
            return CornerType(val)
