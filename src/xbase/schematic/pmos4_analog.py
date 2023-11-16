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

from typing import Dict, Any

import os
import pkg_resources

from bag.design.module import Module
from bag.design.database import ModuleDB
from bag.util.immutable import Param


# noinspection PyPep8Naming
class xbase__pmos4_analog(Module):
    """Module for library xbase cell pmos4_analog.

    Fill in high level description here.
    """

    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'pmos4_analog.yaml'))

    def __init__(self, database: ModuleDB, params: Param, **kwargs: Any) -> None:
        Module.__init__(self, self.yaml_file, database, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            w='width of the transistor, in resolution units or fins.',
            lch='channel length, in resolution units.',
            seg='number of segments.',
            intent='threshold flavor.',
            stack='number of transistors in a stack.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(
            stack=1,
        )

    def get_master_basename(self) -> str:
        w = self.params['w']
        l = self.params['lch']
        seg = self.params['seg']
        intent = self.params['intent']
        stack = self.params['stack']

        # choose 3 terminal mos without extra parameter by encoding it in the intent
        # e.g.: 3_standard
        if intent.startswith('4_'):
            # Case 1: 4 terminal mos
            mos_type = f'pmos{intent}'
        elif intent.startswith('3_'):
            # Case 2: changing to 3 terminal mos
            mos_type = f'pmos{intent}'
        else:
            # Case 3: default case
            mos_type = f'pmos4_{intent}'

        ans = f'{mos_type}_w{w}_l{l}_seg{seg}'
        if stack != 1:
            ans += f'_stack{stack}'
        return ans

    def design(self, w: int, lch: int, seg: int, intent: str, stack: int) -> None:
        self.design_transistor('XP', w, lch, seg, intent, m='mid', stack=stack)

        if intent.startswith('3_'):
            self.remove_pin('b')
