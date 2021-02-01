# BSD 3-Clause License
#
# Copyright (c) 2018, Regents of the University of California
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""This module defines MOM cap on MOSBase with substrate contacts."""

from typing import Any, Dict, Optional, Mapping, List, Tuple, Type

from pybag.core import BBox, BBoxArray

from bag.util.immutable import Param
from bag.design.module import Module
from bag.layout.template import TemplateDB

from ...layout.mos.base import MOSBasePlaceInfo, MOSBase
from ...schematic.momcap_char import xbase__momcap_char
from .mos import MOMCapOnMOS


class MOMCapChar(MOSBase):
    """MOMCap core on MOSBase with substrate contacts
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        MOSBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return xbase__momcap_char

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            pinfo='The MOSBasePlaceInfo object.',
            cap_params='Parameters for MOMCap',
        )

    def draw_layout(self) -> None:
        pinfo = MOSBasePlaceInfo.make_place_info(self.grid, self.params['pinfo'])
        self.draw_base(pinfo)

        # draw cap
        cap_params: Param = self.params['cap_params']
        cap_tile = 1
        cap_pinfo = self.get_tile_info(cap_tile)
        cap_params = cap_params.copy(append=dict(pinfo=cap_pinfo))
        cap_master: MOMCapOnMOS = self.new_template(MOMCapOnMOS, params=cap_params)

        cap = self.add_tile(cap_master, cap_tile, 0)
        for pin_name in ('plus', 'minus'):
            self.reexport(cap.get_port(pin_name))

        # draw substrate contacts
        num_cols = cap_master.num_cols
        vss0 = self.add_substrate_contact(0, 0, tile_idx=0, seg=num_cols)
        vss1 = self.add_substrate_contact(0, 0, tile_idx=2, seg=num_cols)
        self.add_pin('VSS', [vss0, vss1], connect=True)

        self.set_mos_size()
        self.sch_params = cap_master.sch_params
