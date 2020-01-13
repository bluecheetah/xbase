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

from bag.design.module import Module
from bag.design.database import ModuleDB
from bag.util.immutable import Param


# noinspection PyPep8Naming
class xbase__metal_short(Module):
    """Module for library xbase cell metal_short.

    Fill in high level description here.
    """

    yaml_file = pkg_resources.resource_filename(__name__,
                                                str(Path('netlist_info',
                                                         'metal_short.yaml')))

    def __init__(self, database: ModuleDB, params: Param, **kwargs: Any) -> None:
        Module.__init__(self, self.yaml_file, database, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            w='resistor width, in resolution units.',
            l='resistor length, in resolution units.',
            layer='the metal layer ID.',
            npar='number of metal resistors in parallel.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(
            npar=1,
        )

    def get_master_basename(self) -> str:
        return f'{self.orig_cell_name}_m{self.params["layer"]}'

    def design(self, w: int, l: int, layer: int, npar: int) -> None:
        if npar < 0:
            raise ValueError('Cannot have non-positive number of parallel metal resistors.')

        self.instances['XRM'].design(w=w, l=l, layer=layer)

        if npar > 1:
            self.rename_instance('XRM', f'XRM<{npar-1}:0>')
