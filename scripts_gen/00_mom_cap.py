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

"""This script demonstrates how to add substrate contact in transistor row."""

from pathlib import Path

from pybag.enum import DesignOutput

from bag.core import BagProject
from bag.io import read_yaml
from bag.layout.template import TemplateDB
from bag.design.database import ModuleDB

from xbase.layout.cap.core import MOMCapCore
from xbase.schematic.momcap_core import xbase__momcap_core


def run_main(prj: BagProject, gen_sch: bool = True, gen_cdl: bool = True, run_lvs: bool = True) \
        -> None:
    lib_name = 'AAA_XBASE_TEST'
    fname = '00_mom_cap.yaml'

    impl_cell = 'MOMCap_core'
    fname_cdl = 'pvs_run/lvs_run_dir/' + lib_name + '/' + impl_cell + '/schematic.net'

    params = read_yaml(Path('specs_test', 'xbase', fname))

    db = TemplateDB(prj.grid, lib_name, prj=prj)

    print('creating new template')
    master = db.new_template(MOMCapCore, params)
    print('creating batch layout')
    # db.batch_layout([(master, '')], DesignOutput.LAYOUT)
    db.batch_layout([(master, impl_cell)], DesignOutput.LAYOUT)
    print('done')

    if gen_sch or gen_cdl:
        sch_db = ModuleDB(prj.tech_info, lib_name, prj=prj)

        sch_master = sch_db.new_master(xbase__momcap_core, master.sch_params)
        cv_info_list = []

        print('creating schematic')
        sch_db.batch_schematic([(sch_master, impl_cell)], cv_info_out=cv_info_list)
        print('schematic creation done')

        if gen_cdl:
            print('creating CDL netlist')
            sch_db.batch_schematic([(sch_master, impl_cell)], output=DesignOutput.CDL,
                                   fname=fname_cdl, cv_info_list=cv_info_list)
            print('netlist creation done')

    if run_lvs:
        print('Running LVS ...')
        lvs_passed, lvs_log = prj.run_lvs(lib_name, impl_cell, netlist=fname_cdl)
        print('LVS log file:' + lvs_log)
        if lvs_passed:
            print('LVS passed!')
        else:
            print('LVS failed :(')


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()
    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj, gen_sch=True, gen_cdl=True, run_lvs=True)
