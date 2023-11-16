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

from typing import Any, Dict, Optional, Type, Mapping

from bag.util.immutable import Param
from bag.layout.template import TemplateDB
from bag.design.module import Module

from xbase.layout.array.base import ArrayBase
from xbase.layout.res.base import ResBasePlaceInfo, ResArrayBase


class ResOnlyCore(ArrayBase):
    """An array of resistors"""

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        ArrayBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            pinfo='ResBasePlaceInfo object.',
        )

    def draw_layout(self):
        pinfo = ResBasePlaceInfo.make_place_info(self.grid, self.params['pinfo'])
        self.draw_base(pinfo)


class ResArray(ResArrayBase):
    """Another array of resistors"""

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        ResArrayBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return None

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            pinfo='ResBasePlaceInfo object',
        )

    def draw_layout(self) -> None:
        params = self.params
        self.draw_base(params['pinfo'])

