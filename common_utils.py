#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com>, 2024 additions by Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

import os
from threading import Thread
from functools import partial
import copy

from six.moves import range

try:
    from qt.core import (
        QApplication, Qt, QIcon, QPixmap, QLabel, QDialog, QHBoxLayout,
        QVBoxLayout, QFont, QLineEdit, QComboBox, QProgressBar,
        QDialogButtonBox, QTextEdit, QSize, QFileDialog,
        QListWidget, QAbstractItemView, QTextBrowser, pyqtSignal)
except ImportError:
    from PyQt5.Qt import (
        QApplication, Qt, QIcon, QPixmap, QLabel, QDialog, QHBoxLayout,
        QVBoxLayout, QFont, QLineEdit, QComboBox, QProgressBar,
        QDialogButtonBox, QTextEdit, QSize, QFileDialog,
        QListWidget, QAbstractItemView, QTextBrowser, pyqtSignal)

from calibre import prints
from calibre.constants import DEBUG, iswindows
from calibre.constants import numeric_version as calibre_version
from calibre.gui2 import (gprefs, error_dialog, info_dialog,
                          choose_files, FileDialog)
from calibre.gui2.actions import menu_action_unique_name
from calibre.gui2.complete2 import EditWithComplete 
from calibre.gui2.keyboard import ShortcutConfig
from calibre.gui2.widgets import EnLineEdit
from calibre.utils.config import config_dir, tweaks
from calibre.utils.date import now

try:
    load_translations()
except NameError:
    prints("k2pdfopt_plugin::common_utils.py - exception when loading translations")

# Global definition of our plugin name. Used for common functions that require this.
plugin_name = None
# Global definition of our plugin resources. Used to share between the xxxAction and xxxBase
# classes if you need any zip images to be displayed on the configuration dialog.
plugin_icon_resources = {}


def set_plugin_icon_resources(name, resources):
    '''
    Set our global store of plugin name and icon resources for sharing between
    the InterfaceAction class which reads them and the ConfigWidget
    if needed for use on the customization dialog for this plugin.
    '''
    global plugin_icon_resources, plugin_name
    plugin_name = name
    plugin_icon_resources = resources


def get_icon_6_2_plus(icon_name):
    '''
    Retrieve a QIcon for the named image from
    1. Calibre's image cache
    2. resources/images
    3. the icon theme
    4. the plugin zip
    Only plugin zip has images/ in the image name for backward
    compatibility.
    '''
    icon = None
    if icon_name:
        icon = QIcon.ic(icon_name)
        ## both .ic and get_icons return an empty QIcon if not found.
        if not icon or icon.isNull():
            icon = get_icons(icon_name.replace('images/',''), plugin_name,
                             print_tracebacks_for_missing_resources=False)
        if not icon or icon.isNull():
            icon = get_icons(icon_name, plugin_name,
                             print_tracebacks_for_missing_resources=False)
    if not icon:
        icon = QIcon()
    return icon

def get_icon_old(icon_name):
    '''
    Retrieve a QIcon for the named image from the zip file if it exists,
    or if not then from Calibre's image cache.
    '''
    if icon_name:
        pixmap = get_pixmap(icon_name)
        if pixmap is None:
            # Look in Calibre's cache for the icon
            return QIcon(I(icon_name))
        else:
            return QIcon(pixmap)
    return QIcon()

if calibre_version >= (6,2,0):
    get_icon = get_icon_6_2_plus
else:
    get_icon = get_icon_old


def get_pixmap(icon_name):
    '''
    Retrieve a QPixmap for the named image
    Any icons belonging to the plugin must be prefixed with 'images/'
    '''
    global plugin_icon_resources, plugin_name

    if not icon_name.startswith('images/'):
        # We know this is definitely not an icon belonging to this plugin
        pixmap = QPixmap()
        pixmap.load(I(icon_name))
        return pixmap

    # Check to see whether the icon exists as a Calibre resource
    # This will enable skinning if the user stores icons within a folder like:
    # ...\AppData\Roaming\calibre\resources\images\Plugin Name\
    if plugin_name:
        local_images_dir = get_local_images_dir(plugin_name)
        local_image_path = os.path.join(local_images_dir, icon_name.replace('images/', ''))
        if os.path.exists(local_image_path):
            pixmap = QPixmap()
            pixmap.load(local_image_path)
            return pixmap

    # As we did not find an icon elsewhere, look within our zip resources
    if icon_name in plugin_icon_resources:
        pixmap = QPixmap()
        pixmap.loadFromData(plugin_icon_resources[icon_name])
        return pixmap
    return None


