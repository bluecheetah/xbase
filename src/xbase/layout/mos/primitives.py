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

from typing import Dict, Any, Optional, Tuple

from bag.util.immutable import Param, ImmutableList, ImmutableSortedDict
from bag.layout.template import TemplateBase, TemplateDB

from ..enum import MOSPortType, MOSType
from ..data import draw_layout_in_template

from .tech import MOSTech
from .data import MOSEdgeInfo, RowExtInfo, BlkExtInfo, MOSRowInfo


class MOSConn(TemplateBase):
    """Transistor connection primitive.

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self._left_info: Optional[MOSEdgeInfo] = None
        self._right_info: Optional[MOSEdgeInfo] = None
        self._top_info: Optional[BlkExtInfo] = None
        self._bottom_info: Optional[BlkExtInfo] = None
        self._shorted_ports: Optional[ImmutableList[MOSPortType]] = None

    @property
    def left_info(self) -> Optional[MOSEdgeInfo]:
        return self._left_info

    @property
    def right_info(self) -> Optional[MOSEdgeInfo]:
        return self._right_info

    @property
    def top_info(self) -> Optional[BlkExtInfo]:
        return self._top_info

    @property
    def bottom_info(self) -> Optional[BlkExtInfo]:
        return self._bottom_info

    @property
    def shorted_ports(self) -> ImmutableList[MOSPortType]:
        return self._shorted_ports

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            row_info='transistor row information dictionary.',
            conn_layer='connection layer ID.',
            seg='number of segments.',
            w='transistor width, in resolution units or fins.',
            stack='number of transistors in a stack.',
            g_on_s='True if gate is aligned with source.',
            options='Optional process-specific parameters.',
            arr_options='Optional process-specific parameters for the array.',
        )

    def draw_layout(self) -> None:
        row_info: MOSRowInfo = self.params['row_info']
        conn_layer: int = self.params['conn_layer']
        seg: int = self.params['seg']
        w: int = self.params['w']
        stack: int = self.params['stack']
        g_on_s: bool = self.params['g_on_s']
        options: Param = self.params['options']
        arr_options: Param = self.params['arr_options']

        grid = self.grid
        tech_cls: MOSTech = grid.tech_info.get_device_tech('mos', lch=row_info.lch,
                                                           arr_options=arr_options)

        mos_info = tech_cls.get_mos_conn_info(row_info, conn_layer, seg, w, stack, g_on_s, options)
        draw_layout_in_template(self, mos_info.lay_info)

        g_conn_y = row_info.g_conn_y
        if g_on_s:
            if (stack & 1) == 0:
                d_conn_y = row_info.ds_g_conn_y
            else:
                d_conn_y = row_info.ds_conn_y
            s_conn_y = row_info.ds_g_conn_y
        else:
            d_conn_y = row_info.ds_g_conn_y
            s_conn_y = row_info.ds_conn_y

        g_xc, num_g, g_pitch = mos_info.g_info
        d_xc, num_d, d_pitch = mos_info.d_info
        s_xc, num_s, s_pitch = mos_info.s_info

        pitch = grid.get_track_pitch(conn_layer)
        g_tr = grid.coord_to_track(conn_layer, g_xc)
        d_tr = grid.coord_to_track(conn_layer, d_xc)
        s_tr = grid.coord_to_track(conn_layer, s_xc)
        g_tr_p = g_pitch // pitch
        d_tr_p = d_pitch // pitch
        s_tr_p = s_pitch // pitch

        gw = self.add_wires(conn_layer, g_tr, g_conn_y[0], g_conn_y[1], num=num_g, pitch=g_tr_p)
        dw = self.add_wires(conn_layer, d_tr, d_conn_y[0], d_conn_y[1], num=num_d, pitch=d_tr_p)
        sw = self.add_wires(conn_layer, s_tr, s_conn_y[0], s_conn_y[1], num=num_s, pitch=s_tr_p)
        self.add_pin('g', gw)
        self.add_pin('d', dw)
        self.add_pin('s', sw)

        if mos_info.m_info is not None:
            m_xc, num_m, m_pitch = mos_info.m_info
            m_tr = grid.coord_to_track(conn_layer, m_xc)
            m_tr_p = m_pitch // pitch
            m_conn_y = row_info.ds_conn_y
            self.add_pin('m', self.add_wires(conn_layer, m_tr, m_conn_y[0], m_conn_y[1],
                                             num=num_m, pitch=m_tr_p))

        self.prim_top_layer = conn_layer
        self._left_info = mos_info.left_info
        self._right_info = mos_info.right_info
        self._top_info = mos_info.top_info
        self._bottom_info = mos_info.bottom_info
        self._shorted_ports = mos_info.shorted_ports


class MOSTap(TemplateBase):
    """Transistor substrate tap primitive.

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self._left_info: Optional[MOSEdgeInfo] = None
        self._right_info: Optional[MOSEdgeInfo] = None
        self._top_info: Optional[BlkExtInfo] = None
        self._bottom_info: Optional[BlkExtInfo] = None

    @property
    def left_info(self) -> Optional[MOSEdgeInfo]:
        return self._left_info

    @property
    def right_info(self) -> Optional[MOSEdgeInfo]:
        return self._right_info

    @property
    def top_info(self) -> Optional[BlkExtInfo]:
        return self._top_info

    @property
    def bottom_info(self) -> Optional[BlkExtInfo]:
        return self._bottom_info

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            row_info='transistor row information dictionary.',
            conn_layer='connection layer ID.',
            seg='number of segments.',
            options='Optional process-specific parameters.',
            arr_options='Optional process-specific parameters for the array.',
        )

    def draw_layout(self) -> None:
        row_info: MOSRowInfo = self.params['row_info']
        conn_layer: int = self.params['conn_layer']
        seg: int = self.params['seg']
        options: Param = self.params['options']
        arr_options: Param = self.params['arr_options']

        tech_cls: MOSTech = self.grid.tech_info.get_device_tech('mos', lch=row_info.lch,
                                                                arr_options=arr_options)

        mos_info = tech_cls.get_mos_tap_info(row_info, conn_layer, seg, options)
        draw_layout_in_template(self, mos_info.lay_info)

        conn_y = row_info.sub_conn_y
        sup = self.add_wires(conn_layer, -0.5, conn_y[0], conn_y[1], num=seg + 1, pitch=1)
        self.add_pin('sup', sup, show=False)

        self.prim_top_layer = conn_layer
        self._left_info = mos_info.left_info
        self._right_info = mos_info.right_info
        self._top_info = mos_info.top_info
        self._bottom_info = mos_info.bottom_info


