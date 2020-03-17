// SPDX-License-Identifier: LGPL-3.0-or-later

import QtQuick 2.12
import "../../../Base"
import "../../.."

MultiviewPane {
    id: roomPane
    saveName: "roomPane"
    edge: Qt.RightEdge

    buttonsBackgroundColor: theme.chat.roomPane.topBar.background
    background: Rectangle { color: theme.chat.roomPane.background }


    buttonRepeater.model: [
        "members", "files", "notifications", "history", "settings"
    ]

    buttonRepeater.delegate: HButton {
        height: theme.baseElementsHeight
        backgroundColor: "transparent"
        icon.name: "room-view-" + modelData
        toolTip.text: qsTr(
            modelData.charAt(0).toUpperCase() + modelData.slice(1)
        )

        autoExclusive: true
        checked: swipeView.currentIndex === 0 && index === 0 ||
                 swipeView.currentIndex === 1 && index === 4

        enabled: ["members", "settings"].includes(modelData)

        onClicked: swipeView.currentIndex = Math.min(index, 1)
    }


    function toggleFocus() {
        if (swipeView.currentItem.keybindFocusItem.activeFocus) {
            if (roomPane.collapse) roomPane.close()
            pageLoader.takeFocus()
            return
        }

        roomPane.open()
        swipeView.currentItem.keybindFocusItem.forceActiveFocus()
    }


    Connections {
        target: swipeView

        onCurrentItemChanged:
            swipeView.currentItem.keybindFocusItem.forceActiveFocus()
    }

    MemberView {}
    SettingsView { fillAvailableHeight: true }
}
