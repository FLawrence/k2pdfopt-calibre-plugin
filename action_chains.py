#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~

__license__   = 'GPL v3'
__copyright__ = '2024, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

from qt.core import (QApplication, Qt, QWidget, QGridLayout, QHBoxLayout, QVBoxLayout,
                     QGroupBox, QComboBox, QCheckBox, QLabel, QLineEdit, QPlainTextEdit,
                     QDialogButtonBox)

from collections import defaultdict
import copy
import os

from calibre import prints
from calibre.constants import DEBUG
from calibre.gui2.ui import get_gui
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.ebooks.metadata.book.formatter import SafeFormat

from calibre_plugins.action_chains.actions.base import ChainAction

import calibre_plugins.k2pdfopt_plugin.config as cfg
from calibre_plugins.k2pdfopt_plugin.common_utils import (
    get_library_hex_id, NullContext)
from calibre_plugins.k2pdfopt_plugin.gui.main import MainDialog, validate_cmdopts_template
from calibre_plugins.k2pdfopt_plugin.pdf import (
    get_k2pdfopt_path, post_convert_for_all, convert_without_jobs)

try:
    load_translations()
except NameError:
    prints("K2pdfopt::action_chains.py - exception when loading translations")

class ConfigWidget(MainDialog):
    def __init__(self, parent, plugin_action, action, name, title):
        QWidget.__init__(self)
        self.plugin_action = plugin_action
        self.action = action
        self.gui = plugin_action.gui
        self.db = self.gui.current_db
        MainDialog.__init__(self, parent, name, title)

    def _init_controls(self):
        MainDialog._init_controls(self)
        self.convert_button.setVisible(False)
        self.preview_l.addWidget(self.bb)
        self.setMinimumSize(600,600)

    def accept(self):
        self.settings = self.save_settings()
        # validate settings
        is_valid = self.action.validate(self.settings)
        if is_valid is not True:
            msg, details = is_valid
            error_dialog(
                self,
                msg,
                details,
                show=True
            )
            return
        MainDialog.accept(self)

class K2pdfoptAction(ChainAction):

    name = 'K2pdfopt'
    support_scopes = True

    def run(self, gui, settings, chain):
        db = gui.current_db
        tdir = PersistentTemporaryDirectory('_k2pdfopt')
        book_ids = chain.scope().get_book_ids()
        books = []
        input_format = settings.get('input_fmt', 'PDF')
        output_format = 'PDF'
        no_format_ids = []
        for book_id in book_ids:
            src_file = db.format_abspath(book_id, input_format, index_is_id=True)
            if src_file:
                title = db.title(book_id, index_is_id=True)
                mi = db.get_metadata(book_id, index_is_id=True, get_user_categories=False)
                path_to_output_format = os.path.join(tdir, '{}.{}'.format(book_id, 'pdf'))
                books.append((mi, src_file, path_to_output_format))
            else:
                no_format_ids.append((book_id, title))

        extracted_ids, failed_ids = convert_without_jobs(gui, settings['k2pdfopt'], books)
        # Put Last Modified plugin into hibernation mode when adding books
        last_modified_hibernate = NullContext()
        # Test in case plugin not run from gui
        if gui and hasattr(gui, 'iactions'):
            last_modified_hibernate = getattr(gui.iactions.get('Last Modified'), 'hibernate', NullContext())
        with last_modified_hibernate:
            post_convert_for_all(gui, get_library_hex_id(db), input_format, output_format, tdir, extracted_ids)


    def validate(self, settings):
        conversion_settings = settings['k2pdfopt']
        cmdopts = conversion_settings['cmdopts']
        gui = get_gui()
        is_template_valid = validate_cmdopts_template(gui, cmdopts)
        if not is_template_valid:
            return is_template_valid
        # Validate k2pdfopt path
        path = get_k2pdfopt_path()
        if not path:
            return (
                _('Invalid Path'),
                _('You need to specify a valid path for k2pdfopt and make sure it has execution permissions'))
        return True

    def config_widget(self):
        return ConfigWidget

