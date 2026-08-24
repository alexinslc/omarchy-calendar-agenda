import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "AgendaModel.js" as AgendaModel

Panel {
    id: root
    moduleName: "io.github.alexinslc.calendar-agenda"
    ipcTarget: "io.github.alexinslc.calendar-agenda"
    manageIpc: false

    property var anchorItem: null
    property var hostWidget: null
    property date anchorDate: new Date()
    property string viewMode: "day"
    property var events: []
    property var groups: []
    property string dataState: "loading"
    property string dataMessage: "Loading calendar data..."
    readonly property string cachePath: Quickshell.env("HOME") + "/.local/state/omarchy/calendar-agenda/events.json"

    readonly property color contentForeground: bar ? bar.foreground : Color.foreground
    readonly property color contentBackground: Color.background
    readonly property color mutedForeground: Qt.rgba(contentForeground.r, contentForeground.g, contentForeground.b, 0.58)
    readonly property color accentForeground: Color.accent
    readonly property string title: AgendaModel.viewTitle(viewMode, anchorDate)

    function loadEvents(text, fromCache) {
        var data
        try {
            data = JSON.parse(text)
        } catch (error) {
            console.error(
                fromCache ? "calendar cache contains invalid JSON:" : "calendar fixture contains invalid JSON:",
                error.message
            )
            if (fromCache) {
                root.dataState = "error"
                root.dataMessage = "Calendar data is unavailable."
            }
            return
        }
        root.events = AgendaModel.parseEvents(data)
        root.dataState = fromCache ? "ready" : "fixture"
        root.dataMessage = fromCache ? "" : "Using development fixture data."
        rebuild()
    }

    function rebuild() {
        root.groups = AgendaModel.groupedEvents(root.events, root.viewMode, root.anchorDate)
    }

    function setMode(mode) {
        root.viewMode = mode
        root.rebuild()
    }

    function move(direction) {
        root.anchorDate = AgendaModel.moveAnchor(root.anchorDate, root.viewMode, direction)
        root.rebuild()
    }

    function goToToday() {
        root.anchorDate = new Date()
        root.viewMode = "day"
        root.rebuild()
    }

    function open() {
        cacheFile.reload()
        root.controller.show()
    }

    function close() {
        root.controller.hide()
    }

    function toggle() {
        if (root.opened) root.close()
        else root.open()
    }

    FileView {
        id: fixtureFile
        path: Qt.resolvedUrl("fixtures/events.json")
        onLoaded: {
            if (root.dataState !== "error" && root.dataState !== "ready")
                root.loadEvents(text(), false)
        }
    }

    FileView {
        id: cacheFile
        path: root.cachePath
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.loadEvents(text(), true)
        onLoadFailed: {
            if (root.dataState !== "ready") {
                root.dataState = "fixture"
                root.dataMessage = "Using development fixture data."
            }
        }
    }

    Timer {
        interval: 60000
        running: true
        repeat: true
        onTriggered: cacheFile.reload()
    }

    KeyboardPanel {
        id: panel
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        bar: root.bar
        open: root.opened
        focusTarget: keyCatcher
        contentWidth: Style.space(420)
        contentHeight: Style.space(520)

        PanelKeyCatcher {
            id: keyCatcher
            anchors.fill: parent
            onMoveRequested: function(dx, dy) {
                if (dx !== 0) root.move(dx)
                if (dy !== 0) root.move(dy)
            }
            onActivateRequested: root.goToToday()
            onCloseRequested: root.close()
            onTextKey: function(text) {
                if (text === "[" || text === "{") root.move(-1)
                else if (text === "]" || text === "}") root.move(1)
                else if (text === "t" || text === "T") root.goToToday()
                else if (text === "d" || text === "D") root.setMode("day")
                else if (text === "w" || text === "W") root.setMode("week")
                else if (text === "m" || text === "M") root.setMode("month")
            }

            Column {
                id: agendaColumn
                anchors.fill: parent
                anchors.margins: Style.space(16)
                spacing: Style.space(10)

                Row {
                    width: parent.width
                    spacing: Style.space(8)

                    Text {
                        text: "󰃭"
                        color: root.accentForeground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body * 1.4
                    }

                    Text {
                        text: "CALENDAR AGENDA"
                        color: root.contentForeground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.bodySmall
                        font.bold: true
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                Row {
                    width: parent.width
                    spacing: Style.space(5)

                    Repeater {
                        model: ["day", "week", "month"]

                        Rectangle {
                            required property string modelData
                            width: (parent.width - Style.space(10)) / 3
                            height: Style.space(28)
                            radius: Style.cornerRadius
                            color: root.viewMode === modelData
                                ? Qt.rgba(root.accentForeground.r, root.accentForeground.g, root.accentForeground.b, 0.22)
                                : Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.08)

                            Text {
                                anchors.centerIn: parent
                                text: modelData.toUpperCase()
                                color: root.viewMode === modelData ? root.accentForeground : root.mutedForeground
                                font.family: Style.font.family
                                font.pixelSize: Style.font.bodySmall
                                font.bold: true
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.setMode(parent.modelData)
                            }
                        }
                    }
                }

                Row {
                    width: parent.width
                    height: Style.space(30)

                    Text {
                        text: "‹"
                        width: Style.space(30)
                        color: root.contentForeground
                        font.pixelSize: Style.font.body * 1.6
                        horizontalAlignment: Text.AlignHCenter
                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.move(-1)
                        }
                    }

                    Text {
                        text: root.title
                        width: parent.width - Style.space(60)
                        color: root.contentForeground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    Text {
                        text: "›"
                        width: Style.space(30)
                        color: root.contentForeground
                        font.pixelSize: Style.font.body * 1.6
                        horizontalAlignment: Text.AlignHCenter
                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.move(1)
                        }
                    }
                }

                Text {
                    visible: root.dataState !== "ready" && root.dataMessage !== ""
                    width: parent.width
                    text: root.dataMessage
                    color: root.dataState === "error" ? root.accentForeground : root.mutedForeground
                    font.family: Style.font.family
                    font.pixelSize: Style.font.bodySmall
                    wrapMode: Text.Wrap
                }

                Flickable {
                    width: parent.width
                    height: Math.max(0, parent.height - y)
                    contentWidth: width
                    contentHeight: eventGroups.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    Column {
                        id: eventGroups
                        width: parent.width
                        spacing: Style.space(12)

                        Repeater {
                            model: root.groups

                            Column {
                                required property var modelData
                                width: parent.width
                                spacing: Style.space(5)

                                Text {
                                    text: modelData.label
                                    color: root.accentForeground
                                    font.family: Style.font.family
                                    font.pixelSize: Style.font.bodySmall
                                    font.bold: true
                                    font.letterSpacing: 1
                                }

                                Repeater {
                                    model: modelData.events

                                    Rectangle {
                                        required property var modelData
                                        width: parent.width
                                        height: eventText.implicitHeight + Style.space(10)
                                        radius: Style.cornerRadius
                                        color: Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.07)

                                        Row {
                                            anchors.fill: parent
                                            anchors.margins: Style.space(7)
                                            spacing: Style.space(9)

                                            Text {
                                                width: Style.space(58)
                                                text: modelData.timeLabel
                                                color: modelData.allDay ? root.accentForeground : root.mutedForeground
                                                font.family: Style.font.family
                                                font.pixelSize: Style.font.bodySmall
                                                font.bold: modelData.allDay
                                            }

                                            Text {
                                                id: eventText
                                                width: parent.width - Style.space(67)
                                                textFormat: Text.PlainText
                                                text: modelData.title + (modelData.location ? "\n" + modelData.location : "")
                                                color: root.contentForeground
                                                font.family: Style.font.family
                                                font.pixelSize: Style.font.body
                                                wrapMode: Text.Wrap
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            visible: root.groups.length === 0
                            width: parent.width
                            text: "No events in this range."
                            color: root.mutedForeground
                            font.family: Style.font.family
                            font.pixelSize: Style.font.body
                            horizontalAlignment: Text.AlignHCenter
                            topPadding: Style.space(18)
                        }
                    }
                }
            }
        }
    }
}
