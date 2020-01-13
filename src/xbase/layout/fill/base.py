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

from __future__ import annotations

from typing import Any, Dict, Tuple


from pybag.core import BBox

from bag.util.immutable import Param
from bag.layout.template import TemplateBase, TemplateDB

from ..data import draw_layout_in_template

from .tech import FillTech


class DeviceFill(TemplateBase):
    """A template that fills an area with active devices.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_min_fill_dim(cls, tech_info, mos_type, threshold):
        tech_cls = tech_info.tech_params['layout']['mos_tech_class']
        return tech_cls.get_min_fill_dim(mos_type, threshold)

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            width='The width of the fill area, in resolution units.',
            height='The height of the fill area, in resolution units.',
            edges='The left/bottom/right/top edge parameters.',
            mos_type='transistor type.',
            threshold='transistor threshold.',
        )

    @classmethod
    def get_default_param_values(cls) -> Dict[str, Any]:
        return dict(
            mos_type='',
            threshold='',
        )

    def draw_layout(self):
        w: int = self.params['width']
        h: int = self.params['height']
        edges: Tuple[Param, Param, Param, Param] = self.params['edges']
        mos_type: str = self.params['mos_type']
        threshold: str = self.params['threshold']

        # draw fill
        grid = self.grid
        tech_cls: FillTech = grid.tech_info.get_device_tech('fill')

        # set size
        box = BBox(0, 0, w, h)
        self.prim_top_layer = grid.bot_layer
        self.array_box = self.prim_bound_box = box

        mos_type = mos_type or tech_cls.mos_type_default
        threshold = threshold or tech_cls.threshold_default
        info = tech_cls.get_fill_info(mos_type, threshold, w, h, edges[0], edges[1],
                                      edges[2], edges[3])
        draw_layout_in_template(self, info)
