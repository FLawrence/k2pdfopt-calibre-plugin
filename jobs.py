#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2024, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

import time
from threading import Event
import traceback

from calibre import prints
from calibre.constants import DEBUG
from calibre.gui2.threaded_jobs import ThreadedJob

from calibre_plugins.k2pdfopt_plugin.pdf import K2pdfoptProcess

try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9


def convert_book(conversion_settings, path_to_input_format, path_to_output_format, log, abort, notifications=None, in_process=True):
    start_time = time.time()

    # For an initial implementation we will not use child threads to scan each format
    if abort.is_set():
        return False
    proc = K2pdfoptProcess(
        conversion_settings,
        path_to_input_format,
        path_to_output_format,
        add_args_to_exclude=[],
        additional_args=[],
        abort=abort,
        notifications=notifications)
    proc.run()
    if proc.exit_status:
        return True
    else:
        log('  The scan failed to convert in %.2f secs\n'%(time.time() - start_time))
        return False

def start_convert(gui, book_id, conversion_settings, path_to_input_format, path_to_output_format, callback):
    '''
    This approach to converting PDF uses an in-process Thread to
    perform the work. This offers high performance, but suffers from
    memory leaks in the Calibre conversion process and will make the
    GUI less responsive for large numbers of books.

    It is retained only for the purposes of converting a single PDF
    as it is considerably faster than the out of process approach.
    '''
    title = gui.current_db.title(book_id, index_is_id=True)
    job = ThreadedJob('k2pdfopt plugin',
            _('Convert PDF for book: {}'.format(title)),
            convert_threaded, (book_id, title, conversion_settings, path_to_input_format, path_to_output_format), {}, callback)
    gui.job_manager.run_threaded_job(job)
    gui.status_bar.show_message(_('Convert PDF started'), 3000)


def convert_threaded(book_id, title, conversion_settings, path_to_input_format, path_to_output_format, log=None, abort=None, notifications=None):
    '''
    In combination with start_convert this function performs
    the scan of the book(s) from a separate thread.
    '''
    res = False
    try:
        res = convert_book(conversion_settings, path_to_input_format, path_to_output_format, log, abort, notifications=notifications)
    except Exception as e:
        import traceback
        traceback.print_exc()
        log.error('Exception when converting pdf:', e)
        pass
    if res:
        log.warn('  Book converted successfuly: {}'.format(title))
    else:
        log.error('  Failed to convert book')
    return (book_id, path_to_input_format, path_to_output_format)


