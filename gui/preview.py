#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2024, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

import os, sys
import re
import shutil
import traceback
from functools import partial
from threading import Event, Thread

try:
    from qt.core import (
        Qt, QApplication, QWidget, QHBoxLayout, QVBoxLayout, QCheckBox, QAction,
        QToolButton, QPushButton, QPixmap, QUrl, QPalette, QSize, QLineEdit,
        QIntValidator, QLabel, QScrollArea, pyqtSignal, QSizePolicy, QIcon)

    AlignHCenter = Qt.AlignmentFlag.AlignHCenter
    AlignVCenter = Qt.AlignmentFlag.AlignVCenter
    LeftButton = Qt.MouseButton.LeftButton
    ClosedHandCursor = Qt.CursorShape.ClosedHandCursor
    ControlModifier = Qt.KeyboardModifier.ControlModifier
    ColorRoleText = QPalette.ColorRole.Text
    ColorRoleBase = QPalette.ColorRole.Base
    ColorRoleDark = QPalette.ColorRole.Dark
    QSizePolicyIgnored = QSizePolicy.Policy.Ignored
except ImportError:
    from PyQt5.Qt import (
        Qt, QApplication, QWidget, QHBoxLayout, QVBoxLayout, QCheckBox, QAction,
        QToolButton, QPushButton, QPixmap, QUrl, QPalette, QSize, QLineEdit,
        QIntValidator, QLabel, QScrollArea, pyqtSignal, QSizePolicy, QIcon)

    AlignHCenter = Qt.AlignHCenter
    AlignVCenter = Qt.AlignVCenter
    LeftButton = Qt.LeftButton
    ClosedHandCursor = Qt.ClosedHandCursor
    ControlModifier = Qt.ControlModifier
    ColorRoleText = QPalette.Text
    ColorRoleBase = QPalette.Base
    ColorRoleDark = QPalette.Dark
    QSizePolicyIgnored = QSizePolicy.Ignored

from calibre import fit_image, prints
from calibre.constants import DEBUG
from calibre.gui2 import error_dialog
from calibre.ptempfile import PersistentTemporaryDirectory

from calibre_plugins.k2pdfopt_plugin.common_utils import get_icon
from calibre_plugins.k2pdfopt_plugin.pdf import K2pdfoptProcess
import calibre_plugins.k2pdfopt_plugin.config as cfg

try:
    load_translations()
except NameError:
    prints("k2pdfopt_plugin::gui/preview.py - exception when loading translations")

preview_window_css = '''
QLabel {
    text-align: center;
    vertical-align: middle;
    font-size: 50px;
    font-weight: bold;
    color: #593470;
    background-color: #ada9b0}
'''

def pdf_page_count(src_file):
    proc = K2pdfoptProcess({}, src_file, '', [], ['-i'])
    proc.run()
    is_ok = bool(proc.exit_status)
    msg = proc.all_output
    if is_ok:
        ext = os.path.splitext(src_file)[-1]
        if ext.lower() == '.pdf':
            try:
                if re.search(r'.*PAGES:\s*(\d+).*', msg):
                    c = re.sub(r'.*PAGES:\s*(\d+).*', r'\1', msg, flags=re.M | re.DOTALL)
                    return int(c)
            except:
                traceback.print_exc()
        elif ext.lower() == '.djvu':
            try:
                if re.search(r'.*?(\d+) total pages.*', msg):
                    c = re.sub(r'.*?(\d+) total pages.*', r'\1', msg, flags=re.M | re.DOTALL)
                    return int(c)
            except:
                traceback.print_exc()
    else:
        if DEBUG:
            prints(msg)

