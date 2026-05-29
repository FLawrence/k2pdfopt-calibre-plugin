#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2024, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

import os
import regex
import shlex
import shutil
import subprocess
import re
import traceback
import time
import copy
from threading import Event

try:
    from qt.core import Qt, QApplication
except ImportError:
    from PyQt5.Qt import Qt, QApplication

from calibre import prints
from calibre.constants import iswindows, isosx, islinux, DEBUG
from calibre.gui2 import error_dialog
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.utils.date import now, as_local_time

import calibre_plugins.k2pdfopt_plugin.config as cfg
import calibre_plugins.k2pdfopt_plugin.constants as cons

try:
    load_translations()
except NameError:
    prints("k2pdfopt_plugin::k2pdfopt.py - exception when loading translations")

def validate_k2pdfopt_path(k2pdfopt_path):
    try:
        subprocess.call([k2pdfopt_path] + cfg.MANDATORY_OPTS)
    except:
        traceback.print_exc()
        return False
    return True

def get_k2pdfopt_path():
    k2pdfopt_path = cfg.plugin_prefs[cfg.KEY_K2PDFOPT_PATH]
    if not k2pdfopt_path:
        if iswindows:
            k2pdfopt_path = 'k2pdfopt.exe'
        else:
            k2pdfopt_path = 'k2pdfopt'
    is_valid = validate_k2pdfopt_path(k2pdfopt_path)
    if is_valid:
        return k2pdfopt_path
    else:
        return False

def validate_pagelist(pagelist):
    '''
        Valid arg should look like 2-52e,3-33o,111-
    '''
    numbers = re.split(',|-|o|e', pagelist)

    for num in numbers:
        try:
            integer = int(number)
        except:
            return False
        if int(num) == 0:
            return False
    return TRUE

def remove_arg(arg, arg_list):
    try:
        indices = []
        for idx, x in enumerate(arg_list):
            if arg in cons.MULTIFORM_OPTS:
                if x.startswith(arg):
                    if DEBUG:
                        prints('remove_arg: {} match multiform at index {}'.format(arg, idx))
                    indices.append(idx)
            else:
                if re.search(r'^{}[\-\+]*\b'.format(arg), x):
                    if DEBUG:
                        prints('remove_arg: {} match at index {}'.format(arg, idx))
                    indices.append(idx)
        for idx in reversed(indices):
            # first remove arguments following the opt (args not starting with -)
            # FIXME: args following -p opt can start with dash e.g. -p -111
            if len(arg_list) >= idx+2:
                if not str(arg_list[idx+1]).startswith('-'):
                    del arg_list[idx+1]
            del arg_list[idx]
    except ValueError:
        pass

def parse_cmdopts(cmdopts, add_args_to_exclude=[]):
    if cmdopts.strip():
        cmdopts = shlex.split(cmdopts)
    else:
        cmdopts = []
    for arg in ['-o','-x','-y','-ui','-gui', '-\?'] + add_args_to_exclude:
        remove_arg(arg, cmdopts)
    return cmdopts

