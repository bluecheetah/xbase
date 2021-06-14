from typing import Optional, Type, Any, Mapping, Tuple, Sequence
from itertools import chain

from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.util import BlackBoxTemplate
from bag.layout.routing.base import WDictType, SpDictType, TrackManager, TrackID
from bag.design.module import Module
from bag.util.immutable import Param

from pybag.core import BBox
from pybag.enum import Orient2D, Direction, RoundMode

from ...schematic.esd_static import xbase__esd_static


class ESDStatic(TemplateBase):
    """This class instantiates a static ESD layout as a BlackBoxTemplate and then brings up pins on routing grid."""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return xbase__esd_static

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            lib_name='The library name.',
            cell_name='The layout cell name.',
            tr_widths='Track widths dictionary',
            tr_spaces='Track spaces dictionary',
        )

    def draw_layout(self) -> None:
        lib_name: str = self.params['lib_name']
        cell_name: str = self.params['cell_name']
        tr_widths: WDictType = self.params['tr_widths']
        tr_spaces: SpDictType = self.params['tr_spaces']
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces)

        # --- Placement --- #
        esd_info = self.grid.tech_info.tech_params['esd']
        top_layer: int = esd_info['top_layer']
        used_port_layer: int = esd_info['used_port_layer']
        assert used_port_layer < top_layer, f'top_layer={top_layer} must be greater than ' \
                                            f'used_port_layer={used_port_layer}'
        config: Mapping[str, Any] = esd_info['types'][cell_name]
        static_lib: str = config['lib_name']
        static_cell: str = config['cell_name']
        size: Tuple[int, int] = config['size']
        ports: Mapping[str, Mapping[str, Sequence[Tuple[int, int, int, int]]]] = config['ports']

        # make master
        master = self.new_template(BlackBoxTemplate, params=dict(lib_name=static_lib, cell_name=static_cell,
                                                                 top_layer=used_port_layer, size=size, ports=ports))

        # add instance
        inst = self.add_instance(master, inst_name='XINST')
        self.set_size_from_bound_box(top_layer, inst.bound_box, round_up=True)

        # --- Routing --- #
        # using hm for lower layer and vm for higher layer just for convenience.
        plus_hm: Sequence[BBox] = inst.get_all_port_pins('plus', used_port_layer)
        minus_hm: Sequence[BBox] = inst.get_all_port_pins('minus', used_port_layer)
        if cell_name == 'esd_vss':
            sup_name = 'VDD'
            plus_idx = 1
            minus_idx = -2
        elif cell_name == 'esd_vdd':
            sup_name = 'VSS'
            plus_idx = -2
            minus_idx = 1
        else:
            raise ValueError(f'Unknown cell_name={cell_name}. Use "esd_vdd" or "esd_vss".')
        sup_hm: Sequence[BBox] = inst.get_all_port_pins(sup_name, used_port_layer)
        hm_lp = self.grid.tech_info.get_lay_purp_list(used_port_layer)[0]

        # put pins on (used_port_layer + 1) on RoutingGrid
        port_layer = used_port_layer + 1
        hm_dir = self.grid.get_direction(used_port_layer)
        if hm_dir is Orient2D.y:
            hm_lower = min([bbox.yl for bbox in chain(plus_hm, minus_hm, sup_hm)])
            hm_upper = max([bbox.yh for bbox in chain(plus_hm, minus_hm, sup_hm)])
        else:  # Orient2D.x
            hm_lower = min([bbox.xl for bbox in chain(plus_hm, minus_hm, sup_hm)])
            hm_upper = max([bbox.xh for bbox in chain(plus_hm, minus_hm, sup_hm)])
        vm_l_idx = self.grid.coord_to_track(port_layer, hm_lower, RoundMode.GREATER_EQ)
        vm_r_idx = self.grid.coord_to_track(port_layer, hm_upper, RoundMode.LESS_EQ)
        vm_num = tr_manager.get_num_wires_between(port_layer, 'sup', vm_l_idx, 'sup', vm_r_idx, 'sup')
        if vm_num < 4:
            raise ValueError(f'Redo routing on port_layer={port_layer}')
        vm_idx_list = tr_manager.spread_wires(port_layer, ['sup', 'sup', 'sup', 'sup'], vm_l_idx, vm_r_idx,
                                              ('sup', 'sup'))
        w_sup_vm = tr_manager.get_width(port_layer, 'sup')

        sup_vm_tid = TrackID(port_layer, vm_idx_list[0], w_sup_vm, num=2, pitch=vm_idx_list[-1] - vm_idx_list[0])
        sup_vm = []
        for idx, bbox in enumerate(sup_hm):
            sup_vm.append(self.connect_bbox_to_tracks(Direction.LOWER, hm_lp, bbox, sup_vm_tid[idx % 2]))

        plus_vm_tid = TrackID(port_layer, vm_idx_list[plus_idx], w_sup_vm)
        plus_vm = []
        for bbox in plus_hm:
            plus_vm.append(self.connect_bbox_to_tracks(Direction.LOWER, hm_lp, bbox, plus_vm_tid))

        minus_vm_tid = TrackID(port_layer, vm_idx_list[minus_idx], w_sup_vm)
        minus_vm = []
        for bbox in minus_hm:
            minus_vm.append(self.connect_bbox_to_tracks(Direction.LOWER, hm_lp, bbox, minus_vm_tid))

        vm_lower = min([warr.lower for warr in chain(sup_vm, plus_vm, minus_vm)])
        vm_upper = max([warr.upper for warr in chain(sup_vm, plus_vm, minus_vm)])
        self.add_pin(sup_name, self.extend_wires(sup_vm, lower=vm_lower, upper=vm_upper))
        self.add_pin('plus', self.extend_wires(plus_vm, lower=vm_lower, upper=vm_upper))
        self.add_pin('minus', self.extend_wires(minus_vm, lower=vm_lower, upper=vm_upper))

        # setup schematic parameters
        self.sch_params = dict(
            lib_name=lib_name,
            cell_name=cell_name,
        )