def create_image_preview(pdf_file,
                         preview_img_path,
                         conversion_settings,
                         page_no,
                         working_dir,
                         abort=Event()):
    try:
        dir_ = os.path.dirname(pdf_file)
        pdf_frag = os.path.join(dir_, 'preview.pdf')
        proc = K2pdfoptProcess(
            {},
            pdf_file,
            pdf_frag,
            [],
            ['-p', str(page_no), '-mode', 'copy', '-dpi', '323', '-n'],
            abort=abort)
        proc.run()
        is_ok = bool(proc.exit_status)
        msg = proc.all_output
        if not os.path.exists(pdf_frag):
            msg = 'K2pdfopt Plugin: Unable to create pdf fragment\n' \
                  'This can happen sometimes with empty pages\n' \
                  + msg
            is_ok = False
        # Sometimes frag will be created if page is out of range
        # k2pdfopt will keep on converting the whole book, so
        # you have to abort the fork job running this function
        # Inability to count pages of djvu makes puts us in this
        # situation.
        if 'no pages to convert' in msg.lower():
            is_ok = False
            abort.set()
        if not is_ok:
            return is_ok, msg

        # k2pdfopt creates 'k2pdfopt_out.png' in the cwd. You have
        # to pass self.tdir to k2pdfopt in cwd arg
        proc = K2pdfoptProcess(conversion_settings,
                               pdf_frag,
                               '',
                               ['-p', '-sm'],
                               ['-bmp', '1'],
                               abort=abort,
                               working_dir=working_dir)
        proc.run()
        is_ok = bool(proc.exit_status)
        msg = proc.all_output

        if not os.path.exists(preview_img_path):
            msg = 'K2pdfopt Plugin: k2pdfopt did not create preview image\n' + msg
            is_ok = False
        return is_ok, msg
    finally:
        try:
            os.remove(pdf_frag)
        except:
            pass

class Label(QLabel):

    toggle_fit = pyqtSignal()
    zoom_requested = pyqtSignal(bool)

    def __init__(self, scrollarea):
        QLabel.__init__(self, scrollarea)
        scrollarea.zoom_requested.connect(self.zoom_requested)
        try:
            self.setBackgroundRole(ColorRoleText if QApplication.instance().is_dark_theme else ColorRoleBase)
        except:
            # Earlier calibre versions that does not suuport dark theme
            # and don't have QApplication.instance().is_dark_theme
            self.setBackgroundRole(ColorRoleBase)
        self.setSizePolicy(QSizePolicyIgnored, QSizePolicyIgnored)
        self.setScaledContents(True)
        self.default_cursor = self.cursor()
        self.in_drag = False
        self.prev_drag_position = None
        self.scrollarea = scrollarea

    @property
    def is_pannable(self):
        return self.scrollarea.verticalScrollBar().isVisible() or self.scrollarea.horizontalScrollBar().isVisible()

    def mousePressEvent(self, ev):
        if ev.button() == LeftButton and self.is_pannable:
            self.setCursor(ClosedHandCursor)
            self.in_drag = True
            self.prev_drag_position = ev.globalPos()
        return QLabel(self).mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == LeftButton and self.in_drag:
            self.setCursor(self.default_cursor)
            self.in_drag = False
            self.prev_drag_position = None
        return QLabel(self).mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self.prev_drag_position is not None:
            p = self.prev_drag_position
            self.prev_drag_position = pos = ev.globalPos()
            self.dragged(pos.x() - p.x(), pos.y() - p.y())
        return QLabel(self).mouseMoveEvent(ev)

    def dragged(self, dx, dy):
        h = self.scrollarea.horizontalScrollBar()
        if h.isVisible():
            h.setValue(h.value() - dx)
        v = self.scrollarea.verticalScrollBar()
        if v.isVisible():
            v.setValue(v.value() - dy)

class ScrollArea(QScrollArea):

    toggle_fit = pyqtSignal()
    zoom_requested = pyqtSignal(bool)
    current_wheel_angle_delta = 0

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == LeftButton:
            self.toggle_fit.emit()

    def wheelEvent(self, ev):
        if ev.modifiers() == ControlModifier:
            ad = ev.angleDelta().y()
            if ad * self.current_wheel_angle_delta < 0:
                self.current_wheel_angle_delta = 0
            self.current_wheel_angle_delta += ad
            if abs(self.current_wheel_angle_delta) >= 120:
                self.zoom_requested.emit(self.current_wheel_angle_delta < 0)
                self.current_wheel_angle_delta = 0
            ev.accept()
        else:
            QScrollArea(self).wheelEvent(ev)

