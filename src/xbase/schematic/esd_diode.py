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
class xbase__esd_diode(Module):
    """Module for library xbase cell esd_diode.

    Fill in high level description here.
    """

    yaml_file = pkg_resources.resource_filename(__name__,
                                                str(Path('netlist_info',
                                                         'esd_diode.yaml')))

    def __init__(self, database: ModuleDB, params: Param, **kwargs: Any) -> None:
        Module.__init__(self, self.yaml_file, database, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            w='diode width, in resolution units or number of fins.',
            l='diode length, in resolution units or number of fingers.',
            intent='diode flavor.',
            dio_type='diode type, either "ndio" or "pdio".',
            num='total number of diodes.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(
            dio_type='ndio',
            num=1,
        )

    def get_master_basename(self) -> str:
        return f'{self.orig_cell_name}_{self.params["dio_type"]}'

    def design(self, w: int, l: int, intent: str, dio_type: str, num: int) -> None:
        if num < 0:
            raise ValueError('Cannot have non-positive number of diodes.')

        if dio_type == 'pdio':
            self.replace_instance_master('XD', 'BAG_prim', 'pdio_standard',
                                         keep_connections=True)
        elif dio_type != 'ndio':
            raise ValueError(f'Invalid diode name: {dio_type}')

        self.instances['XD'].design(w=w, l=l, intent=intent)

        if num > 1:
            self.rename_instance('XD', f'XD<{num-1}:0>')
