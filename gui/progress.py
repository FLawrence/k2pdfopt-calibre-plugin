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
from threading import Thread, Event
from functools import partial

try:
    from qt.core import (
        Qt, QApplication, QVBoxLayout, QHBoxLayout, QProgressDialog, QTimer,
        QDialog, QDialogButtonBox, pyqtSignal, QProgressBar, QLabel,
        QTextEdit, QObject, QTextCursor, QPushButton)
    CURSOR_END = QTextCursor.MoveOperation.End
except ImportError:
    from PyQt5.Qt import (
        Qt, QApplication, QVBoxLayout, QHBoxLayout, QProgressDialog, QTimer,
        QDialog, QDialogButtonBox, pyqtSignal, QProgressBar, QLabel,
        QTextEdit, QObject, QTextCursor, QPushButton)
    CURSOR_END = QTextCursor.End

from calibre import prints
from calibre.constants import DEBUG, iswindows
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.gui2 import error_dialog, warning_dialog, Dispatcher
from calibre.utils.date import now, as_local_time

from calibre_plugins.k2pdfopt_plugin.pdf import post_convert_for_book
from calibre_plugins.k2pdfopt_plugin.common_utils import get_library_hex_id
from calibre_plugins.k2pdfopt_plugin.jobs import start_convert

class PreProcessProgressDialog(QProgressDialog):

    def __init__(self, gui, conversion_settings, book_ids, tdir, input_format, output_format):
        QProgressDialog.__init__(self, 'Preparing books', u'', 0, len(book_ids), gui)
        self.setWindowTitle(_('Queueing books for converting PDFs'))
        self.setMinimumWidth(500)
        self.book_ids = book_ids
        self.conversion_settings = conversion_settings
        self.gui = gui
        self.db = gui.current_db
        self.input_format = input_format
        self.output_format = output_format
        self.tdir = tdir
        self.i = 0
        self.failed_ids, self.no_format_ids, self.books_to_scan = [], [], []
        # QTimer workaround on Win 10 on first go for Win10/Qt6 users not displaying dialog properly.
        QTimer.singleShot(100, self.do_book)
        self.exec_()

    def do_book(self):
        book_id = self.book_ids[self.i]
        self.i += 1
        title = ''
        try:
            src_file = self.db.format_abspath(book_id, self.input_format, index_is_id=True)
            title = self.db.title(book_id, index_is_id=True)
            mi = self.db.get_metadata(book_id, index_is_id=True, get_user_categories=False)
            # cmd opts box supports templates {
            book_conversion_settings = copy.deepcopy(self.conversion_settings)
            template = book_conversion_settings['cmdopts']
            cmdopts = SafeFormat().safe_format(template, mi, 'TEMPLATE ERROR', mi)
            if cmdopts.startswith('TEMPLATE ERROR'):
                prints('WARNING: Template Error: {}'.format(cmdopts))
                book_conversion_settings['cmdopts'] = ''
            else:
                book_conversion_settings['cmdopts'] = cmdopts
            # }
            if not src_file:
                self.failed_ids.append((book_id, title))
                self.no_format_ids.append((book_id, title))
            else:
                ext = self.input_format.lower()
                if ext.lower().startswith('original_'):
                    ext = ext.lower().lstrip('original_')
                path_to_input_format = os.path.join(self.tdir, '{}_input.{}'.format(book_id, ext))
                # copy input source so that k2pdfopt does not have access to calibre library folders
                shutil.copy(src_file, path_to_input_format)
                path_to_output_format = os.path.join(self.tdir, '{}.{}'.format(book_id, 'pdf'))
                self.setLabelText(_('Queueing') + ' ' + title)
                self.books_to_scan.append((book_id, title, book_conversion_settings, path_to_input_format, path_to_output_format))
            self.setValue(self.i)
        except:
            traceback.print_exc()
            self.failed_ids.append((book_id, title))

        if self.i >= len(self.book_ids):
            return self.do_queue()
        else:
            QTimer.singleShot(0, self.do_book)

    def do_queue(self):
        if self.gui is None:
            # There is a nasty QT bug with the timers/logic above which can
            # result in the do_queue method being called twice
            return
        self.hide()
        if self.books_to_scan == []:
            warning_dialog(self.gui, _('Converting PDF failed'),
                _('Scan aborted as no books with format found.'),
                show_copy_button=False).exec_()
        #self.gui = None
        if self.books_to_scan:
            library_hex_id = get_library_hex_id(self.db)
            for book_id, title, book_conversion_settings, path_to_input_format, path_to_output_format in self.books_to_scan:
                args = (
                    self.gui,
                    library_hex_id,
                    book_id,
                    title,
                    path_to_input_format,
                    path_to_output_format,
                    self.input_format,
                    self.output_format)
                callback = partial(post_convert_for_book, *args)
                start_convert(
                    self.gui,
                    book_id,
                    book_conversion_settings,
                    path_to_input_format,
                    path_to_output_format,
                    Dispatcher(callback))

