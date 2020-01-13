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

from typing import Any

from dataclasses import dataclass

from bag.util.immutable import ImmutableSortedDict

from ..data import LayoutInfo, WireArrayInfo


@dataclass(eq=True, frozen=True)
class ArrayLayInfo:
    """The transistor block layout information object."""
    lay_info: LayoutInfo
    ports_info: ImmutableSortedDict[str, WireArrayInfo]
    edge_info: ImmutableSortedDict[str, Any]
    end_info: ImmutableSortedDict[str, Any]


@dataclass(eq=True, frozen=True)
class ArrayEndInfo:
    lay_info: LayoutInfo
    edge_info: ImmutableSortedDict[str, Any]
