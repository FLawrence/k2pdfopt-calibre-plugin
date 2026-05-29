#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2024, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

import os
import copy
import traceback
import shutil
from threading import Thread

from six.moves import range

try:
    from qt.core import (
        QApplication, Qt, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QGroupBox, QRadioButton, QLineEdit, QCheckBox, QSpinBox,
        QDoubleSpinBox, QListWidgetItem, QListWidget, QAbstractItemView,
        QPushButton, QToolButton, QComboBox, QTextEdit, QScrollArea,
        QSizePolicy, QIcon, QObject, pyqtSignal)
    QSizePolicyIgnored = QSizePolicy.Policy.Ignored
except ImportError:
    from PyQt5.Qt import (
        QApplication, Qt, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QGroupBox, QRadioButton, QLineEdit, QCheckBox, QSpinBox,
        QDoubleSpinBox, QListWidgetItem, QListWidget, QAbstractItemView,
        QPushButton, QToolButton, QComboBox, QTextEdit, QScrollArea,
        QSizePolicy, QIcon, QObject, pyqtSignal)
    QSizePolicyIgnored = QSizePolicy.Ignored

from calibre import prints
from calibre.constants import DEBUG, iswindows
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.gui2 import (
    error_dialog, warning_dialog, choose_dir, choose_files, open_local_file)
from calibre.gui2.widgets2 import Dialog
from calibre.gui2.ui import get_gui
from calibre.ptempfile import PersistentTemporaryDirectory

import calibre_plugins.k2pdfopt_plugin.gui.tooltips as tt
import calibre_plugins.k2pdfopt_plugin.config as cfg
from calibre_plugins.k2pdfopt_plugin.pdf import construct_cmd_args, get_k2pdfopt_path
from calibre_plugins.k2pdfopt_plugin.common_utils import get_icon, DragDropComboBox
from calibre_plugins.k2pdfopt_plugin.gui.preview import Preview
from calibre_plugins.k2pdfopt_plugin.gui.presets import PresetsBar

def dummy_metadata(db):
    fm = db.new_api.field_metadata
    mi = Metadata(_('Title'), [_('Author')])
    mi.author_sort = _('Author Sort')
    mi.series = ngettext('Series', 'Series', 1)
    mi.series_index = 3
    mi.rating = 4.0
    mi.tags = [_('Tag 1'), _('Tag 2')]
    mi.languages = ['eng']
    mi.id = 1
    mi.set_all_user_metadata(fm.custom_field_metadata())
    for col in mi.get_all_user_metadata(False):
        mi.set(col, (col,), 0)
    return mi

def get_metadata_object(gui):
    db = gui.current_db
    try:
        current_row = gui.library_view.currentIndex()
        book_id = gui.library_view.model().id(current_row)
        mi = db.new_api.get_proxy_metadata(book_id)
    except Exception as e:
        if DEBUG:
            prints('Error: exception trying to get mi from current row')
        try:
            book_id = list(db.all_ids())[0]
            mi = db.new_api.get_proxy_metadata(book_id)
        except:
            mi = dummy_metadata(db)
    return mi

class CmdLineOptsText(QWidget):
    def __init__(self, parent, gui):
        QWidget.__init__(self, parent)
        self.gui = gui
        self._init_controls()

    def _init_controls(self):
        l = QHBoxLayout()
        self.setLayout(l)
        if self.gui:
            cmd_box = QGroupBox(_('Additional options'))
            box_l = QVBoxLayout()
            cmd_box.setLayout(box_l)
            l.addWidget(cmd_box)
            self.text_edit = QTextEdit()
            box_l.addWidget(self.text_edit)
        else:
            lbl_command = QLabel(_('Additional options'))
            lbl_command.setToolTip(tt.cmdopts)
            self.ledit = QLineEdit()
            l.addWidget(lbl_command)
            l.addWidget(self.ledit)

    def text(self):
        if self.gui:
            return self.text_edit.toPlainText()
        else:
            return self.ledit.text()

    def setText(self, text):
        if self.gui:
            self.text_edit.setPlainText(text)
        else:
            self.ledit.setText(text)

def validate_cmdopts_template(gui, cmdopts):
    mi = get_metadata_object(gui)
    output = SafeFormat().safe_format(cmdopts, mi, 'TEMPLATE ERROR', mi)
    if output.startswith('TEMPLATE ERROR'):
        msg = 'Template error'
        det = 'Command line option template failed with error: {}'.format(output.lstrip('TEMPLATE ERROR'))
        return (msg, det)
    else:
        return True