def construct_cmd_args(
    settings,
    additional_args=[],
    add_args_to_exclude=[]
):
    cmd_args = []
    # First parse cmdopts
    cmdopts = parse_cmdopts(
        settings.get('cmdopts', ''),
        add_args_to_exclude=add_args_to_exclude)
    if DEBUG:
        prints('cmdopts: {}'.format(cmdopts))
    ignore = {'cmdopts'}
    device = settings.get('device', '')
    if device:
        ignore.add('width')
        ignore.add('height')
        ignore.add('dpi')
    for k, v in settings.items():
        if (k in ignore) or (not k.strip()) or (k not in cfg.CONVERSION_DEFAULTS.keys()): continue
        opt = cfg.OPT_NAME_MAP[k]
        if regex.search('\b{}\b'.format(opt), ' '.join(cmdopts)):
            # option already specified in the cmdopts
            # discard as we give priority to cmdopts
            pass
        else:
            if k in [
                'max_cols',
                'drf',
                'fixed_font_size',
                'dpi',
                'conversion_mode',
                'pages',
                'cover_image'
            ]:
                if v:
                    cmd_args += [opt, str(v)]
            if k == 'device':
                if v is not None:
                    cmd_args += [opt, v]
            elif k in ['width','height']:
                if v[0]:
                    cmd_args += [opt, ''.join([str(x) for x in v])]
            elif k in ['cbox','margins']:
                if v != [0.0,0.0,0.0,0.0]:
                    cmd_args += [opt, ','.join([str(x)+'in' for x in v])]
            elif k in ['erase_vl', 'erase_hl']:
                if v is True:
                    cmd_args += [opt, '1']
            elif k == 'fastpreview':
                if v == True:
                    cmd_args += [opt, 'auto']
            elif k == 'reflow':
                if v == False:
                    cmd_args += [opt+'-']
            elif k == 'ocr':
                if v == True:
                    cmd_args += [opt, 't']
            elif k == 'autocrop':
                if v == True:
                    cmd_args += [opt, '0.1']
                else:
                    cmd_args += [opt+'-']
            elif v is True:
                cmd_args += [opt]
    # cmdopts have priority so added last
    cmd_args += cmdopts
    for arg in add_args_to_exclude:
        remove_arg(arg, cmd_args)
    if additional_args:
        cmd_args += additional_args
    cmd_args += cfg.MANDATORY_OPTS
    return cmd_args

def post_convert_for_all(gui, library_hex_id, input_format, output_format, tdir, extracted_ids):
    QApplication.setOverrideCursor(Qt.WaitCursor)
    db = gui.current_db
    refresh_ids = []
    start_time = now()
    try:
        for book_id, title, in_f, of in extracted_ids:
            ok = post_convert_for_book(gui, library_hex_id, book_id, title, in_f, of, input_format, output_format, refresh=False)
            if ok:
                refresh_ids.append(book_id)
        shutil.rmtree(tdir)
        db_last_modified = as_local_time(db.last_modified())
        if db_last_modified > start_time:
            cr = gui.library_view.currentIndex().row()
            gui.library_view.model().refresh_ids(refresh_ids, cr)
            gui.tags_view.recount()
    finally:
        QApplication.restoreOverrideCursor()


def post_convert_for_book(gui, library_hex_id, book_id, title, in_f, of, input_format, output_format, refresh=True, **kwargs):
    db = gui.current_db
    refresh_ids = []
    res = False
    if cfg.plugin_prefs[cfg.KEY_POST_CONVERT_ACT] == 'addFormat':
        # First we back up the original file, if the backup file is the source, skip
        if input_format.lower().startswith('original_') or (input_format.lower() == 'djvu'):
            backup_format = input_format
        else:
            backup_format = 'ORIGINAL_' + input_format
            has_backup = db.format_abspath(book_id, backup_format, index_is_id=True)
            if not has_backup:
                if DEBUG:
                    prints('K2pdfopt Plugin: Backing up {} format for book: {}'.format(input_format, title))
                tdir = os.path.dirname(of)
                backup_path = os.path.join(tdir, str(book_id) + '.' + backup_format.lower())
                with open(backup_path, 'wb') as f:
                    db.copy_format_to(book_id, input_format, f, index_is_id=True)
                    db.new_api.add_format(book_id, backup_format, backup_path)
        #
        # Now copy the converted file to replace pdf format, but first make sure the backup file is there.
        has_backup = db.format_abspath(book_id, backup_format, index_is_id=True)
        if has_backup:
            db.new_api.add_format(book_id, output_format, of)
            refresh_ids.append(book_id)
            res = True
        else:
            # Cannot find the backuped file. skip adding new converted file
            if DEBUG:
                prints('K2pdfopt Plugin: Cannot find backup format. Not replacing original file with converted one: {}'.format(title))

    elif cfg.plugin_prefs[cfg.KEY_POST_CONVERT_ACT] == 'addBook':
        mi = db.get_metadata(
            book_id,
            index_is_id=True,
            get_user_categories=False,
            get_cover=True,
            cover_as_data=False)
        if library_hex_id:
            url = '{}/{}'.format(library_hex_id, book_id)
            if DEBUG:
                prints('K2pdfopt Plugin: Adding link to original book: {}'.format(url))
            mi.set_identifier('src_book', url)
        try:
            new_id = db.import_book(mi, [])
            refresh_ids.append(new_id)
            if DEBUG:
                prints('K2pdfopt Plugin: Addig new book: {}'.format(new_id))
            db.new_api.add_format(new_id, output_format, of)
            res = True
        except:
            traceback.print_exc()

    if refresh:
        cr = gui.library_view.currentIndex().row()
        gui.library_view.model().refresh_ids(refresh_ids, cr)
        gui.tags_view.recount()
        gui.status_bar.show_message(_('Converted {} for book {}'.format(input_format, title)), 5000)
        try:
            os.remove(in_f)
            os.remove(of)
        except:
            traceback.print_exc()
    return res

