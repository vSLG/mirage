// SPDX-License-Identifier: LGPL-3.0-or-later

import QtQuick 2.12
import QtQuick.Layouts 1.12
import ".."

HButton {
    text: qsTr("Cancel")
    icon.name: "cancel"
    icon.color: theme.colors.negativeBackground

    Layout.preferredHeight: theme.baseElementsHeight
    Layout.fillWidth: true
}