def get_local_images_dir(subfolder=None):
    '''
    Returns a path to the user's local resources/images folder
    If a subfolder name parameter is specified, appends this to the path
    '''
    images_dir = os.path.join(config_dir, 'resources/images')
    if subfolder:
        images_dir = os.path.join(images_dir, subfolder)
    if iswindows:
        images_dir = os.path.normpath(images_dir)
    return images_dir

def create_menu_action_unique(ia, parent_menu, menu_text, image=None, tooltip=None,
                       shortcut=None, triggered=None, is_checked=None, shortcut_name=None,
                       unique_name=None, favourites_menu_unique_name=None):
    '''
    Create a menu action with the specified criteria and action, using the new
    InterfaceAction.create_menu_action() function which ensures that regardless of
    whether a shortcut is specified it will appear in Preferences->Keyboard
    '''
    orig_shortcut = shortcut
    kb = ia.gui.keyboard
    if unique_name is None:
        unique_name = menu_text
    if not shortcut == False:
        full_unique_name = menu_action_unique_name(ia, unique_name)
        if full_unique_name in kb.shortcuts:
            shortcut = False
        else:
            if shortcut is not None and not shortcut == False:
                if len(shortcut) == 0:
                    shortcut = None
                else:
                    shortcut = _(shortcut)

    if shortcut_name is None:
        shortcut_name = menu_text.replace('&','')

    ac = ia.create_menu_action(parent_menu, unique_name, menu_text, icon=None, shortcut=shortcut,
        description=tooltip, triggered=triggered, shortcut_name=shortcut_name)
    if shortcut == False and not orig_shortcut == False:
        if ac.calibre_shortcut_unique_name in ia.gui.keyboard.shortcuts:
            kb.replace_action(ac.calibre_shortcut_unique_name, ac)
    if image:
        ac.setIcon(get_icon(image))
    if is_checked is not None:
        ac.setCheckable(True)
        if is_checked:
            ac.setChecked(True)
    # For use by the Favourites Menu plugin. If this menu action has text
    # that is not constant through the life of this plugin, then we need
    # to attribute it with something that will be constant that the
    # Favourites Menu plugin can use to identify it.
    if favourites_menu_unique_name:
        ac.favourites_menu_unique_name = favourites_menu_unique_name
    return ac

def prompt_for_restart(parent, title, message):
    d = info_dialog(parent, title, message, show_copy_button=False)
    b = d.bb.addButton(_('Restart calibre now'), d.bb.AcceptRole)
    b.setIcon(QIcon(I('lt.png')))
    d.do_restart = False
    def rf():
        d.do_restart = True
    b.clicked.connect(rf)
    d.set_details('')
    d.exec_()
    b.clicked.disconnect()
    return d.do_restart

class SizePersistedDialog(QDialog):
    '''
    This dialog is a base class for any dialogs that want their size/position
    restored when they are next opened.
    '''
    def __init__(self, parent, unique_pref_name):
        QDialog.__init__(self, parent)
        self.unique_pref_name = unique_pref_name
        self.geom = gprefs.get(unique_pref_name, None)
        self.finished.connect(self.dialog_closing)

    def resize_dialog(self):
        if self.geom is None:
            self.resize(self.sizeHint())
        else:
            self.restoreGeometry(self.geom)

    def dialog_closing(self, result):
        geom = bytearray(self.saveGeometry())
        gprefs[self.unique_pref_name] = geom
        self.persist_custom_prefs()

    def persist_custom_prefs(self):
        '''
        Invoked when the dialog is closing. Override this function to call
        save_custom_pref() if you have a setting you want persisted that you can
        retrieve in your __init__() using load_custom_pref() when next opened
        '''
        pass

    def load_custom_pref(self, name, default=None):
        return gprefs.get(self.unique_pref_name+':'+name, default)

    def save_custom_pref(self, name, value):
        gprefs[self.unique_pref_name+':'+name] = value