class Files(QWidget):

    selection_changed = pyqtSignal(bool)

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self._init_controls()

    def _init_controls(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        button_l = QHBoxLayout()
        layout.addLayout(button_l)

        self.add_button = QPushButton(QIcon(I('document-new.png')), _('Add'), self)
        self.add_button.clicked.connect(self.add)
        self.remove_button = QPushButton(QIcon(('trash.png')), _('Remove'), self)
        self.remove_button.clicked.connect(self.remove)

        self.file_list = QListWidget(self)
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setAlternatingRowColors(True)
        layout.addWidget(self.file_list)

        button_l.addWidget(self.add_button)
        button_l.addWidget(self.remove_button)

        button_l.addStretch(1)

        self.populate([], select_index=0)
        self.file_list.itemSelectionChanged.connect(self._on_selection_change)
        self.file_list.itemDoubleClicked.connect(self._open_file)

        folder_layout = self.folder_layout = QHBoxLayout()
        folder_lbl = QLabel(_('Output folder:'))
        self.folder_combo = DragDropComboBox(self, drop_mode='file')
        self.choose_folder_button = QToolButton(self)
        self.choose_folder_button.setToolTip(_('Choose folder'))
        self.choose_folder_button.setIcon(QIcon(I('document_open.png')))
        self.choose_folder_button.clicked.connect(self._choose_folder)
        folder_layout.addWidget(folder_lbl)
        folder_layout.addWidget(self.folder_combo, 1)
        folder_layout.addWidget(self.choose_folder_button)
        layout.addLayout(self.folder_layout)

        self._on_selection_change()

    def _on_selection_change(self):
        items_count = len(self.file_list.selectedItems())
        self.remove_button.setEnabled(items_count > 0)
        # used by parent to for preview_button.setEnabled()
        self.selection_changed.emit(items_count > 0)

    def _open_file(self, item):
        selected_file = item.text()
        open_local_file(selected_file)

    def populate(self, names, clear=True, select_index=None):
        initial_count = self.file_list.count()
        if clear:
            self.file_list.clear()

        existing = self.get_all()

        for name in names:
            if name in existing:
                # Don't allow duplicates
                if DEBUG:
                    prints('K2pdf Plugin: {} already exists in filelist'.format(name))
                continue
            elif os.path.splitext(name)[-1].lower() not in ['.pdf', '.djvu']:
                continue
            item = QListWidgetItem(name, self.file_list)
            item.setIcon(QIcon(I('mimetypes/pdf.png')))
            existing.append(name)

        count = len(names) + initial_count

        current_item = self.file_list.currentItem()
        if select_index == None:
            if not self.file_list.currentItem():
                select_index = count-1
        else:
            select_index += initial_count
        if (select_index in range(count)) and count:
            self.file_list.setCurrentRow(select_index)

    def remove(self):
        selected_items = self.file_list.selectedItems()
        current_row =  self.file_list.currentRow()
        message = _('<p>Are you sure you want to remove the {} selected file(s)?</p>'.format(len(selected_items)))
        if not question_dialog(self, _('Are you sure'), message):
            return
        for item in reversed(selected_items):
            row = self.file_list.row(item)
            self.file_list.takeItem(row)

        count = self.file_list.count()
        if (current_row in range(count)) and count:
            self.file_list.setCurrentRow(current_row)

    def add(self):
        chosen_files = choose_files(
            None, _('Select file dialog'), _('Select a file'),
            all_files=True, select_only_single_file=False)
        if not chosen_files:
            return

        if iswindows:
            new = []
            for x in chosen_files:
                new.append(os.path.normpath(x))
            chosen_files = new

        self.populate(chosen_files, clear=False)

    def _choose_folder(self, *args):
        loc = choose_dir(self, 'k2pdfopt-choose-folder',
                _('Choose folder to save converted books to'))
        if loc:
            self.folder_combo.setCurrentText(loc)

    def get_folder(self):
        path = self.folder_combo.currentText().strip()
        if iswindows:
            path = os.path.normpath(path)
        return path

    def get_all(self):
        data = []
        for row in range(self.file_list.count()):
            text = self.file_list.item(row).text().strip()
            if iswindows:
                text = os.path.normpath(text)
            data.append(text)
        return data

    def get_current(self):
        current_row =  self.file_list.currentRow()
        current_item = self.file_list.item(current_row)
        if current_item:
            return current_item.text().strip()

class CmdDialog(Dialog):
    def __init__(self, parent=None, text=''):
        self.text = text
        Dialog.__init__(
            self,
            _('k2pdf Main Dialog'),
            'k2pdfopt-args-dialog',
            parent
        )

    def setup_ui(self):
        l = QVBoxLayout()
        self.setLayout(l)
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(self.text)
        self.text_edit.setReadOnly(True)
        l.addWidget(self.text_edit)


class MainDialog(Dialog):
    def __init__(self, parent=None, name='k2pdf-main-dialog', title=_('K2pdfopt Plugin')):
        self.gui = get_gui()
        if not self.gui:
            name += '-standalone'
        Dialog.__init__(self, title, name, parent)

    def setup_ui(self):
        self._init_controls()
        # FIXME: restore_defaults has to be called twice.
        # probably because all the changes that happens when
        # _mode_changed() is invoked
        #self.restore_defaults()
        self.restore_defaults()
        settings = cfg.plugin_prefs[cfg.KEY_LAST_USED_SETTINGS]
        cfg.get_missing_values_from_defaults({'k2pdfopt': cfg.CONVERSION_DEFAULTS}, settings)
        self.load_settings(settings)

    def _init_controls(self):
        l = self.l = QHBoxLayout()
        self.setLayout(l)
        self.blockSignals(True)

        scroll_widget = QWidget()
        scroll_l = QVBoxLayout()
        scroll_widget.setLayout(scroll_l)

        scroll = QScrollArea()
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidgetResizable(True)
        #scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        scroll.setWidget(scroll_widget)
        #scroll.setMinimumHeight(80)
        #l.addWidget(scroll, 6, 0, 1, 2)

        self.presets = PresetsBar(self)

        options_groupbox = QGroupBox('Options')
        options_l = QGridLayout()
        options_groupbox.setLayout(options_l)

        device_groupbox = QGroupBox('Device')
        device_l = QGridLayout()
        device_groupbox.setLayout(device_l)

        margins_groupbox = QGroupBox('Crop margins (Inches)')
        margins_l = QGridLayout()
        margins_groupbox.setLayout(margins_l)

        para_groupbox = QGroupBox(_('Parameters'))
        para_l = QGridLayout()
        para_groupbox.setLayout(para_l)

        self.preview = Preview(self)
        #self.preview.setSizePolicy(QSizePolicyIgnored, QSizePolicyIgnored)
        self.convert_button = QPushButton(_('Convert'))
        self.defaults_button = QPushButton(_('Restore defaults'))
        self.defaults_button.clicked.connect(self.restore_defaults)
        self.cmd_version_button = QPushButton(_('Show command version'))
        self.cmd_version_button.clicked.connect(self.on_cmd_version_clicked)

        # Checkboxes
        self.autostraighten_chk = QCheckBox(_('Autostraighten'))
        self.autostraighten_chk.setToolTip(tt.autostraighten)
        self.break_after_chk = QCheckBox(_('Break after each source page'))
        self.break_after_chk.setToolTip(tt.break_after)
        self.color_chk = QCheckBox(_('Color output'))
        self.color_chk.setToolTip(tt.color)
        self.landscape_chk = QCheckBox(_('Rotate output to landscape'))
        self.landscape_chk.setToolTip(tt.landscape)
        self.native_chk = QCheckBox(_('Native PDF output'))
        self.native_chk.setToolTip(tt.native)
        self.native_chk.stateChanged.connect(self._on_native_state_change)
        self.rtl_chk = QCheckBox(_('Right-to-left text'))
        self.rtl_chk.setToolTip(tt.rtl)
        self.reflow_chk = QCheckBox(_('Re-flow text'))
        self.reflow_chk.setToolTip(tt.reflow)
        self.reflow_chk.stateChanged.connect(self._on_reflow_state_change)
        self.erase_vl_chk = QCheckBox(_('Erase vertical lines'))
        self.erase_vl_chk.setToolTip(tt.erase_vl)
        self.erase_hl_chk = QCheckBox(_('Erase horizontal lines'))
        self.erase_hl_chk.setToolTip(tt.erase_hl)
        self.autocrop_chk = QCheckBox(_('Auto Crop'))
        self.autocrop_chk.setToolTip(tt.autocrop)

        row = 0
        col = 0
        options_l.addWidget(self.break_after_chk, row, col, 1, 1)
        row += 1
        options_l.addWidget(self.landscape_chk, row, col, 1, 1)
        row += 1
        options_l.addWidget(self.native_chk, row, col, 1, 1)
        row += 1
        options_l.addWidget(self.erase_vl_chk, row, col, 1, 1)
        row += 1
        options_l.addWidget(self.erase_hl_chk, row, col, 1, 1)
        row = 0
        col = 1
        options_l.addWidget(self.autostraighten_chk, row, col, 1, 1)
        row += 1
        options_l.addWidget(self.rtl_chk, row, col, 1, 1)
        row += 1
        options_l.addWidget(self.color_chk, row, col, 1, 1)
        row += 1
        options_l.addWidget(self.reflow_chk, row, col, 1, 1)
        row += 1
        options_l.addWidget(self.autocrop_chk, row, col, 1, 1)

        # Misc options
        lbl_max_cols = QLabel(_('Max columns'))
        lbl_max_cols.setToolTip(tt.max_cols)
        self.max_cols_spin = QSpinBox()
        self.max_cols_spin.setMaximum(10000)
        self.max_cols_spin.setMinimum(0)
        lbl_drf = QLabel(_('Document resolution factor'))
        lbl_drf.setToolTip(tt.drf)
        self.drf_spin = QDoubleSpinBox()
        self.drf_spin.setMaximum(10000.0)
        self.drf_spin.setMinimum(0.0)
        self.drf_spin.setSingleStep(0.1)
        lbl_pages = QLabel(_('Pages to convert'))
        lbl_pages.setToolTip(tt.pages)
        self.pages_ledit = QLineEdit()
        if not self.gui:
            lbl_command = QLabel(_('Additional options'))
            lbl_command.setToolTip(tt.cmdopts)
            self.cmdopts_ledit = QLineEdit()
        lbl_font_size = QLabel(_('Fixed output font size'))
        lbl_font_size.setToolTip(tt.font_size)
        self.font_size_spin = QDoubleSpinBox()
        self.font_size_spin.setMaximum(100.0)
        self.font_size_spin.setMinimum(0.0)
        self.font_size_spin.setSingleStep(0.1)
        self.font_size_spin.setToolTip(tt.font_size)
        #lbl_cover_image = QLabel(_('Page to use as cover'))
        #lbl_cover_image.setToolTip(tt.cover_image)
        #self.cover_image_spin = QSpinBox()
        #self.cover_image_spin.setMaximum(10000)
        #self.cover_image_spin.setMinimum(0)
        #self.cover_image_spin.setToolTip(tt.cover_image)
        lbl_conversion_mode = QLabel(_('Conversion mode'))
        lbl_conversion_mode.setToolTip(tt.modes)
        self.conversion_mode_combo = QComboBox()
        self.conversion_mode_combo.addItems([''] + list(cfg.MODE_MAP.values()))
        self.conversion_mode_combo.currentTextChanged.connect(self._mode_changed)

        row = 0
        col = 0
        para_l.addWidget(lbl_max_cols, row, col, 1, 1)
        para_l.addWidget(self.max_cols_spin, row, col+1, 1, 1)
        row += 1
        para_l.addWidget(lbl_drf, row, col, 1, 1)
        para_l.addWidget(self.drf_spin, row, col+1, 1, 1)
        row += 1
        para_l.addWidget(lbl_pages, row, col, 1, 1)
        para_l.addWidget(self.pages_ledit, row, col+1, 1, 1)
        if not self.gui:
            row += 1
            para_l.addWidget(lbl_command, row, col, 1, 1)
            para_l.addWidget(self.cmdopts_ledit, row, col+1, 1, 1)
        row += 1
        para_l.addWidget(lbl_font_size, row, col, 1, 1)
        para_l.addWidget(self.font_size_spin, row, col+1, 1, 1)
        #row += 1
        #para_l.addWidget(lbl_cover_image, row, col, 1, 1)
        #para_l.addWidget(self.cover_image_spin, row, col+1, 1, 1)
        row += 1
        para_l.addWidget(lbl_conversion_mode, row, col, 1, 1)
        para_l.addWidget(self.conversion_mode_combo, row, col+1, 1, 1)

        # Device
        device_reset_l = QHBoxLayout()
        self.device_combo = QComboBox()
        self.device_combo.addItems(list(cfg.DEVICE_NAME_MAP.values()))
        self.device_combo.currentTextChanged.connect(self._on_device_change)
        self.device_reset_button = QToolButton()
        self.device_reset_button.setIcon(QIcon(I('edit-undo.png')))
        self.device_reset_button.setToolTip(_('Reset device settings'))
        self.device_reset_button.clicked.connect(self._on_device_reset)
        device_reset_l.addWidget(self.device_combo)
        device_reset_l.addWidget(self.device_reset_button)
        lbl_width = QLabel(_('Width'))
        self.width_spin = QSpinBox()
        self.width_spin.setMaximum(10000)
        self.width_spin.setMinimum(0)
        #self.width_spin.setSingleStep(1)
        self.width_unit_combo = QComboBox()
        self.width_unit_combo.addItems(list(cfg.UNIT_MAP.values()))
        self.width_unit_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon)
        lbl_height = QLabel(_('Height'))
        self.height_spin = QSpinBox()
        self.height_spin.setMaximum(10000)
        self.height_spin.setMinimum(0)
        self.height_unit_combo = QComboBox()
        self.height_unit_combo.addItems(list(cfg.UNIT_MAP.values()))
        self.height_unit_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon)
        lbl_dpi = QLabel(_('DPI'))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setMaximum(10000)
        self.dpi_spin.setMinimum(0)

        #device_l.addWidget(self.device_combo, 0, 0, 1, 3)
        device_l.addLayout(device_reset_l, 0, 0, 1, 3)
        device_l.addWidget(lbl_width, 1, 0, 1, 1)
        device_l.addWidget(self.width_spin, 1, 1, 1, 1)
        device_l.addWidget(self.width_unit_combo, 1, 2, 1, 1)
        device_l.addWidget(lbl_height, 2, 0, 1, 1)
        device_l.addWidget(self.height_spin, 2, 1, 1, 1)
        device_l.addWidget(self.height_unit_combo, 2, 2, 1, 1)
        device_l.addWidget(lbl_dpi, 3, 0, 1, 1)
        device_l.addWidget(self.dpi_spin, 3, 1, 1, 2)

        # Margins
        lbl_left = QLabel(_('Left'))
        self.left_margin_spin = QDoubleSpinBox()
        self.left_margin_spin.setMaximum(10000.0)
        self.left_margin_spin.setMinimum(0.0)
        self.left_margin_spin.setSingleStep(0.1)
        lbl_top = QLabel(_('Top'))
        self.top_margin_spin = QDoubleSpinBox()
        self.top_margin_spin.setMaximum(10000.0)
        self.top_margin_spin.setMinimum(0.0)
        self.top_margin_spin.setSingleStep(0.1)
        lbl_right = QLabel(_('Right'))
        self.right_margin_spin = QDoubleSpinBox()
        self.right_margin_spin.setMaximum(10000.0)
        self.right_margin_spin.setMinimum(0.0)
        self.right_margin_spin.setSingleStep(0.1)
        lbl_bottom = QLabel(_('Bottom'))
        self.bottom_margin_spin = QDoubleSpinBox()
        self.bottom_margin_spin.setMaximum(10000.0)
        self.bottom_margin_spin.setMinimum(0.0)
        self.bottom_margin_spin.setSingleStep(0.1)

        margins_l.addWidget(lbl_left, 0, 0, 1, 1)
        margins_l.addWidget(self.left_margin_spin, 0, 1, 1, 1)
        margins_l.addWidget(lbl_top, 1, 0, 1, 1)
        margins_l.addWidget(self.top_margin_spin, 1, 1, 1, 1)
        margins_l.addWidget(lbl_right, 2, 0, 1, 1)
        margins_l.addWidget(self.right_margin_spin, 2, 1, 1, 1)
        margins_l.addWidget(lbl_bottom, 3, 0, 1, 1)
        margins_l.addWidget(self.bottom_margin_spin, 3, 1, 1, 1)

        vl1 = QVBoxLayout()
        preview_l = self.preview_l = QVBoxLayout()
        hl2 = QHBoxLayout()
        buttons_l = self.buttons_l = QGridLayout()
        l.addLayout(vl1, stretch=1)
        l.addLayout(preview_l, stretch=1)
        preview_l.addLayout(hl2)

        vl1.addWidget(self.presets)
        vl1.addWidget(scroll)
        if self.gui:
            # 1. Add Input format combobox
            self.input_combo = QComboBox()
            self.input_combo.addItems(['PDF', 'ORIGINAL_PDF'])
            self.input_combo.currentTextChanged.connect(self._on_input_format_change)
            input_gb = QGroupBox(_('Input format'))
            input_l = QHBoxLayout()
            input_gb.setLayout(input_l)
            input_l.addWidget(self.input_combo)
            scroll_l.addWidget(input_gb)
            # 2. Add cmd options box
            self.cmdopts_ledit = CmdLineOptsText(self, self.gui)
            self.cmdopts_ledit.setToolTip(tt.cmdopts)
            scroll_l.addWidget(self.cmdopts_ledit)
        else:
            # insert filelist when invoked outside calibre
            self.files = Files(self)
            self.preview.preview_button.setEnabled(False)
            self.files.selection_changed.connect(self._on_files_selection_change)
            scroll_l.addWidget(self.files)
        scroll_l.addWidget(options_groupbox)
        scroll_l.addWidget(para_groupbox)
        vl1.addLayout(buttons_l)
        preview_l.addWidget(self.preview)
        hl2.addWidget(device_groupbox)
        hl2.addWidget(margins_groupbox)
        buttons_l.addWidget(self.defaults_button, 0, 0, 1, 1)
        buttons_l.addWidget(self.cmd_version_button, 0, 1, 1, 1)
        buttons_l.addWidget(self.convert_button, 1, 0, 1, 2)

        self.convert_button.clicked.connect(self.on_convert_clicked)
        if self.gui:
            self.preview.open_current_file.connect(self.open_current_file)
            self.preview.open_button.setEnabled(bool(self.get_currently_selected_book()))
        else:
            self.preview.open_button.setVisible(False)

    def _mode_changed(self, current_text):
        mode = {v:k for k,v in cfg.MODE_MAP.items()}.get(current_text, '')
        native = mode not in ['copy','def','def_k2','crop','crop_k2']
        if not native:
            self.native_chk.setChecked(native)
        self.native_chk.setEnabled(native)
        wrapped = mode not in ['copy','fp','fw','2col','crop_k2']
        if not wrapped:
            self.reflow_chk.setChecked(wrapped)
        self.reflow_chk.setEnabled(wrapped)
        color = mode not in ['def_k2','crop_k2']
        if not color:
            self.color_chk.setChecked(color)
        self.color_chk.setEnabled(color)
        landscape = mode not in ['def', 'def_k2','crop','crop_k2']
        if not landscape:
            self.landscape_chk.setChecked(landscape)
        self.landscape_chk.setEnabled(landscape)
        if mode and not (mode in ['def', 'def_k2','2col']):
            self.max_cols_spin.setValue(1)
        if mode in ['def','def_k2','2col']:
            self.max_cols_spin.setValue(2)
        if mode:
            s = copy.deepcopy(self.save_settings()['k2pdfopt'])
            s.update(cfg.MODE_SETTINGS_MAP[mode])
            self.load_settings({'k2pdfopt': s})

    def _on_native_state_change(self, state):
        if self.native_chk.isChecked():
            self.reflow_chk.setChecked(False)
            #self.cover_image_spin.setValue(0)

    def _on_reflow_state_change(self, state):
        if self.reflow_chk.isChecked():
            self.native_chk.setChecked(False)

    def _on_device_change(self, text):
        device = {v: k for k, v in cfg.DEVICE_NAME_MAP.items()}.get(text)
        if device:
            self.width_spin.setValue(cfg.DEVICE_WIDTH_MAP[device])
            self.width_unit_combo.setCurrentText(cfg.UNIT_MAP.get('p'))
            self.height_spin.setValue(cfg.DEVICE_HEIGHT_MAP[device])
            self.height_unit_combo.setCurrentText(cfg.UNIT_MAP.get('p'))
            self.dpi_spin.setValue(cfg.DEVICE_DPI_MAP[device])

        self.width_spin.setReadOnly(device is not None)
        self.width_unit_combo.setDisabled(device is not None)
        self.height_spin.setReadOnly(device is not None)
        self.height_unit_combo.setDisabled(device is not None)
        self.dpi_spin.setReadOnly(device is not None)

    def _on_files_selection_change(self, b):
        self.preview.preview_button.setEnabled(b)

    def _on_input_format_change(self):
        self.preview.open_button.setEnabled(bool(self.get_currently_selected_book()))

    def _on_device_reset(self):
        self.device_combo.setCurrentIndex(-1)
        self.height_spin.setValue(0)
        #self.height_unit_combo.setCurrentIndex(-1)
        self.width_spin.setValue(0)
        #self.width_unit_combo.setCurrentIndex(-1)
        self.dpi_spin.setValue(0)

    def save_settings(self):
        settings = {}
        s = {}
        # checkboxes
        s['autostraighten'] = self.autostraighten_chk.isChecked()
        s['break_after'] = self.break_after_chk.isChecked()
        s['color'] = self.color_chk.isChecked()
        s['landscape'] = self.landscape_chk.isChecked()
        s['native'] = self.native_chk.isChecked()
        s['rtl'] = self.rtl_chk.isChecked()
        s['reflow'] = self.reflow_chk.isChecked()
        s['erase_vl'] = self.erase_vl_chk.isChecked()
        s['erase_hl'] = self.erase_hl_chk.isChecked()
        s['autocrop'] = self.autocrop_chk.isChecked()

        # misc
        s['max_cols'] = self.max_cols_spin.value()
        s['drf'] = self.drf_spin.value()
        s['pages'] = self.pages_ledit.text()
        s['cmdopts'] = self.cmdopts_ledit.text()
        conversion_mode_text = self.conversion_mode_combo.currentText()
        s['conversion_mode'] = {v:k for k,v in cfg.MODE_MAP.items()}.get(conversion_mode_text, '')
        s['fixed_font_size'] = self.font_size_spin.value()
        #s['cover_image'] = self.cover_image_spin.value()

        # Device
        device_text = self.device_combo.currentText()
        s['device'] = {v: k for k,v in cfg.DEVICE_NAME_MAP.items()}.get(device_text)
        width_unit_text = self.width_unit_combo.currentText()
        height_unit_text = self.height_unit_combo.currentText()
        s['width'] = [ self.width_spin.value(), {v: k for k,v in cfg.UNIT_MAP.items()}.get(width_unit_text) ]
        s['height'] = [ self.height_spin.value(), {v: k for k,v in cfg.UNIT_MAP.items()}.get(height_unit_text) ]
        s['dpi'] = self.dpi_spin.value()

        # Margins
        s['margins'] = [
            self.left_margin_spin.value(),
            self.top_margin_spin.value(),
            self.right_margin_spin.value(),
            self.bottom_margin_spin.value()
        ]
        settings['k2pdfopt'] = s

        # Other
        settings['preset_name'] = self.presets.preset_name
        if self.gui:
            settings['input_fmt'] = self.input_combo.currentText()

        return settings

    def load_settings(self, settings):
        s = settings['k2pdfopt']
        # checkboxex
        self.autostraighten_chk.setChecked(s['autostraighten'])
        self.break_after_chk.setChecked(s['break_after'])
        self.color_chk.setChecked(s['color'])
        self.landscape_chk.setChecked(s['landscape'])
        self.native_chk.setChecked(s['native'])
        self.rtl_chk.setChecked(s['rtl'])
        self.reflow_chk.setChecked(s['reflow'])
        self.erase_vl_chk.setChecked(s['erase_vl'])
        self.erase_hl_chk.setChecked(s['erase_hl'])
        self.autocrop_chk.setChecked(s['autocrop'])

        # misc
        self.max_cols_spin.setValue(s['max_cols'])
        self.drf_spin.setValue(s['drf'])
        self.pages_ledit.setText(s['pages'])
        self.cmdopts_ledit.setText(s['cmdopts'])
        conversion_mode = s['conversion_mode']
        if conversion_mode in cfg.MODE_MAP.keys():
            self.conversion_mode_combo.setCurrentText(cfg.MODE_MAP[conversion_mode])
        else:
            self.conversion_mode_combo.setCurrentText(conversion_mode)

        self.font_size_spin.setValue(s['fixed_font_size'])
        #self.cover_image_spin.setValue(s['cover_image'])

        # Device
        device_text = cfg.DEVICE_NAME_MAP[s['device']]
        self.device_combo.setCurrentText(device_text)
        self._on_device_change(device_text)
        width, width_unit = s['width']
        self.width_spin.setValue(width)
        self.width_unit_combo.setCurrentText(cfg.UNIT_MAP[width_unit])
        height, height_unit = s['height']
        self.height_spin.setValue(height)
        self.height_unit_combo.setCurrentText(cfg.UNIT_MAP[height_unit])
        self.dpi_spin.setValue(s['dpi'])

        # Margins
        self.left_margin_spin.setValue(s['margins'][0])
        self.top_margin_spin.setValue(s['margins'][1])
        self.right_margin_spin.setValue(s['margins'][2])
        self.bottom_margin_spin.setValue(s['margins'][3])

        # Other
        self.presets.preset_name = settings.get('preset_name', '')
        if self.gui:
            self.input_combo.setCurrentText(settings.get('input_fmt', 'PDF'))

    def persist_settings(self):
        settings = self.save_settings()
        last_used_preset = settings['preset_name']
        if last_used_preset:
            preset_settings = cfg.plugin_prefs[cfg.KEY_PRESETS][last_used_preset]
            if preset_settings['k2pdfopt'] != settings['k2pdfopt']:
                settings['preset_name'] = ''
        cfg.plugin_prefs[cfg.KEY_LAST_USED_SETTINGS] = settings

    def restore_defaults(self):
        self.load_settings({'k2pdfopt':cfg.CONVERSION_DEFAULTS})

    def get_input_format(self):
        if self.gui:
            fmt = self.input_combo.currentText() or 'PDF'
        else:
            fmt = 'PDF'
        return fmt

    def get_currently_selected_book(self):
        if self.gui:
            row = self.gui.library_view.currentIndex()
            try:
                book_id = self.gui.library_view.model().id(row)
            except:
                # no books selected
                return None
            src_file = self.gui.current_db.format_abspath(book_id, self.get_input_format(), index_is_id=True)
            if src_file:
                return src_file
        else:
            return self.files.get_current()

    def on_cmd_version_clicked(self):
        cmd_args = construct_cmd_args(self.save_settings()['k2pdfopt'])
        d = CmdDialog(self, ' '.join(cmd_args))
        d.exec_()

    def open_current_file(self, *args):
        if self.gui:
            f = self.get_currently_selected_book()
            if f:
                open_local_file(f)
            else:
                fmt = self.get_input_format()
                if DEBUG:
                    prints('K2pdfopt Plugin: No {} file found.'.format(fmt))

    def on_convert_clicked(self):
        if self.gui:
            self.input_format = self.get_input_format()
        settings = self.save_settings()
        self.conversion_settings = settings['k2pdfopt']
        if DEBUG:
            prints(self.conversion_settings)
        cmd_args = construct_cmd_args(self.conversion_settings)
        is_cmdopt_template_valid = validate_cmdopts_template(self.gui, self.conversion_settings['cmdopts'])
        if is_cmdopt_template_valid is True:
            if DEBUG:
                prints('K2pdfopt Plugin: cmd_args: {}'.format(cmd_args))
            self.persist_settings()
            Dialog.accept(self)
        else:
            error_dialog(self, *is_cmdopt_template_valid, show=True)

    def closeEvent(self, ev):
        # Kill any preview thread before leaving
        self.preview.abort.set()
        Dialog.closeEvent(self, ev)

