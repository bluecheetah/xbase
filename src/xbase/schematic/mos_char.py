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

from typing import Dict, Any, List, Tuple, Optional

import os
import pkg_resources

from bag.design.module import Module
from bag.design.database import ModuleDB
from bag.util.immutable import Param


# noinspection PyPep8Naming
class xbase__mos_char(Module):
    """Module for library xbase cell mos_char.

    Fill in high level description here.
    """

    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'mos_char.yaml'))

    def __init__(self, database: ModuleDB, params: Param, **kwargs: Any) -> None:
        Module.__init__(self, self.yaml_file, database, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            mos_type='transistor type.',
            w='width of the transistor, in resolution units or fins.',
            lch='channel length, in resolution units.',
            seg='number of segments.',
            intent='threshold flavor.',
            stack='number of transistors in a stack.',
            dum_info='Dummy transistor information.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(
            stack=1,
            dum_info=None,
        )

    def get_master_basename(self) -> str:
        w = self.params['w']
        lch = self.params['lch']
        seg = self.params['seg']
        intent = self.params['intent']
        stack = self.params['stack']
        ans = f'mos_char_{intent}_w{w}_l{lch}_seg{seg}'
        if stack != 1:
            ans += f'_stack{stack}'
        return ans

    def design(self, mos_type: str, w: int, lch: int, seg: int, intent: str, stack: int,
               dum_info: Optional[List[Tuple[Any]]]) -> None:
        self.design_transistor('XM', w, lch, seg, intent, m='mid', stack=stack, mos_type=mos_type)
        if dum_info:
            self.design_dummy_transistors(dum_info, 'XD', 'b', 'b')
        else:
            self.remove_instance('XD')