def truncate(string, length=50):
    return (string[:length] + '..') if len(string) > length else string

def convert_without_jobs(gui, conversion_settings, books, abort=Event(), pbar=None):
    kw = {}
    if pbar:
        logger = pbar.write
        kw = {'logger': logger}
    failed_ids = []
    extracted_ids = []
    if pbar:
        pbar.cmd_error = ''
    count = len(books)
    for idx, book in enumerate(books, 1):
        try:
            mi, path_to_input_format, path_to_output_format = book
            title = mi.title
            if pbar:
                pbar.update_overall(100)
            book_conversion_settings = copy.deepcopy(conversion_settings)
            if gui:
                # Fist: process cmdopts template
                template = book_conversion_settings['cmdopts']
                cmdopts = SafeFormat().safe_format(template, mi, 'TEMPLATE ERROR', mi)
                if cmdopts.startswith('TEMPLATE ERROR'):
                    prints('WARNING: Template Error: {}'.format(cmdopts))
                    book_conversion_settings['cmdopts'] = ''
                else:
                    book_conversion_settings['cmdopts'] = cmdopts
                # Second: copy src_file from calibre library to tdir, as to not
                # give k2pdfopt access to library files
                ext = os.path.splitext(path_to_input_format)[1][1:]
                if ext.lower().startswith('original_'):
                    ext = ext.lower().lstrip('original_')
                new_input = os.path.splitext(path_to_output_format)[0] + '_input.' + ext
                shutil.copy(path_to_input_format, new_input)
                path_to_input_format = new_input
            text = truncate(_('Converting book {} of {}: {}'.format(idx, count, title)))
            proc = K2pdfoptProcess(book_conversion_settings, path_to_input_format, path_to_output_format, abort=abort, pbar=pbar, progress_msg=text, **kw)
            proc.run()
            is_ok = bool(proc.exit_status)
            msg = proc.all_output
            if is_ok is True:
                extracted_ids.append((mi.id, mi.title, path_to_input_format, path_to_output_format))
                msg = 'Book ({}) converted successfuly\n'.format(title) + msg
            else:
                failed_ids.append(mi)
                msg = 'Title ({})\n'.format(title) + msg
                if pbar:
                    pbar.cmd_error += msg + '\n'
            if DEBUG:
                prints(msg)
            if pbar:
                pbar.update_progress(1, _('Converting book: {}'.format(title)))
        except:
            traceback.print_exc()
            failed_ids.append(mi)
        if abort.is_set():
            return
    if pbar:
        pbar.failed_ids = failed_ids
        pbar.extracted_ids = extracted_ids
    return extracted_ids, failed_ids

