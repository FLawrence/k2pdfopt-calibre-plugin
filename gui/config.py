#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2024, by Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

import os

try:
    from qt.core import (
        Qt, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QCheckBox, QSpinBox,
        QPushButton, QGroupBox, QToolButton, QLabel, QUrl, QComboBox, QFrame)
except ImportError:
    from PyQt5.Qt import (
        Qt, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QCheckBox, QSpinBox,
        QPushButton, QGroupBox, QToolButton, QLabel, QUrl, QComboBox, QFrame)


from calibre import prints
from calibre.constants import iswindows
from calibre.gui2 import choose_files, open_url

from calibre_plugins.k2pdfopt_plugin.common_utils import (
    get_icon, DragDropComboBox, KeyboardConfigDialog, prompt_for_restart)
import calibre_plugins.k2pdfopt_plugin.config as cfg

HELP_URL = 'https://www.mobileread.com/forums/showthread.php?p=4394198'

def show_help():
    open_url(QUrl(HELP_URL))

class ConfigWidget(QWidget):

    def __init__(self, plugin_action):
        QWidget.__init__(self)
        self.plugin_action = plugin_action
        self.gui = plugin_action.gui
        self.post_convert_dict = {
            'addFormat': _( 'Add converted format to the same book record'),
            'addBook': _('Add converted format as a new books')
        }
        self._initialise_controls()

    def _initialise_controls(self):
        l = QVBoxLayout(self)
        self.setLayout(l)
        self.binary_box = QGroupBox(_('&Choose binary:'))
        l.addWidget(self.binary_box)
        binary_layout = QVBoxLayout()
        self.binary_box.setLayout(binary_layout)
        self.binary_combo = DragDropComboBox(self, drop_mode='file')
        self.binary_combo.setCurrentText(cfg.plugin_prefs[cfg.KEY_K2PDFOPT_PATH])
        binary_layout.addWidget(self.binary_combo)
        hl1 = QHBoxLayout()
        binary_layout.addLayout(hl1)
        hl1.addWidget(self.binary_combo, 1)
        self.choose_binary_button = QToolButton(self)
        self.choose_binary_button.setToolTip(_('Choose binary'))
        self.choose_binary_button.setIcon(get_icon('document_open.png'))
        self.choose_binary_button.clicked.connect(self._choose_file)
        hl1.addWidget(self.choose_binary_button)

        gl = QGridLayout()
        l.addLayout(gl)

        post_convert_lbl = QLabel(_('Post-convert Action'))
        gl.addWidget(post_convert_lbl, 0, 0, 1, 1)

        post_convert = cfg.plugin_prefs[cfg.KEY_POST_CONVERT_ACT]
        self.post_convert_combo = QComboBox(self)
        self.post_convert_combo.addItems(list(self.post_convert_dict.values()))
        self.post_convert_combo.setCurrentText(self.post_convert_dict[post_convert])
        gl.addWidget(self.post_convert_combo, 0, 1, 1, 1)

        button_layout = QHBoxLayout()
        keyboard_shortcuts_button = QPushButton(' '+_('Keyboard shortcuts')+'... ', self)
        keyboard_shortcuts_button.setToolTip(_('Edit the keyboard shortcuts associated with this plugin'))
        keyboard_shortcuts_button.clicked.connect(self.edit_shortcuts)
        button_layout.addWidget(keyboard_shortcuts_button)

        help_button = QPushButton(' '+_('Help'), self)
        help_button.setIcon(get_icon('help.png'))
        help_button.clicked.connect(show_help)
        button_layout.addWidget(help_button)
        gl.addLayout(button_layout, 1, 0, 1, 2)

        l.addStretch(1)

        self.setMinimumSize(400,200)

    def _choose_file(self):
        files = choose_files(
            None,
            _('Select binary dialog'),
            _('Select a binary'),
            all_files=True,
            select_only_single_file=True)
        if not files:
            return
        binary_path = files[0]
        if iswindows:
            binary_path = os.path.normpath(binary_path)

        self.block_events = True
        existing_index = self.binary_combo.findText(binary_path, Qt.MatchExactly)
        if existing_index >= 0:
            self.binary_combo.setCurrentIndex(existing_index)
        else:
            self.binary_combo.insertItem(0, binary_path)
            self.binary_combo.setCurrentIndex(0)
        self.block_events = False

    def save_settings(self):
        cfg.plugin_prefs[cfg.KEY_K2PDFOPT_PATH] = self.binary_combo.currentText().strip()
        post_convert_text = self.post_convert_combo.currentText().strip()
        cfg.plugin_prefs[cfg.KEY_POST_CONVERT_ACT] = {v:k for k,v in self.post_convert_dict.items()}[post_convert_text]

        cfg.plugin_prefs.commit()

    def edit_shortcuts(self):
        d = KeyboardConfigDialog(self.plugin_action.gui, self.plugin_action.action_spec[0])
        if d.exec_() == d.Accepted:
            self.plugin_action.gui.keyboard.finalize()