class K2pdfoptPathDialog(Dialog):

    def __init__(self, parent, path=''):
        self.path = path
        Dialog.__init__(self, 'K2pdfopt Path', 'k2pdfopt-path-dialog', parent)

    def setup_ui(self):
        l = QVBoxLayout(self)
        self.setLayout(l)
        lbl = QLabel(_(
            'Choose the path for k2pdfopt here.\n'
            'Make sure the it has execusion permissions.'))
        self.binary_box = QGroupBox(_('Path to k2pdfopt:'))
        l.addWidget(self.binary_box)
        binary_layout = QVBoxLayout()
        self.binary_box.setLayout(binary_layout)
        self.binary_combo = DragDropComboBox(self, drop_mode='file')
        self.binary_combo.setCurrentText(self.path)
        binary_layout.addWidget(self.binary_combo)
        hl1 = QHBoxLayout()
        binary_layout.addWidget(lbl)
        binary_layout.addLayout(hl1)
        hl1.addWidget(self.binary_combo, 1)
        self.choose_binary_button = QToolButton(self)
        self.choose_binary_button.setToolTip(_('Choose binary'))
        self.choose_binary_button.setIcon(get_icon('document_open.png'))
        self.choose_binary_button.clicked.connect(self._choose_file)
        hl1.addWidget(self.choose_binary_button)

        l.addWidget(self.bb)
        self.setMinimumWidth(400)

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

    def accept(self):
        self.path = self.binary_combo.currentText()
        Dialog.accept(self)
