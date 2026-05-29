#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2024, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

import copy

try:
    from qt.core import (
        QApplication, Qt, QWidget, QHBoxLayout, QLabel,
        QToolButton, QComboBox, QInputDialog, QIcon)
except ImportError:
    from PyQt5.Qt import (
        QApplication, Qt, QWidget, QHBoxLayout, QLabel,
        QToolButton, QComboBox, QInputDialog, QIcon)

from calibre.gui2 import error_dialog, question_dialog

import calibre_plugins.k2pdfopt_plugin.config as cfg


PRESETS_DEFAULTS = {'k2pdfopt': cfg.CONVERSION_DEFAULTS}

class PresetsBar(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.presets = cfg.plugin_prefs[cfg.KEY_PRESETS]
        self._init_controls()

    def _init_controls(self):
        l = QHBoxLayout()
        self.setLayout(l)
        presets_label = QLabel(_('Presets:'), self)
        l.addStretch(1)
        l.addWidget(presets_label)
        self.select_preset_combo = QComboBox()
        self.select_preset_combo.addItems([''] + list(self.presets.keys()))
        self.select_preset_combo.setMinimumSize(150, 20)
        self.select_preset_combo.currentTextChanged.connect(self._select_preset_combo_changed)
        l.addWidget(self.select_preset_combo)
        self.add_preset_button = QToolButton(self)
        self.add_preset_button.setToolTip(_('Add preset'))
        self.add_preset_button.setIcon(QIcon(I('plus.png')))
        self.add_preset_button.clicked.connect(self.add_preset)
        l.addWidget(self.add_preset_button)
        self.delete_preset_button = QToolButton(self)
        self.delete_preset_button.setToolTip(_('Delete preset'))
        self.delete_preset_button.setIcon(QIcon(I('minus.png')))
        self.delete_preset_button.clicked.connect(self.delete_preset)
        l.addWidget(self.delete_preset_button)
        self.rename_preset_button = QToolButton(self)
        self.rename_preset_button.setToolTip(_('Rename preset'))
        self.rename_preset_button.setIcon(QIcon(I('edit-undo.png')))
        self.rename_preset_button.clicked.connect(self.rename_preset)
        l.addWidget(self.rename_preset_button)
        l.addStretch(1)

    def _select_preset_combo_changed(self, preset_name):
        if preset_name:
            preset_settings = self.presets.get(preset_name, {})
            # Presets might be old and does not contain some new settings
            # Make sure to fill in the blanks from defaults
            cfg.get_missing_values_from_defaults(PRESETS_DEFAULTS, preset_settings)
            #settings = copy.deepcopy(cfg.CONVERSION_DEFAULTS)
            #settings.update(preset_settings)
            self.parent().load_settings(preset_settings)
            self.current_preset = preset_name

    def add_preset(self):
        # Display a prompt allowing user to specify a new preset
        new_preset_name, ok = QInputDialog.getText(self, _('Add new preset'),
                    _('Enter a unique display name for this preset:'), text=_('Default'))
        if not ok:
            # Operation cancelled
            return
        new_preset_name = new_preset_name.strip()

        # Verify it does not clash with any other presets in the preset
        if new_preset_name in self.presets.keys():
            msg = _('You already have a preset with the name: {}. Do you want to overwrite it?'.format(new_preset_name))
            if not question_dialog(self, _('Are you sure'), msg):
                return

        # As we are about to switch preset, persist the current presets details if any
        self.presets[new_preset_name] = copy.deepcopy(self.parent().save_settings())
        try:
            del self.presets[new_preset_name]['preset_name']
        except:
            pass
        self.persist_preset_config()
        # Now update the presets combobox
        self.populate_select_preset_combo(self.presets, new_preset_name)

    def rename_preset(self):
        current_preset_name = self.select_preset_combo.currentText()
        if not current_preset_name:
            return
        # Display a prompt allowing user to specify a rename preset
        new_preset_name, ok = QInputDialog.getText(self, _('Rename preset'),
                    _('Enter a new display name for this preset:'), text=current_preset_name)
        if not ok:
            # Operation cancelled
            return
        new_preset_name = new_preset_name.strip()

        if new_preset_name == current_preset_name:
            return

        # Verify it does not clash with any other presets in the preset
        if new_preset_name in self.presets.keys():
            msg = _('You already have a preset with the name: {}. Do you want to overwrite it?'.format(new_preset_name))
            if not question_dialog(self, _('Are you sure'), msg):
                return

        # As we are about to rename preset, persist the current presets details if any
        self.presets[new_preset_name] = self.presets[current_preset_name]
        del self.presets[current_preset_name]
        self.persist_preset_config()
        # Now update the presets combobox
        self.populate_select_preset_combo(self.presets, new_preset_name)

    def delete_preset(self):
        current_preset_name = self.select_preset_combo.currentText()
        if not current_preset_name:
            return
        #if len(self.presets) == 1:
            #return error_dialog(self, _('Cannot delete'),
                                #_('You must have at least one preset'),
                                #show=True, show_copy_button=False)
        msg = _("Do you want to delete the preset named '{}'".format(current_preset_name))
        if not question_dialog(self, _('Are you sure'), msg):
            return

        del self.presets[current_preset_name]
        self.persist_preset_config()
        # Now update the presets combobox
        self.populate_select_preset_combo(self.presets, '')

    def populate_select_preset_combo(self, presets, current_preset):
        if not current_preset in presets:
            presets = list(current_preset) + [current_preset]
        self.select_preset_combo.blockSignals(True)
        self.select_preset_combo.clear()
        self.select_preset_combo.addItems(presets)
        self.select_preset_combo.setCurrentText(current_preset)
        self.select_preset_combo.blockSignals(False)
        self.current_preset = current_preset

    @property
    def preset_name(self):
        return self.select_preset_combo.currentText()

    @preset_name.setter
    def preset_name(self, preset_name):
        if not preset_name in self.presets:
            return
        self.select_preset_combo.blockSignals(True)
        self.select_preset_combo.setCurrentText(preset_name)
        self.select_preset_combo.blockSignals(False)
        self.current_preset = preset_name

    def persist_preset_config(self):
        cfg.plugin_prefs.commit()
