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


import argparse
from pathlib import Path

from bag.env import create_routing_grid
from bag.util.misc import register_pdb_hook

from xbase.layout.mos.placement.data import TileInfoTable

register_pdb_hook()


def parse_options() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate cell from spec file.')
    parser.add_argument('root_dir', help='place info YAML specs file root directory.')
    args = parser.parse_args()
    return args


def run_main(args: argparse.Namespace) -> None:
    grid = create_routing_grid()
    root_path = Path(args.root_dir)
    table = TileInfoTable.make_tiles_dir(grid, root_path)
    table.save(root_path)

    print('Finished creating TileInfoTable.')


if __name__ == '__main__':
    _args = parse_options()
    run_main(_args)
