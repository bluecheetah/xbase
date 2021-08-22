from typing import Any, Mapping

from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.util import BlackBoxTemplate
from bag.util.immutable import Param
from bag.io import read_yaml


class BlackBoxTest(TemplateBase):
    """This class instantiates a custom cell as a BlackBoxTemplate."""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            params_file='The black box specifications file.',
        )

    def draw_layout(self) -> None:
        bb_params = read_yaml(self.params['params_file'])

        # make master
        master = self.new_template(BlackBoxTemplate, params=bb_params)

        # add instance
        inst = self.add_instance(master, inst_name='XINST')
        bbox = inst.bound_box
        top_layer = bb_params['top_layer']
        self.set_size_from_bound_box(top_layer, bbox, round_up=True)