class Preview(QWidget):

    open_current_file = pyqtSignal(object)
    error = pyqtSignal(str, str)
    restore_preview_button = pyqtSignal()
    show_image = pyqtSignal(str)
    show_text = pyqtSignal(str, str)

    def __init__(self, parent):
        QWidget.__init__(self)
        self.current_url = ''
        self.current_img = None
        self.factor = 1.0
        self.is_fit_image = False
        self.tdir = PersistentTemporaryDirectory('_k2pdfopt_preview')
        self.original_src_file = None
        self.abort = Event()
        self._init_controls()

    def _init_controls(self):
        self.scrollarea = sa = ScrollArea()
        sa.setAlignment(AlignHCenter | AlignVCenter)
        sa.setBackgroundRole(ColorRoleDark)
        self.label = l = Label(sa)
        l.zoom_requested.connect(self.zoom_requested)
        sa.setWidget(l)

        self.zi_button = QToolButton()
        self.zi_button.setToolTip(_('Zoom In'))
        self.zi_button.setIcon(QIcon(I('plus.png')))
        self.zi_button.clicked.connect(self.zoom_in)
        self.zo_button = QToolButton()
        self.zo_button.setToolTip(_('Zoom Out'))
        self.zo_button.setIcon(QIcon(I('minus.png')))
        self.zo_button.clicked.connect(self.zoom_out)
        self.actual_size_button = QToolButton()
        self.actual_size_button.setToolTip(_('Actual Size'))
        self.actual_size_button.setIcon(get_icon('images/actual_size.png'))
        self.actual_size_button.clicked.connect(self.fit_to_actual_size)
        self.fitimage_button = QToolButton()
        self.fitimage_button.setToolTip(_('Fit Image'))
        self.fitimage_button.setIcon(get_icon('images/fitimage.png'))
        self.fitimage_button.clicked.connect(self.set_to_viewport_size)
        self.preview_button = QPushButton(_('Preview'))
        self.preview_button.setCheckable(True)
        self.preview_button.toggled.connect(self._on_preview_toggled)

        self.move_10_left_button = QToolButton(self)
        self.move_10_left_button.setToolTip(_('Move 10 pages less'))
        self.move_10_left_button.setIcon(get_icon('images/arrow_left_double.png'))
        self.move_10_left_button.clicked.connect(partial(self.move_pages, -10))

        # move left one page button
        self.move_left_button = QToolButton(self)
        self.move_left_button.setToolTip(_('Move one page less'))
        self.move_left_button.setIcon(get_icon('images/arrow_left_single.png'))
        self.move_left_button.clicked.connect(partial(self.move_pages, -1))

        onlyInt = QIntValidator()
        onlyInt.setRange(1, 10000)
        self.page_ledit = QLineEdit()
        self.page_ledit.setValidator(onlyInt)
        self.page_ledit.setText('1')
        self.page_ledit.setToolTip('Page number to preview')
        self.page_ledit.textChanged.connect(self.refresh_buttons)

        # move right one page button
        self.move_right_button = QToolButton(self)
        self.move_right_button.setToolTip(_('Move one page more'))
        self.move_right_button.setIcon(get_icon('images/arrow_right_single.png'))
        self.move_right_button.clicked.connect(partial(self.move_pages, 1))

        # move right 10 pages button
        self.move_10_right_button = QToolButton(self)
        self.move_10_right_button.setToolTip(_('Move 10 pages more'))
        self.move_10_right_button.setIcon(get_icon('images/arrow_right_double.png'))
        self.move_10_right_button.clicked.connect(partial(self.move_pages, 10))

        self.open_button = QToolButton(self)
        self.open_button.setToolTip(_('Open currently selected file'))
        self.open_button.setIcon(get_icon('document_open.png'))
        self.open_button.clicked.connect(self.open_current_file.emit)

        self.l = l = QVBoxLayout(self)
        self.h1 = h1 = QHBoxLayout()
        h1.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h1)
        l.addWidget(sa, stretch=1)
        self.h2 = h2 = QHBoxLayout()
        h2.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h2)
        h1.addWidget(self.open_button)
        h1.addStretch(1)
        h1.addWidget(self.actual_size_button)
        h1.addWidget(self.fitimage_button)
        h1.addWidget(self.zi_button)
        h1.addWidget(self.zo_button)

        h2.addWidget(self.preview_button, stretch=1)
        h2.addWidget(self.move_10_left_button)
        h2.addWidget(self.move_left_button)
        h2.addWidget(self.page_ledit)
        h2.addWidget(self.move_right_button)
        h2.addWidget(self.move_10_right_button)

        self.error.connect(self._on_error)
        self.restore_preview_button.connect(self.do_restore_preview_button)
        self.show_image.connect(self.do_show_image)
        self.show_text.connect(self.do_show_text)

        self.refresh_buttons()
        self.resize(450, 600)
        self.do_show_text('Preview Window', preview_window_css)

    def set_to_viewport_size(self):
        page_size = self.scrollarea.size()
        pw, ph = page_size.width() - 2, page_size.height() - 2
        img_size = self.current_img.size()
        iw, ih = img_size.width(), img_size.height()
        scaled, nw, nh = fit_image(iw, ih, pw, ph)
        if scaled:
            self.factor = min(nw/iw, nh/ih)
        img_size.setWidth(nw), img_size.setHeight(nh)
        self.label.resize(img_size)
        self.is_fit_image = True

    def resizeEvent(self, ev):
        if self.is_fit_image:
            self.set_to_viewport_size()
        if not self.current_img:
            # Resize text label
            self.label.resize(self.scrollarea.size())

    def factor_from_fit(self):
        scaled_height = self.label.size().height()
        actual_height = self.current_img.size().height()
        return scaled_height / actual_height

    def zoom_requested(self, zoom_out):
        if not self.current_image:
            return
        if (zoom_out and self.zo_button.isEnabled()) or (not zoom_out and self.zi_button.isEnabled()):
            (self.zoom_out if zoom_out else self.zoom_in)()

    def zoom_in(self):
        if self.is_fit_image:
            factor = self.factor_from_fit()
            self.factor = factor
        self.factor *= 1.25
        self.adjust_image(1.25)

    def zoom_out(self):
        if self.is_fit_image:
            factor = self.factor_from_fit()
            self.factor = factor
        self.factor *= 0.8
        self.adjust_image(0.8)

    def fit_to_actual_size(self):
        if not self.current_img:
            return
        self.factor = 1
        self.adjust_image(1)

    def adjust_image(self, factor):
        self.label.resize(self.factor * self.current_img.size())
        self.zi_button.setEnabled(self.factor <= 3)
        self.zo_button.setEnabled(self.factor >= 0.3333)
        self.adjust_scrollbars(factor)
        self.is_fit_image = False

    def adjust_scrollbars(self, factor):
        for sb in (self.scrollarea.horizontalScrollBar(),
                self.scrollarea.verticalScrollBar()):
            sb.setValue(int(factor*sb.value()) + int((factor - 1) * sb.pageStep()/2))

    def image_from_pixmap(self, pixmap=QPixmap(), page=1):
        self.current_img = pixmap
        self.refresh_image()
        if page:
            self.page_ledit.setText(str(page))
        self.refresh_buttons()

    def image_from_path(self, img_path):
        self.current_img = QPixmap()
        self.current_img.load(img_path)
        self.current_url = QUrl.fromLocalFile(img_path)
        self.refresh_image()
        self.refresh_buttons()

    def refresh_image(self):
        self.label.setPixmap(self.current_img)
        self.label.adjustSize()
        reso = ''
        if self.current_img and not self.current_img.isNull():
            if self.factor != 1:
                self.adjust_image(self.factor)
            reso = '[{}x{}]'.format(self.current_img.width(), self.current_img.height())
        #self.set_to_viewport_size()

    def do_show_text(self, text, css=None, page=None):
        self.current_image = None
        self.is_fit_image = False
        self.label.setText(text)
        if css:
            self.label.setStyleSheet(css)
        self.label.resize(self.scrollarea.size())
        self.label.setAlignment(Qt.AlignCenter)
        font = self.font()
        font.setPointSize(24)
        self.label.setFont(font)
        if page:
            self.page_ledit.setText(str(page))

    def do_show_image(self, path):
        try:
            self.image_from_path(path)
        finally:
            try:
                os.remove(path)
            except:
                pass

    def move_pages(self, num):
        new_num = int(self.page_ledit.text()) + num
        if new_num >= 0:
            self.page_ledit.setText(str(new_num))
        self.refresh_buttons()

    def refresh_buttons(self, *args):
        num = int(self.page_ledit.text() or 1)
        self.move_10_left_button.setEnabled(num > 10)
        self.move_left_button.setEnabled(num > 1)
        self.zi_button.setEnabled(bool(self.current_url))
        self.zo_button.setEnabled(bool(self.current_url))
        self.fitimage_button.setEnabled(bool(self.current_url))
        self.actual_size_button.setEnabled(bool(self.current_url))

    def _on_preview_toggled(self, f):
        if f:
            self.abort.clear()
            self.preview_button.setText('Cancel')
            self.thread = Thread(target=self.do_preview)
            self.thread.start()
        else:
            self.abort.set()
            self.preview_button.setEnabled(False)

    def _on_error(self, msg, det):
        return error_dialog(
            self,
            msg,
            det,
            show=True)

    def do_restore_preview_button(self):
        self.preview_button.blockSignals(True)
        self.preview_button.setEnabled(True)
        self.preview_button.setChecked(False)
        self.preview_button.setText('Preview')
        self.preview_button.blockSignals(False)
        self.abort.clear()

    def do_preview(self):
        # k2pdfopt creates 'k2pdfopt_out.png' in the cwd. You have
        # to pass self.tdir to k2pdfopt in cwd arg
        preview_img_path = os.path.join(self.tdir, 'k2pdfopt_out.png')
        try:
            conversion_settings = self.parent().save_settings()['k2pdfopt']
            page_no = str(self.page_ledit.text())
            if page_no:
                src_file = self.parent().get_currently_selected_book()
                if not src_file:
                    fmt = self.parent().get_input_format()
                    self.show_text.emit('Format\n{}\nnot available'.format(fmt), preview_window_css)
                    if DEBUG:
                        prints('K2pdfopt Plugin: No {} file found.'.format(fmt))
                    return
                ext = os.path.splitext(src_file)[-1][1:].lstrip('original_')
                copied_src_file = os.path.join(self.tdir, 'src.'+ext)
                if src_file == self.original_src_file:
                    # file was already copied before to copied_src_file. skip
                    if DEBUG:
                        prints('K2pdfopt Plugin: File already copied: {}'.format(src_file))
                else:
                    # copy src_file to tdir, to prevent k2pdfopt from accessing
                    # the calibre library folder. It must have the name src.pdf
                    # for the get_info() function to work properly
                    # cache the path if the src_file to prevent re-copying it
                    # later again when generating another previews from the
                    # same book
                    shutil.copy(src_file, copied_src_file)
                    self.original_src_file = src_file
                # Count file pages to make sure page is within range.
                # If you give k2pdfopt a page out of range, it generates
                # preview for the whole pdf file.
                # Note: Thiw will nor work for djvu files
                #if copied_src_file.lower().endswith('.pdf'):
                count = pdf_page_count(copied_src_file)
                if count:
                    if int(page_no) > count:
                        msg = _('Page out of range')
                        det = _('The currently selected book contains {} pages. Preview page must be within this range.'.format(count))
                        self.error.emit(msg, det)
                        #error_dialog(
                            #self,
                            #msg,
                            #det,
                            #show=True
                        #)
                        return
                #
                else:
                    if DEBUG:
                        prints('K2pdf Plugin: unable to get count for source file')
                    return
                try:
                    # remove any lingering previews from previous runs
                    os.remove(preview_img_path)
                except:
                    pass
                self.show_text.emit('Previewing\nPage: {}'.format(page_no), preview_window_css)
                try:
                    is_ok, msg = create_image_preview(copied_src_file,
                                                      preview_img_path,
                                                      conversion_settings,
                                                      page_no,
                                                      abort=self.abort,
                                                      working_dir = self.tdir)
                except:
                    if DEBUG:
                        traceback.print_exc()
                    self.restore_preview_button.emit()
                    self.show_text.emit('Preview Failed', preview_window_css)
                    return
                if self.abort.is_set():
                    self.restore_preview_button.emit()
                    self.show_text.emit('Preview Aborted', preview_window_css)
                    return
                #is_ok, msg = r['result']
                if is_ok and os.path.exists(preview_img_path):
                    self.show_image.emit(preview_img_path)
                    return
                else:
                    if DEBUG:
                        prints(msg)
                    self.show_text.emit('Preview Failed', preview_window_css)
                    return
            self.show_text.emit('Preview Window', preview_window_css)
        except:
            traceback.print_exc()
        finally:
            self.restore_preview_button.emit()
            self.thread = None
            # remove preview png after displaying it.
            sys.exit()

if __name__ == '__main__':
    path = sys.argv[-1]
    app = QApplication([])
    d = Peview(None)
    d.image_from_path(path)
    d()
    app.exec_()
