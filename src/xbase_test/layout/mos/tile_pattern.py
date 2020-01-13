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

from typing import Any, Dict

from bag.util.immutable import Param
from bag.layout.template import TemplateDB

from xbase.layout.mos.base import MOSBasePlaceInfo, MOSBase


class TilePatternTest(MOSBase):
    """A MOSBase of only rows of transistors, no connection specs.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            pinfo='the tile specification object.',
            ncol='number of columns.',
            ntile='number of tiles.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(min_ntr=0, w_list=None)

    def draw_layout(self):
        pinfo = MOSBasePlaceInfo.make_place_info(self.grid, self.params['pinfo'])
        self.draw_base(pinfo)

        ncol: int = self.params['ncol']
        ntile: int = self.params['ntile']

        self.set_mos_size(ncol, ntile)

        for tile_idx in range(ntile):
            pinfo = self.get_tile_pinfo(tile_idx)
            for row_idx in range(pinfo.num_rows):
                rinfo = pinfo.get_row_place_info(row_idx).row_info
                if rinfo.row_type.is_substrate:
                    self.add_substrate_contact(row_idx, 0, tile_idx=tile_idx, seg=ncol)
                else:
                    self.add_mos(row_idx, 0, ncol, tile_idx=tile_idx)