class NoWheelComboBox(QComboBox):

    def wheelEvent (self, event):
        # Disable the mouse wheel on top of the combo box changing selection as plays havoc in a grid
        event.ignore()

class ReorderedComboBox(QComboBox):

    def __init__(self, parent, strip_items=True):
        QComboBox.__init__(self, parent)
        self.strip_items = strip_items
        self.setEditable(True)
        self.setMaxCount(10)
        self.setInsertPolicy(QComboBox.InsertAtTop)

    def populate_items(self, items, sel_item):
        self.blockSignals(True)
        self.clear()
        self.clearEditText()
        for text in items:
            if text != sel_item:
                self.addItem(text)
        if sel_item:
            self.insertItem(0, sel_item)
            self.setCurrentIndex(0)
        else:
            self.setEditText('')
        self.blockSignals(False)

    def reorder_items(self):
        self.blockSignals(True)
        text = str(self.currentText())
        if self.strip_items:
            text = text.strip()
        if not text.strip():
            return
        existing_index = self.findText(text, Qt.MatchExactly)
        if existing_index:
            self.removeItem(existing_index)
            self.insertItem(0, text)
            self.setCurrentIndex(0)
        self.blockSignals(False)

    def get_items_list(self):
        if self.strip_items:
            return [str(self.itemText(i)).strip() for i in range(0, self.count())]
        else:
            return [str(self.itemText(i)) for i in range(0, self.count())]

class DragDropLineEdit(QLineEdit):
    '''
    Unfortunately there is a flaw in the Qt implementation which means that
    when the QComboBox is in editable mode that dropEvent is not fired
    if you drag into the editable text area. Working around this by having
    a custom LineEdit() set for the parent combobox.
    '''
    def __init__(self, parent, drop_mode):
        QLineEdit.__init__(self, parent)
        self.drop_mode = drop_mode
        self.setAcceptDrops(True)

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dragEnterEvent(self, event):
        if int(event.possibleActions() & Qt.CopyAction) + \
           int(event.possibleActions() & Qt.MoveAction) == 0:
            return
        data = self._get_data_from_event(event)
        if data:
            event.acceptProposedAction()

    def dropEvent(self, event):
        data = self._get_data_from_event(event)
        event.setDropAction(Qt.CopyAction)
        self.setText(data[0])

    def _get_data_from_event(self, event):
        md = event.mimeData()
        if self.drop_mode == 'file':
            urls, filenames = dnd_get_files(md, ['csv', 'txt'])
            if not urls:
                # Nothing found
                return
            if not filenames:
                # Local files
                return urls
            else:
                # Remote files
                return filenames
        if event.mimeData().hasFormat('text/uri-list'):
            urls = [str(u.toString()).strip() for u in md.urls()]
            return urls

class DragDropComboBox(ReorderedComboBox):
    '''
    Unfortunately there is a flaw in the Qt implementation which means that
    when the QComboBox is in editable mode that dropEvent is not fired
    if you drag into the editable text area. Working around this by having
    a custom LineEdit() set for the parent combobox.
    '''
    def __init__(self, parent, drop_mode='url'):
        ReorderedComboBox.__init__(self, parent)
        self.drop_line_edit = DragDropLineEdit(parent, drop_mode)
        self.setLineEdit(self.drop_line_edit)
        self.setAcceptDrops(True)
        self.setEditable(True)
        self.setMaxCount(10)
        self.setInsertPolicy(QComboBox.InsertAtTop)

    def dragMoveEvent(self, event):
        self.lineEdit().dragMoveEvent(event)

    def dragEnterEvent(self, event):
        self.lineEdit().dragEnterEvent(event)

    def dropEvent(self, event):
        self.lineEdit().dropEvent(event)

