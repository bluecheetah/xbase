from typing import Any, Mapping

from bag.layout.template import TemplateDB, TemplateBase
from bag.util.immutable import Param
from bag.util.math import HalfInt

from pybag.enum import Orient2D
from pybag.core import BBox


class ViaTest(TemplateBase):
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            bot_layer='Bottom metal layer',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(bot_layer=2)

    def get_next_track(self, layer, ntr1, ntr2, cur_idx):
        sep = self.grid.get_sep_tracks(layer, ntr1, ntr2)
        cur_idx = HalfInt.convert(cur_idx)
        return cur_idx + 2 * 2 * sep

    def draw_layout(self) -> None:
        bot_layer = self.params['bot_layer']
        top_layer = bot_layer + 1
        if self.grid.get_direction(bot_layer) is Orient2D.x:
            hlayer = bot_layer
            vlayer = top_layer
        else:
            hlayer = top_layer
            vlayer = bot_layer

        num_w = 20
        for tdx in range(1, num_w + 1):
            bdx = self.grid.get_min_track_width(bot_layer, top_ntr=tdx)
            self.log(f'For top layer track_w = {tdx}, minimum bot layer track_w = {bdx}')
        cur_idx_h, cur_idx_v = 0, 0
        for hdx in range(1, num_w + 1):
            h_min_len = self.grid.get_next_length(hlayer, hdx, 0, even=True)
            v_coord = self.grid.track_to_coord(hlayer, 0)
            h_wire = self.add_wires(hlayer, cur_idx_h, lower=v_coord - h_min_len // 2, upper=v_coord + h_min_len // 2,
                                    width=hdx)
            cur_idx_h = self.get_next_track(hlayer, hdx, hdx + 1, cur_idx_h)
            cur_idx_v = 0
            for vdx in range(1, num_w + 1):
                v_min_len = self.grid.get_next_length(vlayer, vdx, 0, even=True)
                h_coord = self.grid.track_to_coord(hlayer, cur_idx_h)
                v_wire = self.add_wires(vlayer, cur_idx_v, lower=h_coord - v_min_len // 2,
                                        upper=h_coord + v_min_len // 2, width=vdx)
                try:
                    self.connect_to_track_wires(h_wire, v_wire)
                except RuntimeError:
                    self.warn(f'No possible via between hlayer track_w = {hdx} and vlayer track_w = {vdx}')
                cur_idx_v = self.get_next_track(vlayer, vdx, vdx + 1, cur_idx_v)

        w_tot = self.grid.track_to_coord(vlayer, cur_idx_v)
        h_tot = self.grid.track_to_coord(hlayer, cur_idx_h)
        self.set_size_from_bound_box(top_layer, BBox(0, 0, w_tot, h_tot), round_up=True)
