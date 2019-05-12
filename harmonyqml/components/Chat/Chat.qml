import QtQuick 2.7
import QtQuick.Layouts 1.3
import "../Base"
import "Banners"
import "RoomEventList"
import "RoomSidePane"

HColumnLayout {
    property string userId: ""
    property string category: ""
    property string roomId: ""

    readonly property var roomInfo:
        Backend.accounts.get(userId)
               .roomCategories.get(category)
               .rooms.get(roomId)

    readonly property var sender: Backend.users.get(userId)

    readonly property bool hasUnknownDevices:
         category == "Rooms" ?
         Backend.clients.get(userId).roomHasUnknownDevices(roomId) : false

    id: chatPage
    onFocusChanged: sendBox.setFocus()

   Component.onCompleted: Backend.signals.roomCategoryChanged.connect(
        function(forUserId, forRoomId, previous, now) {
            if (chatPage && forUserId == userId && forRoomId == roomId) {
                chatPage.category = now
            }
        }
    )

    RoomHeader {
        id: roomHeader
        displayName: roomInfo.displayName
        topic: roomInfo.topic || ""

        Layout.fillWidth: true
        Layout.preferredHeight: 32
    }


    HSplitView {
        Layout.fillWidth: true
        Layout.fillHeight: true

        HColumnLayout {
            Layout.fillWidth: true

            RoomEventList {
                Layout.fillWidth: true
                Layout.fillHeight: true
            }

            TypingMembersBar {}

            InviteBanner {
                visible: category === "Invites"
                inviter: roomInfo.inviter
            }

            UnknownDevicesBanner {
                visible: category == "Rooms" && hasUnknownDevices
            }

            SendBox {
                id: sendBox
                visible: category == "Rooms" && ! hasUnknownDevices
            }

            LeftBanner {
                visible: category === "Left"
                leftEvent: roomInfo.leftEvent
            }
        }

        RoomSidePane {
            id: roomSidePane

            property int referenceWidth: roomHeader.buttonsWidth
            onReferenceWidthChanged: width = referenceWidth

            Layout.minimumWidth: 36
            Layout.maximumWidth: parent.width
        }
    }
}