class KeyboardConfigDialog(SizePersistedDialog):
    '''
    This dialog is used to allow editing of keyboard shortcuts.
    '''
    def __init__(self, gui, group_name):
        SizePersistedDialog.__init__(self, gui, _('Keyboard shortcut dialog'))
        self.gui = gui
        self.setWindowTitle(_('Keyboard shortcuts'))
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.keyboard_widget = ShortcutConfig(self)
        layout.addWidget(self.keyboard_widget)
        self.group_name = group_name

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.commit)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()
        self.initialize()

    def initialize(self):
        self.keyboard_widget.initialize(self.gui.keyboard)
        self.keyboard_widget.highlight_group(self.group_name)

    def commit(self):
        self.keyboard_widget.commit()
        self.accept()

class ViewLog(QDialog):

    def __init__(self, title, html, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)

        self.tb = QTextBrowser(self)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        # Rather than formatting the text in <pre> blocks like the calibre
        # ViewLog does, instead just format it inside divs to keep style formatting
        html = html.replace('\t','&nbsp;&nbsp;&nbsp;&nbsp;').replace('\n', '<br/>')
        html = html.replace('> ','>&nbsp;')
        self.tb.setHtml('<div>%s</div>' % html)
        QApplication.restoreOverrideCursor()
        l.addWidget(self.tb)

        self.bb = QDialogButtonBox(QDialogButtonBox.Ok)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        self.copy_button = self.bb.addButton(_('Copy to clipboard'),
                self.bb.ActionRole)
        #self.copy_button.setIcon(QIcon(I('edit-copy.png')))
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        l.addWidget(self.bb)
        self.setModal(False)
        self.resize(QSize(700, 500))
        self.setWindowTitle(title)
        #self.setWindowIcon(QIcon(I('debug.png')))
        self.show()

    def copy_to_clipboard(self):
        txt = self.tb.toPlainText()
        QApplication.clipboard().setText(txt)

def prompt_for_restart(parent, title, message):
    d = info_dialog(parent, title, message, show_copy_button=False)
    b = d.bb.addButton(_('Restart calibre now'), d.bb.AcceptRole)
    b.setIcon(QIcon(I('lt.png')))
    d.do_restart = False
    def rf():
        d.do_restart = True
    b.clicked.connect(rf)
    d.set_details('')
    d.exec_()
    b.clicked.disconnect()
    return d.do_restart

