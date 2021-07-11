# Copyright Mirage authors & contributors <https://github.com/mirukana/mirage>
# SPDX-License-Identifier: LGPL-3.0-or-later

from PySide6.QtCore import Property, QObject

from .. import __version__

# from .user_files import Accounts, History, Settings, Theme, UIState


class Backend(QObject):
    def __init__(self):
        QObject.__init__(self)

        # self._saved_accounts: Accounts = Accounts(self)
        # self._settings:       Settings = Settings(self)
        # self._ui_state:       UIState  = UIState(self)
        # self._history:        History  = History(self)
        # self._theme:          Theme    = Theme(
        #     self, self._settings.General.theme,
        # )

        # print(self._settings)

    # saved_accounts = Property(
    #     "QVariant", lambda self: self._saved_accounts.qml_data,
    # )
    # settings = Property(
    #     "QVariant", lambda self: self._settings.qml_data,
    # )

    # theme = Property(
    #     "QVariant", lambda self: self._theme.qml_data,
    # )

    def get_version(self):
        return __version__

    version = Property(str, get_version)
