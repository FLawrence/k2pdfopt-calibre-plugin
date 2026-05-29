#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2024, by Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

import copy

from calibre import prints
from calibre.utils.config import JSONConfig


try:
    load_translations()
except NameError:
    prints("k2pdfopt_plugin::config.py - exception when loading translations")

KEY_K2PDFOPT_PATH = 'k2pdfoptPath'
KEY_POST_CONVERT_ACT = 'postConvertAct'
KEY_PRESETS = 'presets'
KEY_LAST_USED_SETTINGS = 'lastUsedSettings'
#KEY_LAST_USED_PRESET = 'lastUsedPreset'

DEFAULT_VALUES = {
    KEY_K2PDFOPT_PATH: '',
    KEY_POST_CONVERT_ACT: 'addFormat',
    KEY_LAST_USED_SETTINGS: {},
#    KEY_LAST_USED_PRESET: '',
    KEY_PRESETS: {}
}

KEY_SCHEMA_VERSION = 'schemaVersion'
DEFAULT_SCHEMA_VERSION = 1.0

PLUGIN_ICONS = [
    'images/plugin.png',
    'images/arrow_left_double.png',
    'images/arrow_left_single.png',
    'images/arrow_right_double.png',
    'images/arrow_right_single.png',
    'images/fitimage.png',
    'images/actual_size.png'
]

# This is where all preferences for this plugin will be stored
plugin_prefs = JSONConfig('plugins/K2pdfopt Plugin')

# Set defaults
#plugin_prefs.defaults = DEFAULT_VALUES

def get_missing_values_from_defaults(default_settings, settings):
    '''add keys present in default_settings and absent in setting'''
    for k, default_value in default_settings.items():
        try:
            setting_value = settings[k]
            if isinstance(default_value, dict):
                get_missing_values_from_defaults(default_value, setting_value)
        except KeyError:
            settings[k] = copy.deepcopy(default_value)

def migrate_plugin_prefs_if_required(plugin_prefs, commit=True):
    schema_version = plugin_prefs.get(KEY_SCHEMA_VERSION, 0)
    if schema_version == DEFAULT_SCHEMA_VERSION:
        return

    # We have changes to be made - mark schema as updated
    plugin_prefs[KEY_SCHEMA_VERSION] = DEFAULT_SCHEMA_VERSION

    # Any migration code in future will exist in here.
    if schema_version < 1.1:
        pass

    # Update: add defaults for new keys {
    get_missing_values_from_defaults(DEFAULT_VALUES, plugin_prefs)
    if commit:
        plugin_prefs.commit()

get_missing_values_from_defaults(DEFAULT_VALUES, plugin_prefs)
migrate_plugin_prefs_if_required(plugin_prefs)

MANDATORY_OPTS = ['-y', '-a-', '-ui-', '-gui-', '-x']


UNIT_MAP = {
    'in': 'Inches',
    'cm': 'Centimeters',
    's': 'Source Page Size',
    't': 'Trimmed Source Region Size',
    'p': 'Pixels',
    'x': 'Relative to the OCR Text Layer',
}

DEVICE_NAME_MAP = {
    'k2': 'Kindle 1-5',
    'dx': 'Kindle DX',
    'kpw': 'Kindle Paperwhite',
    'kp2': 'Kindle Paperwhite 2',
    'kp3': 'Kindle Paperwhite 3',
    'kv': 'Kindle Voyage/PW3+/Oasis',
    'ko2': 'Kindle Oasis 2',
    'pb2': 'Pocketbook Basic 2',
    'nookst': 'Nook Simple Touch',
    'kbt': 'Kobo Touch',
    'kbg': 'Kobo Glo',
    'kghd': 'Kobo Glo HD',
    'kghdfs': 'Kobo Glo HD Full Screen',
    'kbm': 'Kobo Mini',
    'kba': 'Kobo Aura',
    'kbhd': 'Kobo Aura HD',
    'kbh2o': 'Kobo H2O',
    'kbh2ofs': 'Kobo H2O Full Screen',
    'kao': 'Kobo Aura One',
    'koc': 'Kobo Clara HD',
    'kof': 'Kobo Forma',
    'kol': 'Kobo Libra H2O',
    'kolc': 'Kobo Libre Colour',
    'nex7': 'Nexus 7',
    None: 'Other (specify width & height)'
}

DEVICE_WIDTH_MAP = {
    'k2': 560,
    'dx': 800,
    'kpw': 658,
    'kp2': 718,
    'kp3': 1016,
    'kv': 1016,
    'ko2': 1200,
    'pb2': 600,
    'nookst': 552,
    'kbt': 600,
    'kbg': 758,
    'kghd': 1072,
    'kghdfs': 1072,
    'kbm': 600,
    'kba': 758,
    'kbhd': 1080,
    'kbh2o': 1080,
    'kbh2ofs': 1080,
    'kao': 1404,
    'koc': 1072,
    'kof': 1440,
    'kol': 1264,
    'kolc': 1264,
    'nex7': 1187
}

