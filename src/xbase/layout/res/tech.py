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

"""This module defines resistor technology class.
"""

from __future__ import annotations

from typing import Any, Mapping

import abc

from bag.layout.tech import TechInfo

from ..array.tech import ArrayTech


class ResTech(ArrayTech, abc.ABC):
    def __init__(self, tech_info: TechInfo, metal: bool = False) -> None:
        ArrayTech.__init__(self, tech_info, 'res', metal=metal)
        self._res_config = tech_info.config['res_metal' if metal else 'res']

    @property
    def res_config(self) -> Mapping[str, Any]:
        return self._res_config

    @property
    def conn_layer(self) -> int:
        return self._res_config['conn_layer']

    @property
    def mos_type_default(self) -> str:
        return self._res_config['mos_type_default']

    @property
    def threshold_default(self) -> str:
        return self._res_config['threshold_default']

    @property
    def has_substrate_port(self) -> bool:
        return self._res_config['has_substrate_port']
