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

import pkg_resources
from pathlib import Path

from pybag.enum import TermType

from bag.design.module import Module
from bag.design.database import ModuleDB
from bag.util.immutable import Param


# noinspection PyPep8Naming
class xbase__nmos4_stack(Module):
    """Module for library xbase cell nmos4_stack.

    Fill in high level description here.
    """

    yaml_file = pkg_resources.resource_filename(__name__,
                                                str(Path('netlist_info',
                                                         'nmos4_stack.yaml')))

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
            export_mid='True to export intermediate node.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(
            stack=2,
            export_mid=False,
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
            mos_type = f'nmos{intent}'
        elif intent.startswith('3_'):
            # Case 2: changing to 3 terminal mos
            mos_type = f'nmos{intent}'
        else:
            # Case 3: default case
            mos_type = f'nmos4_{intent}'

        if stack > 1:
            ans = f'{mos_type}_stack{stack}_w{w}_l{l}_seg{seg}'
        else:
            ans = f'{mos_type}_w{w}_l{l}_seg{seg}'

        return ans

    def design(self, w: int, lch: int, seg: int, intent: str, stack: int, export_mid: bool) -> None:
        if stack < 1:
            raise ValueError(f'stack = {stack} must be >= 1.')

        if stack != 2:
            if stack > 1:
                self.rename_pin('g<1:0>', f'g<{stack - 1}:0>')
                gate = [f'g<{idx}>' for idx in range(stack)]
            else:
                self.rename_pin('g<1:0>', 'g')
                gate = 'g'
        else:
            if export_mid:
                if seg == 1:
                    self.add_pin('m', TermType.inout)
                else:
                    self.add_pin(f'm<{seg-1}:0>', TermType.inout)
            gate = ['g<0>', 'g<1>']

        self.design_transistor('XN', w, lch, seg, intent, g=gate, m='m', stack=stack)

        if intent.startswith('3_'):
            self.remove_pin('b')
