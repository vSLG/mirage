// SPDX-License-Identifier: LGPL-3.0-or-later

import QtQuick 2.12
import SortFilterProxyModel 0.2
import ".."
import "../Base"

HListView {
    id: mainPaneList
    model: ModelStore.get("accounts")

    delegate: AccountRoomsDelegate {
        width: mainPaneList.width
        height: childrenRect.height
    }

    highlightFollowsCurrentItem: false
    currentItemHeight:
        selectedRoom ? selectedRoom.height :
        currentItem ? currentItem.account.height : 0

    highlight: Rectangle {
        y:
            selectedRoom ?
            currentItem.y + currentItem.account.height +
            currentItem.roomList.currentItem.y :
            currentItem.y

        width: mainPaneList.width
        height:
            selectedRoom ?
            currentItem.roomList.currentItem.height :
            currentItem.account.height

        color: theme.controls.listView.highlight

        Behavior on y { HNumberAnimation {} }
        Behavior on height { HNumberAnimation {} }
    }


    readonly property Room selectedRoom:
        currentItem ? currentItem.roomList.currentItem : null


    function previous(activate=true) {
        let currentAccount = currentItem

        // Nothing is selected
        if (! currentAccount) {
            decrementCurrentIndex()
            return
        }

        let roomList = currentAccount.roomList

        // An account is selected
        if (! roomList.currentItem) {
            decrementCurrentIndex()
            // Select the last room of the previous account that's now selected
            currentItem.roomList.decrementCurrentIndex()
            return
        }

        // A room is selected
        const selectedIsFirst = roomList.currentIndex === 0
        const noRooms         = roomList.count === 0

        if (currentAccount.collapsed || selectedIsFirst || noRooms) {
            // Have the account itself be selected
            roomList.currentIndex = -1
        } else {
            roomList.decrementCurrentIndex()
        }
    }

    function next(activate=true) {
        const currentAccount = currentItem

        // Nothing is selected
        if (! currentAccount) {
            incrementCurrentIndex()
            return
        }

        const roomList = currentAccount.roomList

        // An account is selected
        if (! roomList.currentItem) {
            if (currentAccount.collapsed || roomList.count === 0) {
                incrementCurrentIndex()
            } else {
                roomList.incrementCurrentIndex()
            }
            return
        }

        // A room is selected
        const selectedIsLast = roomList.currentIndex >= roomList.count - 1
        const noRooms        = roomList.count === 0

        if (currentAccount.collapsed || selectedIsLast || noRooms) {
            roomList.currentIndex = -1
            mainPaneList.incrementCurrentIndex()
        } else {
            roomList.incrementCurrentIndex()
        }
    }

    function activate() {
        currentItem.item.activated()
    }

    function accountSettings() {
        if (! currentItem) incrementCurrentIndex()
        currentItem.roomList.currentIndex = -1
        currentItem.account.activated()
    }

    function addNewChat() {
        if (! currentItem) incrementCurrentIndex()
        currentItem.roomList.currentIndex = -1
        currentItem.account.activated()
    }

    function toggleCollapseAccount() {
        if (mainPane.filter) return
        if (! currentItem) incrementCurrentIndex()
        currentItem.account.toggleCollapse()
    }


    Timer {
        id: activateLimiter
        interval: 300
        onTriggered: activate()
    }
}