class PrefsViewerDialog(SizePersistedDialog):

    def __init__(self, gui, namespace):
        SizePersistedDialog.__init__(self, gui, _('Prefs Viewer dialog'))
        self.setWindowTitle('Preferences for: '+namespace)

        self.gui = gui
        self.db = gui.current_db
        self.namespace = namespace
        self._init_controls()
        self.resize_dialog()

        self._populate_settings()

        if self.keys_list.count():
            self.keys_list.setCurrentRow(0)

    def _init_controls(self):
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        ml = QHBoxLayout()
        layout.addLayout(ml, 1)

        self.keys_list = QListWidget(self)
        self.keys_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.keys_list.setFixedWidth(150)
        self.keys_list.setAlternatingRowColors(True)
        ml.addWidget(self.keys_list)
        self.value_text = QTextEdit(self)
        self.value_text.setTabStopDistance(24)
        self.value_text.setReadOnly(False)
        ml.addWidget(self.value_text, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._apply_changes)
        button_box.rejected.connect(self.reject)
        self.clear_button = button_box.addButton(_('Clear'), QDialogButtonBox.ResetRole)
        self.clear_button.setIcon(get_icon('trash.png'))
        self.clear_button.setToolTip(_('Clear all settings for this plugin'))
        self.clear_button.clicked.connect(self._clear_settings)
        layout.addWidget(button_box)

    def _populate_settings(self):
        self.keys_list.clear()
        ns_prefix = self._get_ns_prefix()
        keys = sorted([k[len(ns_prefix):] for k in list(self.db.prefs.keys())
                       if k.startswith(ns_prefix)])
        for key in keys:
            self.keys_list.addItem(key)
        self.keys_list.setMinimumWidth(self.keys_list.sizeHintForColumn(0))
        self.keys_list.currentRowChanged[int].connect(self._current_row_changed)

    def _current_row_changed(self, new_row):
        if new_row < 0:
            self.value_text.clear()
            return
        key = str(self.keys_list.currentItem().text())
        val = self.db.prefs.get_namespaced(self.namespace, key, '')
        self.value_text.setPlainText(self.db.prefs.to_raw(val))

    def _get_ns_prefix(self):
        return 'namespaced:%s:'% self.namespace

    def _apply_changes(self):
        from calibre.gui2.dialogs.confirm_delete import confirm
        message = _('<p>Are you sure you want to change your settings in this library for this plugin?</p>' \
                  '<p>Any settings in other libraries or stored in a JSON file in your calibre plugins ' \
                  'folder will not be touched.</p>' \
                  '<p>You must restart calibre afterwards.</p>')
        if not confirm(message, self.namespace+'_clear_settings', self):
            return

        val = self.db.prefs.raw_to_object(str(self.value_text.toPlainText()))
        key = str(self.keys_list.currentItem().text())
        self.db.prefs.set_namespaced(self.namespace, key, val)

        restart = prompt_for_restart(self, _('Settings changed'),
                           _('<p>Settings for this plugin in this library have been changed.</p>'
                           '<p>Please restart calibre now.</p>'))
        self.close()
        if restart:
            self.gui.quit(restart=True)

    def _clear_settings(self):
        from calibre.gui2.dialogs.confirm_delete import confirm
        message = _('<p>Are you sure you want to clear your settings in this library for this plugin?</p>' \
                  '<p>Any settings in other libraries or stored in a JSON file in your calibre plugins ' \
                  'folder will not be touched.</p>' \
                  '<p>You must restart calibre afterwards.</p>')
        if not confirm(message, self.namespace+'_clear_settings', self):
            return

        ns_prefix = self._get_ns_prefix()
        keys = [k for k in list(self.db.prefs.keys()) if k.startswith(ns_prefix)]
        for k in keys:
            del self.db.prefs[k]
        self._populate_settings()
        restart = prompt_for_restart(self, _('Settings deleted'),
                           _('<p>All settings for this plugin in this library have been cleared.</p>'
                           '<p>Please restart calibre now.</p>'))
        self.close()
        if restart:
            self.gui.quit(restart=True)

def load_resources(plugin_name, names):
    '''
    If this plugin comes in a ZIP file (user added plugin), this method
    will allow you to load resources from the ZIP file.

    For example to load an image::

        pixmap = QPixmap()
        pixmap.loadFromData(tuple(self.load_resources(['images/icon.png']).values())[0])
        icon = QIcon(pixmap)

    :param names: List of paths to resources in the ZIP file using / as separator

    :return: A dictionary of the form ``{name : file_contents}``. Any names
                that were not found in the ZIP file will not be present in the
                dictionary.

    '''
    from zipfile import ZipFile
    from calibre.utils.config import config_dir

    plugin_path = os.path.join(config_dir, 'plugins/{}.zip'.format(plugin_name))
    if plugin_path is None:
        raise ValueError('This plugin was not loaded from a ZIP file')
    ans = {}
    with ZipFile(plugin_path, 'r') as zf:
        for candidate in zf.namelist():
            if candidate in names:
                ans[candidate] = zf.read(candidate)
    return ans

def to_hex(string):
    try:
        # python3
        hex_ = string.encode('utf-8').hex()
    except:
        # python 2
        hex_ = ''.join(x.encode('hex') for x in string)
    return hex_

def get_library_hex_id(db):
    library_id = getattr(db.new_api, 'server_library_id', None)
    if not library_id:
        library_hex_id = None
    else:
        #library_hex_id = '_hex_-' + library_id.encode('utf-8').hex()
        library_hex_id = '_hex_-' + to_hex(library_id)
    return library_hex_id

class NullContext(object):

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return None

    def __exit__(self, *args):
        pass
