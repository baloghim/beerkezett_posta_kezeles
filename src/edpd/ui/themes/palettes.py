"""Small colour tables; Longhorn shares QSS, Luna has its own control surfaces."""
from ...surface_styles import LUNA
PALETTES = {
    'Longhorn Blue': dict(window='#e8f1fe', top='#f9fcff', middle='#dcecff', bottom='#bed5f4',
        edge='#789dcc', shine='#ffffff', title_top='#94c6f9', title_mid='#467fca',
        title_bottom='#2c5c9d', title_edge='#416d9f', title_text='#ffffff',
        text='#172b43', alternate='#f0f6ff', selection='#beddf7', selection_edge='#568cc7',
        hover_top='#ffffff', hover_bottom='#b3d7fb', pressed='#8dbbe9', disabled='#718096',
        viewport='#6b7789', field='#ffffff'),
    'Longhorn Slate': dict(window='#e3e9f0', top='#f5f8fc', middle='#d7e0eb', bottom='#b7c4d7',
        edge='#7b8da6', shine='#ffffff', title_top='#8e9fb7', title_mid='#546b89',
        title_bottom='#354b67', title_edge='#40526c', title_text='#ffffff',
        text='#202c3d', alternate='#edf1f7', selection='#c7d5e8', selection_edge='#627fa4',
        hover_top='#f8fbff', hover_bottom='#bdcde1', pressed='#9caec7', disabled='#717d8d',
        viewport='#606a79', field='#ffffff'),
    LUNA: dict(window='#ece9d8', top='#fffef7', middle='#f4f1e2', bottom='#e2dfce',
        edge='#7f9db9', shine='#ffffff', title_top='#5d9bff', title_mid='#1259e4',
        title_bottom='#003bb4', title_edge='#003caa', title_text='#ffffff',
        text='#111111', alternate='#f3f7ff', selection='#316ac5', selection_edge='#003c74',
        hover_top='#fff8df', hover_bottom='#ffd27d', pressed='#c9d8ed', disabled='#77776c',
        viewport='#808c9f', field='#ffffff'),
}

REQUIRED_KEYS = frozenset(next(iter(PALETTES.values())))
