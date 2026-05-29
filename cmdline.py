#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2024, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

import os, sys
import shutil
from functools import partial
import traceback
from threading import Event

try:
    from qt.core import QApplication
except ImportError:
    from PyQt5.Qt import QApplication

_app = QApplication([])

from calibre import prints
from calibre.constants import DEBUG
from calibre.gui2 import error_dialog, info_dialog

from calibre_plugins.k2pdfopt_plugin.action import K2pdfoptAction
from calibre_plugins.k2pdfopt_plugin.common_utils import (
    load_resources, set_plugin_icon_resources)
from calibre_plugins.k2pdfopt_plugin.gui.main import MainDialog, K2pdfoptPathDialog
from calibre_plugins.k2pdfopt_plugin.gui.progress import DoubleProgressDialog
from calibre_plugins.k2pdfopt_plugin.pdf import (
    get_k2pdfopt_path, validate_k2pdfopt_path, convert_without_jobs)
import calibre_plugins.k2pdfopt_plugin.config as cfg

try:
    load_translations()
except NameError:
    prints("k2pdfopt_plugin::cmdline.py - exception when loading translations")

class Mi:
    pass

icon_resources = load_resources(K2pdfoptAction.name, cfg.PLUGIN_ICONS)
set_plugin_icon_resources(K2pdfoptAction.name, icon_resources)

class NoCalibreDialog(MainDialog):
    def on_convert_clicked(self):
        conversion_settings = self.save_settings()['k2pdfopt']
        if DEBUG:
            prints(conversion_settings)
        files = self.files.get_all()
        output_dir = self.files.get_folder()
        if output_dir:
            if not (os.access(output_dir, os.W_OK) and os.path.isdir(output_dir)):
                return error_dialog(
                    self,
                    _('Directory error'),
                    _('Path supplied for output directory is not a valid writable direcotry'),
                    show=True)
        if not files:
            return error_dialog(
                self,
                _('No books'),
                _('You must choose at least one book to convert'),
                show=True)
        self.persist_settings()
        books = []
        abort = Event()
        for f in files:
            base = os.path.basename(f)
            name, ext = os.path.splitext(base)
            input_dir = os.path.dirname(f)
            #FIXME: Make sure no name clashes from files coming from different
            # folders having the same basename
            if output_dir == input_dir or not output_dir:
                of = None
            else:
                of = os.path.join(output_dir, name+'_k2opt'+ext)
            mi = Mi()
            mi.title = base
            mi.id = None
            books.append((mi, f, of))
        try:
            count = len(books)
            pd = DoubleProgressDialog(
                count,
                partial(convert_without_jobs, None, conversion_settings, books, abort),
                self,
                abort=abort,
                details=True,
                title=_('Converting PDFs')
            )
            pd.exec_()
            pd.thread = None
            if pd.failed_ids:
                failed_titles = [mi.title for mi in pd.failed_ids]
                return error_dialog(
                    self,
                    _('Failed'),
                    'Failed to convert some books',
                    det_msg='Failed titles: {}\n{}\n{}'.format(failed_titles, pd.cmd_error, pd.logged_details.strip()),
                    show=True)
            elif pd.error is not None:
                return error_dialog(
                    self,
                    _('Failed'),
                    pd.error[0], det_msg=pd.error[1] + '\n' + pd.logged_details.strip(),
                    show=True)
            else:
                info_dialog(
                    self,
                    _('Convesion done'),
                    'Finished converting {} books'.format(count),
                    det_msg=pd.logged_details.strip(),
                    show=True,
                    show_copy_button=False)
        except:
            traceback.print_exc()


def cmdline_run(args):
    res = get_k2pdfopt_path()
    if res is False:
        d = K2pdfoptPathDialog(None, path=cfg.plugin_prefs[cfg.KEY_K2PDFOPT_PATH])
        if d.exec_() == d.Accepted:
            if validate_k2pdfopt_path(d.path):
                cfg.plugin_prefs[cfg.KEY_K2PDFOPT_PATH] = d.path
                cfg.plugin_prefs.commit()
            else:
                return error_dialog(
                    d,
                    _('Path not found'),
                    _('Unable to run k2pdfopt from specified location. '
                      'Make sure you enter the right path and that the file '
                      'has execution permissions'),
                    show=True
                )
        else:
            return

    d = NoCalibreDialog()
    d.exec_()

if __name__ == '__main__':
    args = sys.argv
    if "K2pdfopt Plugin" in args:
        args.remove("K2pdfopt Plugin")
    #_app = QApplication(args)
    cmdline_run(args)
    sys.exit(_app.exec_())
