#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2024, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

from functools import partial

try:
    from qt.core import QApplication, Qt, QToolButton, QMenu
except ImportError:
    from PyQt5.Qt import QApplication, Qt, QToolButton, QMenu

from calibre import prints
from calibre.constants import DEBUG
from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.date import now

import calibre_plugins.k2pdfopt_plugin.config as cfg
from calibre_plugins.k2pdfopt_plugin.common_utils import (
    set_plugin_icon_resources, get_icon, create_menu_action_unique,
)
from calibre_plugins.k2pdfopt_plugin.gui.main import MainDialog, K2pdfoptPathDialog
from calibre_plugins.k2pdfopt_plugin.gui.progress import (
    PreProcessProgressDialog)
from calibre_plugins.k2pdfopt_plugin.pdf import (
    get_k2pdfopt_path, validate_k2pdfopt_path)

try:
    load_translations()
except NameError:
    prints("k2pdfopt_plugin::action.py - exception when loading translations")

class K2pdfoptAction(InterfaceAction):

    name = 'K2pdfopt Plugin'
    action_spec = (_('K2pdfopt Plugin'), None, _('Convert PDFs using k2pdfopt'), ())
    popup_type = QToolButton.MenuButtonPopup
    action_type = 'current'
    dont_add_to = frozenset(['context-menu-device'])

    def genesis(self):
        # Read the plugin icons and store for potential sharing with the config widget
        self.icon_resources = self.load_resources(cfg.PLUGIN_ICONS)
        set_plugin_icon_resources(self.name, self.icon_resources)

        # Assign our menu to this action and an icon
        self.qaction.setIcon(get_icon(cfg.PLUGIN_ICONS[0]))
        self.qaction.triggered.connect(self.show_main_dialog)

        self.menu = QMenu(self.gui)
        self.qaction.setMenu(self.menu)

        create_menu_action_unique(self, self.menu, _('Convert books')+'...', cfg.PLUGIN_ICONS[0],
                                  shortcut=False, triggered=self.show_main_dialog)

        create_menu_action_unique(self, self.menu, _('&Customize plugin')+'...', 'config.png',
                                  shortcut=False, triggered=self.show_configuration)
        self.gui.keyboard.finalize()

    def show_configuration(self):
        self.interface_action_base_plugin.do_user_config(self.gui)

    def show_main_dialog(self):
        res = get_k2pdfopt_path()
        if res is False:
            d = K2pdfoptPathDialog(self.gui, path=cfg.plugin_prefs[cfg.KEY_K2PDFOPT_PATH])
            if d.exec_() == d.Accepted:
                if validate_k2pdfopt_path(d.path):
                    cfg.plugin_prefs[cfg.KEY_K2PDFOPT_PATH] = d.path
                    cfg.plugin_prefs.commit()
                else:
                    return error_dialog(
                        self.gui,
                        _('Path not found'),
                        _('Unable to run k2pdfopt from specified location. '
                          'Make sure you enter the right path and that '
                          'the file has execution permissions'),
                        show=True
                    )
            else:
                return
        d = MainDialog()
        if d.exec_() == d.Accepted:
            self.reflow_books(d.conversion_settings, input_format=d.input_format, output_format='PDF')

    def reflow_books(self, conversion_settings, input_format, output_format):
        self.start_time = now()
        tdir = PersistentTemporaryDirectory('_k2pdfopt')
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, _('No rows selected'),
                                _('You must select one or more books to perform this action.'), show=True)
        book_ids = self.gui.library_view.get_selected_ids()
        db = self.gui.library_view.model().db

        PreProcessProgressDialog(self.gui, conversion_settings, book_ids, tdir, input_format, output_format)