class MOSAbut(TemplateBase):
    """An empty space in a transistor row.

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self.prim_top_layer = self.grid.bot_layer

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            row_info='transistor row information dictionary.',
            edgel='edge info of the block to the left.',
            edger='edge info of the block to the right.',
            arr_options='Optional process-specific parameters for the array.',
        )

    def draw_layout(self) -> None:
        row_info: MOSRowInfo = self.params['row_info']
        edgel: MOSEdgeInfo = self.params['edgel']
        edger: MOSEdgeInfo = self.params['edger']
        arr_options: Param = self.params['arr_options']

        tech_cls: MOSTech = self.grid.tech_info.get_device_tech('mos', lch=row_info.lch,
                                                                arr_options=arr_options)

        lay_info = tech_cls.get_mos_abut_info(row_info, edgel, edger)
        draw_layout_in_template(self, lay_info)
        self.disable_cell_boundary()


class MOSSpace(TemplateBase):
    """An empty space in a transistor row.

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self.prim_top_layer = self.grid.bot_layer

        self._left_info: Optional[MOSEdgeInfo] = None
        self._right_info: Optional[MOSEdgeInfo] = None
        self._top_info: Optional[BlkExtInfo] = None
        self._bottom_info: Optional[BlkExtInfo] = None

    @property
    def left_info(self) -> Optional[MOSEdgeInfo]:
        return self._left_info

    @property
    def right_info(self) -> Optional[MOSEdgeInfo]:
        return self._right_info

    @property
    def top_info(self) -> Optional[BlkExtInfo]:
        return self._top_info

    @property
    def bottom_info(self) -> Optional[BlkExtInfo]:
        return self._bottom_info

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            row_info='transistor row information dictionary.',
            num_cols='number of columns.',
            left_info='edge info of the block to the left.',
            right_info='edge info of the block to the right.',
            arr_options='Optional process-specific parameters for the array.',
        )

    def draw_layout(self) -> None:
        row_info: MOSRowInfo = self.params['row_info']
        num_cols: int = self.params['num_cols']
        left_info: MOSEdgeInfo = self.params['left_info']
        right_info: MOSEdgeInfo = self.params['right_info']
        arr_options: Param = self.params['arr_options']

        tech_cls: MOSTech = self.grid.tech_info.get_device_tech('mos', lch=row_info.lch,
                                                                arr_options=arr_options)

        mos_info = tech_cls.get_mos_space_info(row_info, num_cols, left_info, right_info)
        draw_layout_in_template(self, mos_info.lay_info)

        self._left_info = mos_info.left_info
        self._right_info = mos_info.right_info
        self._top_info = mos_info.top_info
        self._bottom_info = mos_info.bottom_info