class K2pdfoptProcess(object):
    def __init__(self,
                 conversion_settings,
                 path_to_input_format,
                 path_to_output_format,
                 add_args_to_exclude=[],
                 additional_args=[],
                 abort=Event(),
                 notifications=None,
                 logger=None,
                 working_dir=None,
                 shell=False,
                 pbar=None,
                 progress_msg=''
    ):
        self.conversion_settings = conversion_settings
        self.path_to_input_format = path_to_input_format
        self.path_to_output_format = path_to_output_format
        self.add_args_to_exclude = add_args_to_exclude
        self.additional_args = additional_args
        self.logger = logger or prints
        self.shell = shell
        self.abort = abort
        self.pbar = pbar
        self.progress_msg = progress_msg
        self.notifications = notifications
        self.all_output = ''
        self._progress = 0
        self.previous_progress = 0
        self.exit_status = None
        self.returncode = None
        self.working_dir = working_dir

    def kwargs(self):
        clean_env = dict(os.environ)
        kw = {'env': clean_env, 'shell': self.shell}
        if self.working_dir:
            kw['cwd'] = self.working_dir
        kw['stdout'] = stdout=subprocess.PIPE
        kw['stderr'] = stdout=subprocess.PIPE
        #kw['stderr'] = stdout=subprocess.STDOUT
        kw['bufsize'] = 1
        if isosx:
            pass
            #TODO: Test on macosx and see whether it needs to run through shell.
            #kw['shell'] = True
        else:
            if iswindows:
                #DETACHED_PROCESS = 0x00000008
                kw['creationflags'] = subprocess.CREATE_NO_WINDOW
                del clean_env['PATH']
            else:
                clean_env['LD_LIBRARY_PATH'] = ''
        return kw

    def build_args(self):
        args = construct_cmd_args(
            self.conversion_settings,
            additional_args=self.additional_args,
            add_args_to_exclude=self.add_args_to_exclude)
        if self.path_to_output_format:
            args += ['-o', os.path.normpath(self.path_to_output_format)]
        args.append(os.path.normpath(self.path_to_input_format))
        return args

    def run(self):
        k2pdfopt_path = os.path.normpath(get_k2pdfopt_path())
        cmd = [k2pdfopt_path] + self.build_args()
        kw = self.kwargs()
        if kw['shell'] == True:
            cmd = self.shell_cmd()
        if DEBUG:
            prints('K2pdfopt Plugin: About to run command: {}'.format(cmd))
        if self.pbar:
            self.pbar.update_progress(0, self.progress_msg)
        previous_p = 0
        self.proc = proc = subprocess.Popen(cmd, **kw)
        while proc.poll() is None:
            text = proc.stdout.readline().decode('utf-8', errors='ignore')
            self.all_output += text
            self.logger(text)
            self.parse_progress()
            self.update_progress_bars()
            if self.abort.is_set():
                if kw['shell'] == True:
                    #TODO: proc.terminate() only kills the shell and not the defunct command
                    pass
                else:
                    proc.kill()
                    proc.wait()
                    return
        for line in proc.stdout.read().decode('utf-8', errors='ignore').split('\n'):
            self.logger(line) #remainder of post-polled buffer
            self.all_output += line

        proc.communicate()
        self.return_code = proc.returncode
        if proc.returncode == 0:
            self.exit_status = True
        else:
            self.exit_status = False

    def shell_cmd(self):
        k2pdfopt_path = os.path.normpath(get_k2pdfopt_path())
        cmd = construct_cmd_args(self.conversion_settings)
        cmd = ' '.join(cmd)
        if self.path_to_output_format:
            cmd += ' -o "{}"'.format(os.path.normpath(self.path_to_output_format))
        if ' ' in k2pdfopt_path:
            k2pdfopt_path = '"{}"'.format(k2pdfopt_path)
        cmd = '{} {} "{}"'.format(k2pdfopt_path, cmd, os.path.normpath(self.path_to_input_format))
        return cmd

    def parse_progress(self):
        for line in reversed(self.all_output.split('\n')):
            if re.search(r'.*SOURCE.PAGE.*?(\d+) of (\d+).*', line):
                current = re.sub(r'.*SOURCE.PAGE.*?(\d+) of (\d+).*', r'\1', line)
                total = re.sub(r'.*SOURCE.PAGE.*?(\d+) of (\d+).*', r'\2', line)
                try:
                    progress = int(current) / int(total)
                    self._progress = progress
                    break
                except:
                    traceback.print_exc()

    def update_progress_bars(self):
        # notifications is a queue used to update calibre job progress
        if self.notifications:
            self.notifications.put((self.progress, 'converting PDF'))
        # pbar is progress dialog if invoked outside calibre
        if self.pbar:
            p = int(self.progress * 100)
            if p > self.previous_progress:
                self.pbar.update_progress(p - self.previous_progress, self.progress_msg)
                self.previous_progress = p

    @property
    def progress(self):
        return self._progress
