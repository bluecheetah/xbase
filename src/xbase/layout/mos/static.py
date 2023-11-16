from typing import Optional, Type, Any, Mapping, Sequence, Tuple

from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.util import BlackBoxTemplate
from bag.design.module import Module
from bag.util.immutable import Param

from pybag.core import BBox, Transform

from ...schematic.mos_char import xbase__mos_char


class MOSStatic(TemplateBase):
    """This class instantiates a static MOS layout as a BlackBoxTemplate and adds primitive pins"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)
        self._conn_layer = -1

    @property
    def conn_layer(self) -> int:
        return self._conn_layer

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return xbase__mos_char

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            mos_type='transistor type.',
            w='width of the transistor, in resolution units or fins.',
            lch='channel length, in resolution units.',
            seg='number of segments.',
            intent='threshold flavor.',
        )

    def draw_layout(self) -> None:
        mos_type: str = self.params['mos_type']
        w: int = self.params['w']
        lch: int = self.params['lch']
        seg: int = self.params['seg']
        intent: str = self.params['intent']

        mos_info = self.grid.tech_info.tech_params['mos_static']
        pcell_list: Sequence[Mapping[str, Any]] = mos_info['pcell_list']
        for _info in pcell_list:
            if mos_type == _info['mos_type'] and w == _info['w'] and lch == _info['lch'] and seg == _info['nf'] and \
                    intent == _info['intent']:
                pcell_info = _info['inst_info']
                break
        else:
            raise ValueError(f'Requested pcell is not supported yet.')

        # make master
        master = self.new_template(BlackBoxTemplate, params=pcell_info)

        # add instance
        inst = self.add_instance(master, inst_name='XINST')
        bbox = inst.bound_box
        self._conn_layer = top_layer = pcell_info['top_layer']
        self.set_size_from_bound_box(top_layer, bbox, round_up=True)

        # add rectangle arrays, if any
        rect_arr_list: Sequence[Mapping[str, Any]] = mos_info['rect_arr_list']
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

        # pins
        conn_lp = self.grid.tech_info.get_lay_purp_list(top_layer)[0]
        for term in ('b', 'd', 'g', 's'):
            _pins: Sequence[BBox] = inst.get_all_port_pins(term, top_layer)
            if len(_pins) > 1:
                for idx, _bbox in enumerate(_pins):
                    self.add_pin_primitive(f'{term}{idx}', conn_lp[0], _bbox, label=term, connect=True)
            else:
                self.add_pin_primitive(term, conn_lp[0], _pins[0])

        self.sch_params = dict(
            mos_type=mos_type,
            w=w,
            lch=lch,
            seg=seg,
            intent=intent,
        )


class MOSStaticWrapper(TemplateBase):
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self._core: Optional[MOSStatic] = None
        self._xform: Transform = Transform()

    @property
    def core(self) -> MOSStatic:
        return self._core

    @property
    def core_xform(self) -> Transform:
        return self._xform

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            params='parameters for the wrapped class.',
            export_hidden='True to export hidden pins.',
            half_blk_x='Defaults to True.  True to allow half-block width.',
            half_blk_y='Defaults to True.  True to allow half-block height.',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(export_hidden=False, half_blk_x=True, half_blk_y=True)

    def get_schematic_class_inst(self) -> Optional[Type[Module]]:
        return self._core.get_schematic_class_inst()

    def draw_layout(self):
        params = self.params
        dut_params: Param = params['params']
        export_hidden: bool = params['export_hidden']
        half_blk_x: bool = params['half_blk_x']
        half_blk_y: bool = params['half_blk_y']

        master = self.new_template(MOSStatic, params=dut_params)

        self.wrap_mos_static(master, export_hidden, half_blk_x=half_blk_x, half_blk_y=half_blk_y)

    def wrap_mos_static(self, master: MOSStatic, export_hidden: bool, half_blk_x: bool = True,
                        half_blk_y: bool = True) -> None:
        top_layer = master.top_layer
        bbox = master.bound_box
        w_blk, h_blk = self.grid.get_block_size(top_layer, half_blk_x=half_blk_x, half_blk_y=half_blk_y)

        self._core = master
        edge_sep = self.grid.tech_info.tech_params['mos_static']['edge_sep']
        w_tot = bbox.w + 2 * edge_sep['x']
        h_tot = bbox.h + 2 * edge_sep['y']
        assert w_tot % w_blk == 0 and h_tot % h_blk == 0

        self._xform = Transform(edge_sep['x'], edge_sep['y'])
        inst = self.add_instance(master, inst_name='X0', xform=self._xform)
        self.set_size_from_bound_box(top_layer, BBox(0, 0, w_tot, h_tot))

        # re-export pins
        for name in inst.port_names_iter():
            if not master.get_port(name).hidden or export_hidden:
                self.reexport(inst.get_port(name))

        # pass out schematic parameters
        self.sch_params = master.sch_params
