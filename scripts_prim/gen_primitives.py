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

from typing import List, Tuple, Dict, cast, Type

import sys
import argparse
from pathlib import Path

from pybag.enum import DesignOutput

from bag.core import BagProject
from bag.io import read_yaml
from bag.util.importlib import import_class
from bag.layout.template import TemplateDB, TemplateBase


def _info(etype, value, tb):
    if hasattr(sys, 'ps1') or not sys.stderr.isatty():
        # we are in interactive mode or we don't have a tty-like
        # device, so we call the default hook
        sys.__excepthook__(etype, value, tb)
    else:
        import pdb
        import traceback
        # we are NOT in interactive mode, print the exception...
        traceback.print_exception(etype, value, tb)
        print()
        # ...then start the debugger in post-mortem mode.
        pdb.post_mortem(tb)


sys.excepthook = _info


def get_index() -> int:
    parser = argparse.ArgumentParser(description='Run primitive test scripts.')
    parser.add_argument('index', metavar='N', type=int, default=-1, nargs='?',
                        help='test case index.')

    args = parser.parse_args()
    return args.index


def get_test_dict(specs_root: Path) -> Dict[int, List[Path]]:
    test_dict = {}
    for fpath in specs_root.glob('*.yaml'):
        if fpath.is_file():
            test_num = fpath.name.split('_')[0]
            if len(test_num) == 4 and test_num.isdigit():
                idx = int(test_num[:2])
                flist = test_dict.get(idx, None)
                if flist is None:
                    test_dict[idx] = flist = []
                flist.append(fpath)

    return test_dict


def run_test(db: TemplateDB, lay_list: List[Tuple[TemplateBase, str]],
             fpath_list: List[Path]) -> None:
    for fpath in fpath_list:
        print(f'creating layout from file: {fpath.name}')
        specs = read_yaml(fpath)
        lay_cls = cast(Type[TemplateBase], import_class(specs['lay_class']))
        params = specs['params']
        master = db.new_template(lay_cls, params=params)
        lay_list.append((master, fpath.stem))


def run_main(prj: BagProject, idx: int) -> None:
    lib_name = 'AAA_XBASE_TEST'
    specs_root = Path('specs_test', 'xbase_test')

    db = TemplateDB(prj.grid, lib_name, prj=prj)
    lay_list = []
    test_dict = get_test_dict(specs_root)
    if idx < 0:
        for i in sorted(test_dict.keys()):
            run_test(db, lay_list, test_dict[i])
    else:
        run_test(db, lay_list, test_dict[idx])

    print('batch layout')
    db.batch_layout(lay_list, DesignOutput.LAYOUT)
    print('done')


if __name__ == '__main__':
    idx_ = get_index()

    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()
    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj, idx_)