class MOSExt(TemplateBase):
    """An extension block between transistor rows

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self.prim_top_layer = self.grid.bot_layer
        self._edge_info: Optional[MOSEdgeInfo] = None

    @property
    def edge_info(self) -> Optional[MOSEdgeInfo]:
        return self._edge_info

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            lch='channel length in resolution units.',
            num_cols='number of columns.',
            height='extension height in resolution unit.',
            bot_info='RowExtInfo object of bottom row.',
            top_info='RowExtInfo object of top row.',
            gr_info='Tuple of guard ring edge tap fingers and total guard ring edge fingers.',
            arr_options='Optional process-specific parameters for the array.',
        )

    def draw_layout(self) -> None:
        lch: int = self.params['lch']
        num_cols: int = self.params['num_cols']
        height: int = self.params['height']
        bot_info: RowExtInfo = self.params['bot_info']
        top_info: RowExtInfo = self.params['top_info']
        gr_info: Tuple[int, int] = self.params['gr_info']
        arr_options: Param = self.params['arr_options']

        tech_cls: MOSTech = self.grid.tech_info.get_device_tech('mos', lch=lch,
                                                                arr_options=arr_options)

        ext_info = tech_cls.get_mos_ext_info(num_cols, height, bot_info, top_info, gr_info)
        draw_layout_in_template(self, ext_info.lay_info)

        self._edge_info = ext_info.edge_info


class MOSExtGR(TemplateBase):
    """An extension block between transistor rows

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self.prim_top_layer = self.grid.bot_layer
        self._edge_info: Optional[MOSEdgeInfo] = None

    @property
    def edge_info(self) -> Optional[MOSEdgeInfo]:
        return self._edge_info

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            lch='channel length in resolution units.',
            num_cols='number of columns.',
            edge_cols='number of guard ring edge columns.',
            height='extension height in resolution unit.',
            bot_info='RowExtInfo object of bottom row.',
            top_info='RowExtInfo object of top row.',
            sub_type='guard ring substrate type.',
            einfo='MOSEdgeInfo object of adjacent MOSExt block.',
            arr_options='Optional process-specific parameters for the array.',
        )

    def draw_layout(self) -> None:
        params = self.params
        lch: int = params['lch']
        num_cols: int = params['num_cols']
        edge_cols: int = params['edge_cols']
        height: int = params['height']
        bot_info: RowExtInfo = params['bot_info']
        top_info: RowExtInfo = params['top_info']
        sub_type: MOSType = params['sub_type']
        einfo: MOSEdgeInfo = params['einfo']
        arr_options: Param = params['arr_options']

        tech_cls: MOSTech = self.grid.tech_info.get_device_tech('mos', lch=lch,
                                                                arr_options=arr_options)

        ext_info = tech_cls.get_mos_ext_gr_info(num_cols, edge_cols, height,
                                                bot_info, top_info, sub_type, einfo)
        draw_layout_in_template(self, ext_info.lay_info)

        self._edge_info = ext_info.edge_info


