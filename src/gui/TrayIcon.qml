// Copyright Mirage authors & contributors <https://github.com/mirukana/mirage>
// SPDX-License-Identifier: LGPL-3.0-or-later

import QtQuick 2.12
import QtQuick.Controls 2.12
import Qt.labs.platform 1.1
import Qt.labs.folderlistmodel 2.12

Item {
    property ApplicationWindow window
    property alias settingsFolder: showUpWatcher.folder

    SystemTrayIcon {
        property string iconPack: theme ? theme.icons.preferredPack : "thin"

        visible: true
        tooltip: Qt.application.displayName
        icon.source: `../icons/${iconPack}/tray-icon.png`

        onActivated: {
            if (reason === SystemTrayIcon.MiddleClick)
                Qt.quit()
            else if (reason !== SystemTrayIcon.Context)
                window.visible ? window.hide() : window.restoreFromTray()
        }

        menu: Menu {
            MenuItem {
                text:
                    window.visible ?
                    "Minimize to tray" :
                    qsTr("Open %1").arg(Qt.application.displayName)
                onTriggered:
                    window.visible ?
                    window.hide() :
                    window.restoreFromTray()
            }

            MenuItem {
                text: qsTr("Quit %1").arg(Qt.application.displayName)
                onTriggered: Qt.quit()
            }
        }
    }

    FolderListModel {
        id: showUpWatcher
        showDirs: false
        showHidden: true
        nameFilters: [".show"]

        onCountChanged: {
            if (count) {
                window.restoreFromTray()
                py.importModule("os", () => {
                    py.call("os.remove", [get(0, "filePath")])
                })
            }
        }
    }
}