DEVICE_HEIGHT_MAP = {
    'k2': 735,
    'dx': 1180,
    'kpw': 889,
    'kp2': 965,
    'kp3': 1364,
    'kv': 1364,
    'ko2': 1583,
    'pb2': 800,
    'nookst': 725,
    'kbt': 730,
    'kbg': 942,
    'kghd': 1328,
    'kghdfs': 1448,
    'kbm': 730,
    'kba': 932,
    'kbhd': 1320,
    'kbh2o': 1309,
    'kbh2ofs': 1429,
    'kao': 1713,
    'koc': 1317,
    'kof': 1745,
    'kol': 1527,
    'kolc': 1680,
    'nex7': 1811
}

DEVICE_DPI_MAP = {
    'k2': 167,
    'dx': 167,
    'kpw': 212,
    'kp2': 212,
    'kp3': 300,
    'kv': 300,
    'ko2': 300,
    'pb2': 167,
    'nookst': 167,
    'kbt': 167,
    'kbg': 213,
    'kghd': 250,
    'kghdfs': 250,
    'kbm': 200,
    'kba': 211,
    'kbhd': 250,
    'kbh2o': 265,
    'kbh2ofs': 265,
    'kao': 300,
    'koc': 300,
    'kof': 300,
    'kol': 300,
    'kolc': 300,
    'nex7': 323
}

MODE_MAP = {
    'def': 'Default (Kobo Libre Colour)',
    'def_k2': 'Default (Kindle 1-5)',
    'copy': 'Copy',
    'fp': 'Fit Page',
    'fw': 'Fit Width',
    '2col': '2 Columns',
    'tm': 'Trim Margins',
    'crop': 'Crop (Kobo Libre Colour)',
    'crop_k2': 'Crop (Kindle 1-5)',
    'concat': 'Concat',
}

CONVERSION_DEFAULTS = {
    'device': 'kolc',
    'width': [1264, 'p'],
    'height': [1680, 'p'],
    'dpi': 300,
    'margins': [0.0,0.0,0.0,0.0],
    'max_cols': 2,
    'drf': 0.0,
    'fixed_font_size': 0.0,
    'pages': '',
    'cmdopts': '',
    'conversion_mode': 'def',
    'cover_image': 0,
    'fastpreview': True,
    'autostraighten': False,
    'break_after': False,
    'color': True,
    'landscape': False,
    'native': False,
    'rtl': False,
    'marked': True,
    'reflow': True,
    'erase_vl': False,
    'erase_hl': False,
    'ocr': False,
    'autocrop': False
}

OPT_NAME_MAP = {
    'device': '-dev',
    'width': '-w',
    'height': '-h',
    'dpi': '-dpi',
    'margins': '-m',
    'max_cols': '-col',
    'drf': '-dr',
    'pages': '-p',
    'cover_image': '-ci',
    'conversion_mode': '-mode',
    'autostraighten': '-as',
    'break_after': '-pb',
    'color': '-c',
    'landscape': '-ls',
    'native': '-n',
    'rtl': '-r',
    'marked': '-sm',
    'reflow': '-wrap',
    'erase_vl': '-evl',
    'erase_hl': '-ehl',
    'fastpreview': '-rt',
    'ocr': '-ocr',
    'autocrop': '-ac',
    'fixed_font_size': '-fs'
}

MODE_SETTINGS_MAP = {
    'def': {
        'device': 'kolc',
        'width': [1264, 'p'],
        'height': [1680, 'p'],
        'dpi': 300,
        'margins': [0.0,0.0,0.0,0.0],
        'max_cols': 2,
        'color': True,
        'landscape': False,
        'native': False,
        'reflow': True
    },
    'def_k2': {
        'device': 'k2',
        'width': [560, 'p'],
        'height': [735, 'p'],
        'dpi': 167,
        'margins': [0.0,0.0,0.0,0.0],
        'max_cols': 2,
        'color': False,
        'landscape': False,
        'native': False,
        'reflow': True
    },
    'copy': {
        'device': None,
        'width': [1, 's'],
        'height': [1, 's'],
        'dpi': 150,
        'margins': [0.0,0.0,0.0,0.0],
        'max_cols': 1,
        'color': True,
        'native': False,
        'reflow': False
    },
    'fp': {
        'max_cols': 1,
        'native': True,
        'reflow': False
    },
    'fw': {
        'max_cols': 1,
        'landscape': True,
        'native': True,
        'reflow': False
    },
    '2col': {
        'max_cols': 2,
        'native': True,
        'reflow': False
    },
    'tm': {
        'device': None,
        'width': [1, 't'],
        'height': [1, 't'],
        'dpi': 167,
        'margins': [0.0,0.0,0.0,0.0],
        'max_cols': 1,
        'color': True,
        'native': True,
        'reflow': False
    },
    'crop': {
        'device': 'kolc',
        'width': [1264, 'p'],
        'height': [1680, 'p'],
        'dpi': 300,
        'margins': [0.0,0.0,0.0,0.0],
        'max_cols': 1,
        'color': True,
        'landscape': False,
        'native': False,
        'reflow': True
    },    
    'crop_k2': {
        'device': 'k2',
        'width': [560, 'p'],
        'height': [735, 'p'],
        'dpi': 167,
        'margins': [0.0,0.0,0.0,0.0],
        'max_cols': 1,
        'color': False,
        'landscape': False,
        'native': False,
        'reflow': False
    },
    'concat': {
        'device': None,
        'width': [1, 's'],
        'height': [1, 's'],
        'max_cols': 1,
        'native': True,
        'reflow': False
    }
}
