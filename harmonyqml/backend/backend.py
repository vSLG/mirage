# Copyright 2019 miruka
# This file is part of harmonyqml, licensed under GPLv3.

import hashlib
from typing import Dict

from PyQt5.QtCore import QObject, pyqtProperty, pyqtSlot

from .client_manager import ClientManager
from .model.items import User
from .model.qml_models import QMLModels


class Backend(QObject):
    def __init__(self) -> None:
        super().__init__()
        self._client_manager: ClientManager = ClientManager()
        self._models:         QMLModels     = QMLModels()

        from .signal_manager import SignalManager
        self._signal_manager: SignalManager = SignalManager(self)

        # a = self._client_manager; m = self._models
        # from PyQt5.QtCore import pyqtRemoveInputHook as PRI
        # import pdb; PRI(); pdb.set_trace()

        self.clientManager.configLoad()


    @pyqtProperty("QVariant", constant=True)
    def clientManager(self):
        return self._client_manager


    @pyqtProperty("QVariant", constant=True)
    def models(self):
        return self._models


    @pyqtSlot(str, result="QVariantMap")
    def getUser(self, user_id: str) -> Dict[str, str]:
        for client in self.clientManager.clients.values():
            for room in client.nio.rooms.values():

                name = room.user_name(user_id)
                if name:
                    return User(user_id=user_id, display_name=name)._asdict()

        return User(user_id=user_id, display_name=user_id)._asdict()


    @pyqtSlot(str, result=float)
    def hueFromString(self, string: str) -> float:
      # pylint:disable=no-self-use
        md5 = hashlib.md5(bytes(string, "utf-8")).hexdigest()
        return float("0.%s" % int(md5[-10:], 16))
