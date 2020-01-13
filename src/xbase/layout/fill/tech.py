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

"""This module defines abstract analog mosfet template classes.
"""

from __future__ import annotations

import abc

from bag.util.immutable import Param
from bag.layout.tech import TechInfo

from ..data import LayoutInfo


class FillTech(abc.ABC):
    """An abstract class for drawing transistor related layout.

    This class defines various methods use to draw layouts used by MOSBase.

    Parameters
    ----------
    tech_info : TechInfo
        the TechInfo object.
    """

    def __init__(self, tech_info: TechInfo) -> None:
        self._tech_info = tech_info
        self._fill_config = tech_info.config['fill']

    @abc.abstractmethod
    def get_fill_info(self, mos_type: str, threshold: str, w: int, h: int,
                      el: Param, eb: Param, er: Param, et: Param) -> LayoutInfo:
        raise NotImplementedError('Not implemented')

    @property
    def tech_info(self) -> TechInfo:
        return self._tech_info

    @property
    def mos_type_default(self) -> str:
        return self._fill_config['mos_type_default']

    @property
    def threshold_default(self) -> str:
        return self._fill_config['threshold_default']
