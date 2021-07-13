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
        self._conn_layer = -1
        self._tr_manager = None

    @property
    def conn_layer(self) -> int:
        return self._conn_layer

    @property
    def tr_manager(self) -> TrackManager:
        return self._tr_manager

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
        self._tr_manager = tr_manager = TrackManager(self.grid, tr_widths, tr_spaces)

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
        bbox = inst.bound_box
        self.set_size_from_bound_box(top_layer, bbox, round_up=True)

        # add rectangle arrays, if any
        rect_arr_list: Sequence[Mapping[str, Any]] = esd_info['rect_arr_list']
        for rect_arr in rect_arr_list:
            edge_margin: Mapping[str, int] = rect_arr.get('edge_margin', {})
            rect_xl = bbox.xl + edge_margin.get('xl', 0)
            rect_xh = bbox.xh + edge_margin.get('xh', 0)
            rect_yl = bbox.yl + edge_margin.get('yl', 0)
            rect_yh = bbox.yh + edge_margin.get('yh', 0)
            spx: int = rect_arr.get('spx', 0)
            if spx == 0:
                num_x = 1
            else:
                w_unit: int = rect_arr['w_unit']
                num_x = (rect_xh - rect_xl - w_unit) // spx + 1
                rect_xh = rect_xl + w_unit
            spy: int = rect_arr.get('spy', 0)
            if spy == 0:
                num_y = 1
            else:
                h_unit: int = rect_arr['h_unit']
                num_y = (rect_yh - rect_yl - h_unit) // spy + 1
                rect_yh = rect_yl + h_unit
            lp: Tuple[str, str] = rect_arr['lay_purp']
            self.add_rect_array(lp, BBox(rect_xl, rect_yl, rect_xh, rect_yh), num_x, num_y, spx, spy)

        # --- Routing --- #
        # using hm for lower layer and vm for higher layer just for convenience.
        plus_hm: Sequence[BBox] = inst.get_all_port_pins('plus', used_port_layer)
        minus_hm: Sequence[BBox] = inst.get_all_port_pins('minus', used_port_layer)
        if cell_name == 'esd_vss':
            sup_name = 'VDD'
            sup_idx = 0
            minus_idx = 1
            plus_idx = 2
        elif cell_name == 'esd_vdd':
            sup_name = 'VSS'
            sup_idx = 2
            minus_idx = 0
            plus_idx = 1
        else:
            raise ValueError(f'Unknown cell_name={cell_name}. Use "esd_vdd" or "esd_vss".')
        sup_hm: Sequence[BBox] = inst.get_all_port_pins(sup_name, used_port_layer)
        hm_lp = self.grid.tech_info.get_lay_purp_list(used_port_layer)[0]

        # put pins on (used_port_layer + 1) on RoutingGrid
        self._conn_layer = port_layer = used_port_layer + 1
        hm_dir = self.grid.get_direction(used_port_layer)
        if hm_dir is Orient2D.y:
            hm_lower = max([bbox.yl for bbox in chain(plus_hm, minus_hm, sup_hm)])
            hm_upper = min([bbox.yh for bbox in chain(plus_hm, minus_hm, sup_hm)])
        else:  # Orient2D.x
            hm_lower = max([bbox.xl for bbox in chain(plus_hm, minus_hm, sup_hm)])
            hm_upper = min([bbox.xh for bbox in chain(plus_hm, minus_hm, sup_hm)])
        vm_l_idx = self.grid.coord_to_track(port_layer, hm_lower, RoundMode.GREATER_EQ)
        vm_r_idx = self.grid.coord_to_track(port_layer, hm_upper, RoundMode.LESS_EQ)
        vm_num = tr_manager.get_num_wires_between(port_layer, 'sup', vm_l_idx, 'sup', vm_r_idx, 'sup')
        if vm_num < 1:
            raise ValueError(f'Redo routing on port_layer={port_layer}')
        vm_idx_list = tr_manager.spread_wires(port_layer, ['sup', 'sup', 'sup'], vm_l_idx, vm_r_idx,
                                              ('sup', 'sup'))
        w_sup_vm = tr_manager.get_width(port_layer, 'sup')

        sup_vm_tid = TrackID(port_layer, vm_idx_list[sup_idx], w_sup_vm)
        sup_vm = []
        for idx, bbox in enumerate(sup_hm):
            sup_vm.append(self.connect_bbox_to_tracks(Direction.LOWER, hm_lp, bbox, sup_vm_tid))

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

        # add hidden pins on unconnected used_port_layer wires for collision checking in top level cells
        nc_hm: Sequence[BBox] = inst.get_all_port_pins('NC', used_port_layer)
        for bbox in nc_hm:
            self.add_rect(hm_lp, bbox)
            self.add_pin_primitive('NC', f'{used_port_layer}', bbox, hide=True)

        # setup schematic parameters
        self.sch_params = dict(
            lib_name=lib_name,
            cell_name=cell_name,
        )
