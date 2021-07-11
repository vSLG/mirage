// Copyright Mirage authors & contributors <https://github.com/mirukana/mirage>
// SPDX-License-Identifier: LGPL-3.0-or-later

import QtQuick
import QtQuick.Controls

import Backend

/* import "Base" */

ApplicationWindow {
    id: window

    visible: true
    width: Math.min(screen.width, 1152)
    height: Math.min(screen.height, 768)
    color: "transparent"

    Component.onCompleted: {
        print(`Mirage version: ${Backend.version}`)
    }

    /* HLoader { */
    /*     anchors.fill: parent */
    /*     source: "LoadingScreen.qml" */
    /* } */
}