class DoubleProgressDialog(QDialog):

    all_done = pyqtSignal()
    progress_update = pyqtSignal(int, str)
    overall_update = pyqtSignal(int)
    new_text = pyqtSignal(str)

    #class UserInterrupt(Exception):
        #pass

    def __init__(self, selected_options, callback_fn, parent, cancelable=True, abort=Event(), details=False, title=''):
        QDialog.__init__(self, parent)
        self.selected_options = selected_options
        self.logged_details = ''
        self.callback_fn = callback_fn
        self.abort = abort
        self._layout =  l = QVBoxLayout()
        self.setLayout(l)
        self.msg = QLabel()
        self.current_step_pb = QProgressBar(self)
        self.current_step_pb.setFormat(_("Current progress: %p %"))
        if self.selected_options > 1:
            # More than one Step needs to be done! Add Overall ProgressBar
            self.overall_pb = QProgressBar(self)
            self.overall_pb.setRange(0, self.selected_options)
            self.overall_pb.setValue(0)
            self.overall_pb.setFormat(_("Step %v/%m"))
            self._layout.addWidget(self.overall_pb)
            self._layout.addSpacing(15)
        self.overall_step = 0
        self.current_step_value = 0
        self._layout.addWidget(self.current_step_pb)
        self._layout.addSpacing(15)
        self._layout.addWidget(self.msg, 0, Qt.AlignLeft)
        button_layout = QHBoxLayout()
        l.addLayout(button_layout)
        self.abort_button = QPushButton(_('Abort'))
        self.abort_button.clicked.connect(self._canceled)
        if not cancelable:
            self.abort_button.setVisible(False)
        self.cancelable = cancelable
        self.canceled = False
        #
        self.show_details_button = QPushButton('Show Details')
        self.show_details_button.setCheckable(True)
        self.show_details_button.toggled.connect(self._show_detail)
        self.details_box = QTextEdit()
        self.new_text.connect(self._add_to_details)
        self._layout.addWidget(self.details_box)
        self.details_box.setVisible(False)
        #
        if details:
            button_layout.addWidget(self.show_details_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.abort_button)
        self.setWindowTitle(title)
        self.setMinimumWidth(800)
        self.error = None
        self.progress_update.connect(self.on_progress_update, type=Qt.QueuedConnection)
        self.overall_update.connect(self.on_overall_update, type=Qt.QueuedConnection)
        self.all_done.connect(self.on_all_done, type=Qt.QueuedConnection)

    def _show_detail(self, f):
        if f:
            self.show_details_button.setText('Hide')
        else:
            self.show_details_button.setText('Show Details')
        self.details_box.setVisible(f)
        self.adjustSize()

    def write(self, text):
        self.new_text.emit(text)

    def _add_to_details(self, text):
        # first save the text to display later after the progress
        # bar finishes
        self.logged_details += text.lstrip()
        cursor = self.details_box.textCursor()
        cursor.movePosition(CURSOR_END)
        cursor.insertText(text)
        self.details_box.setTextCursor(cursor)
        self.details_box.ensureCursorVisible()

    def _canceled(self, *args):
        self.canceled = True
        self.abort.set()
        self.abort_button.setDisabled(True)
        self.title = _('Aborting...')
        QDialog.reject(self)

    def reject(self):
        pass

    def accept(self):
        pass

    def update_progress(self, processed_steps, msg):
        #if self.canceled:
            #raise self.UserInterrupt
        self.progress_update.emit(processed_steps, msg)

    def on_progress_update(self, processed_steps, msg):
        self.current_step_value += processed_steps
        self.current_step_pb.setValue(self.current_step_value)
        self.msg.setText(msg)

    def update_overall(self, steps):
        self.overall_update.emit(steps)

    def on_overall_update(self, steps):
        self.current_step_value = 0
        self.current_step_pb.setRange(0, steps)
        if self.selected_options > 1:
            self.overall_step += 1
            self.overall_pb.setValue(self.overall_step)

    def exec_(self):
        self.thread = Thread(target=self.do_it)
        self.thread.start()
        return QDialog.exec_(self)

    def on_all_done(self):
        QApplication.beep()
        QDialog.accept(self)

    def do_it(self):
        try:
            self.callback_fn(pbar=self)
        #except self.UserInterrupt as e:
            ## raised when abort button is pressed.
            #QDialog.reject(self)
        except Exception as err:
            import traceback
            try:
                err = str(err)
            except:
                err = repr(err)
            self.error = (err, traceback.format_exc())
        finally:
            self.all_done.emit()