class MOSEnd(TemplateBase):
    """An end row block of transistor array.

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self.prim_top_layer = self.grid.bot_layer
        self._einfo: Optional[MOSEdgeInfo] = None

    @property
    def edge_info(self) -> Optional[MOSEdgeInfo]:
        return self._einfo

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            lch='channel length in resolution units.',
            blk_h='end height in resolution units.',
            num_cols='number of columns.',
            einfo='RowExtInfo object of adjacent row.',
            arr_options='Optional process-specific parameters for the array.',
        )

    def draw_layout(self) -> None:
        params = self.params
        lch: int = params['lch']
        blk_h: int = params['blk_h']
        num_cols: int = params['num_cols']
        einfo: RowExtInfo = params['einfo']
        arr_options: Param = params['arr_options']

        tech_cls: MOSTech = self.grid.tech_info.get_device_tech('mos', lch=lch,
                                                                arr_options=arr_options)

        end_info = tech_cls.get_mos_end_info(blk_h, num_cols, einfo)
        draw_layout_in_template(self, end_info.lay_info)

        self._einfo = end_info.edge_info


class MOSRowEdge(TemplateBase):
    """The edge block of a transistor row.

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self.prim_top_layer = self.grid.bot_layer

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            blk_w='edge width in resolution units.',
            rinfo='MOSRowInfo object of adjacent row.',
            einfo='MOSEdgeInfo object of adjacent MOSConn block.',
            arr_options='Optional process-specific parameters for the array.',
        )

    def draw_layout(self) -> None:
        blk_w: int = self.params['blk_w']
        rinfo: MOSRowInfo = self.params['rinfo']
        einfo: MOSEdgeInfo = self.params['einfo']
        arr_options: Param = self.params['arr_options']

        tech_cls: MOSTech = self.grid.tech_info.get_device_tech('mos', lch=rinfo.lch,
                                                                arr_options=arr_options)

        lay_info = tech_cls.get_mos_row_edge_info(blk_w, rinfo, einfo)
        draw_layout_in_template(self, lay_info)


class MOSExtEdge(TemplateBase):
    """The edge block of the transistor extension region.

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self.prim_top_layer = self.grid.bot_layer

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            lch='channel length in resolution units.',
            blk_w='edge width in resolution units.',
            einfo='MOSEdgeInfo object of adjacent MOSExt or MOSExtGR block.',
            arr_options='Optional process-specific parameters for the array.',
        )

    def draw_layout(self) -> None:
        lch: int = self.params['lch']
        blk_w: int = self.params['blk_w']
        einfo: MOSEdgeInfo = self.params['einfo']
        arr_options: Param = self.params['arr_options']

        tech_cls: MOSTech = self.grid.tech_info.get_device_tech('mos', lch=lch,
                                                                arr_options=arr_options)

        lay_info = tech_cls.get_mos_ext_edge_info(blk_w, einfo)
        draw_layout_in_template(self, lay_info)


class MOSCorner(TemplateBase):
    """The corner block of transistor array.

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    params : Param
        the parameter values.
    kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

        self.prim_top_layer = self.grid.bot_layer
        self._corner: Optional[Tuple[int, int]] = None
        self._edgel = self._edgeb = ImmutableSortedDict()

    @property
    def corner(self) -> Tuple[int, int]:
        return self._corner

    @property
    def left_edge(self) -> Param:
        return self._edgel

    @property
    def bottom_edge(self) -> Param:
        return self._edgeb

    @classmethod
    def get_params_info(cls) -> Dict[str, str]:
        return dict(
            lch='channel length in resolution units.',
            blk_w='edge width in resolution units.',
            blk_h='end height in resolution units.',
            einfo='MOSEdgeInfo object of adjacent MOSEnd block.',
            arr_options='Optional process-specific parameters for the array.',
        )

    def draw_layout(self) -> None:
        lch: int = self.params['lch']
        blk_w: int = self.params['blk_w']
        blk_h: int = self.params['blk_h']
        einfo: MOSEdgeInfo = self.params['einfo']
        arr_options: Param = self.params['arr_options']

        tech_cls: MOSTech = self.grid.tech_info.get_device_tech('mos', lch=lch,
                                                                arr_options=arr_options)

        corner_info = tech_cls.get_mos_corner_info(blk_w, blk_h, einfo)
        draw_layout_in_template(self, corner_info.lay_info)
        self._corner = corner_info.corner
        self._edgel = corner_info.edgel
        self._edgeb = corner_info.edgeb
