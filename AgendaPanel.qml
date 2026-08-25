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
    property bool settingsOpen: false
    property var preferences: ({
        "showTime": true,
        "showCalendar": true,
        "showLocation": true,
        "refreshMinutes": 15,
        "accounts": {},
        "calendars": {}
    })
    property var accountOptions: []
    property var calendarOptions: []
    readonly property string cachePath: Quickshell.env("HOME") + "/.local/state/omarchy/calendar-agenda/events.json"
    readonly property string settingsPath: Quickshell.env("HOME") + "/.local/state/omarchy/calendar-agenda/settings.json"

    readonly property color contentForeground: bar ? bar.foreground : Color.foreground
    readonly property color contentBackground: Color.background
    readonly property color mutedForeground: Qt.rgba(contentForeground.r, contentForeground.g, contentForeground.b, 0.58)
    readonly property color accentForeground: Color.accent
    readonly property string title: AgendaModel.viewTitle(viewMode, anchorDate)

    function loadEvents(text) {
        var data
        try {
            data = JSON.parse(text)
        } catch (error) {
            console.error(
                "calendar cache contains invalid JSON:",
                error.message
            )
            root.events = []
            root.groups = []
            root.dataState = "error"
            root.dataMessage = "Calendar data is unavailable. Run a sync to refresh it."
            return
        }
        root.events = AgendaModel.parseEvents(data)
        root.dataState = "ready"
        root.dataMessage = ""
        root.updateOptions()
        rebuild()
    }

    function updateOptions() {
        var accounts = {}
        var calendars = {}
        for (var i = 0; i < root.events.length; i++) {
            var event = root.events[i]
            if (event.accountId) accounts[event.accountId] = true
            if (event.calendarId) {
                calendars[event.calendarId] = {
                    "id": event.calendarId,
                    "name": event.calendarName || event.calendarId
                }
            }
        }
        root.accountOptions = Object.keys(accounts).sort()
        root.calendarOptions = Object.keys(calendars).sort().map(function(id) {
            return calendars[id]
        })
    }

    function enabled(map, key) {
        return !map || map[key] !== false
    }

    function savePreferences() {
        settingsFile.setText(JSON.stringify(root.preferences, null, 2) + "\n")
    }

    function rebuild() {
        var visible = root.events.filter(function(event) {
            return root.enabled(root.preferences.accounts, event.accountId)
                && root.enabled(root.preferences.calendars, event.calendarId)
        })
        root.groups = AgendaModel.groupedEvents(visible, root.viewMode, root.anchorDate)
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
        id: settingsFile
        path: root.settingsPath
        atomicWrites: true
        printErrors: false
        onLoaded: {
            try {
                var parsed = JSON.parse(text())
                if (parsed && typeof parsed === "object")
                    root.preferences = Object.assign(root.preferences, parsed)
            } catch (error) {
                console.warn("calendar settings could not be loaded:", error)
            }
            root.rebuild()
        }
    }

    FileView {
        id: cacheFile
        path: root.cachePath
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.loadEvents(text())
        onLoadFailed: {
            root.events = []
            root.groups = []
            root.dataState = "error"
            root.dataMessage = "No calendar data is available. Run a sync to refresh it."
        }
    }

    Timer {
        interval: root.preferences.refreshMinutes * 60000
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

            SettingsPanel {
                visible: root.settingsOpen
                panel: root
            }

            Column {
                id: agendaColumn
                visible: !root.settingsOpen
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

                    Text {
                        text: "⚙"
                        width: Style.space(24)
                        color: root.mutedForeground
                        font.pixelSize: Style.font.body
                        horizontalAlignment: Text.AlignRight
                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.settingsOpen = true
                        }
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

                        Column {
                            id: settingsColumn
                            visible: false
                            anchors.fill: parent
                            anchors.margins: Style.space(16)
                            spacing: Style.space(10)

                            Row {
                                width: parent.width
                                spacing: Style.space(8)
                                Text {
                                    text: "SETTINGS"
                                    color: root.contentForeground
                                    font.family: Style.font.family
                                    font.pixelSize: Style.font.body
                                    font.bold: true
                                }
                                Text {
                                    text: "Done"
                                    width: parent.width - Style.space(70)
                                    color: root.accentForeground
                                    horizontalAlignment: Text.AlignRight
                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: root.settingsOpen = false
                                    }
                                }
                            }

                            Text {
                                text: "DISPLAY"
                                color: root.accentForeground
                                font.family: Style.font.family
                                font.pixelSize: Style.font.bodySmall
                                font.bold: true
                            }

                            Repeater {
                                model: [
                                    { "key": "showTime", "label": "Show event times" },
                                    { "key": "showCalendar", "label": "Show calendar names" },
                                    { "key": "showLocation", "label": "Show locations" }
                                ]
                                delegate: Rectangle {
                                    required property var modelData
                                    width: parent.width
                                    height: Style.space(30)
                                    color: "transparent"
                                    Text {
                                        text: modelData.label
                                        color: root.contentForeground
                                        font.family: Style.font.family
                                        font.pixelSize: Style.font.body
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Text {
                                        text: root.preferences[modelData.key] ? "ON" : "OFF"
                                        color: root.preferences[modelData.key] ? root.accentForeground : root.mutedForeground
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: {
                                                var updated = Object.assign({}, root.preferences)
                                                updated[modelData.key] = !root.preferences[modelData.key]
                                                root.preferences = updated
                                                root.savePreferences()
                                            }
                                        }
                                    }
                                }
                            }

                            Text {
                                text: "CALENDARS"
                                color: root.accentForeground
                                font.family: Style.font.family
                                font.pixelSize: Style.font.bodySmall
                                font.bold: true
                            }

                            Text {
                                text: "ACCOUNTS"
                                color: root.accentForeground
                                font.family: Style.font.family
                                font.pixelSize: Style.font.bodySmall
                                font.bold: true
                            }

                            Repeater {
                                model: root.accountOptions
                                delegate: Rectangle {
                                    required property string modelData
                                    width: parent.width
                                    height: Style.space(30)
                                    color: "transparent"
                                    Text {
                                        text: modelData
                                        color: root.contentForeground
                                        font.family: Style.font.family
                                        font.pixelSize: Style.font.body
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Text {
                                        text: root.enabled(root.preferences.accounts, modelData) ? "ON" : "OFF"
                                        color: root.enabled(root.preferences.accounts, modelData) ? root.accentForeground : root.mutedForeground
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: {
                                                var accounts = Object.assign({}, root.preferences.accounts)
                                                accounts[modelData] = !root.enabled(accounts, modelData)
                                                root.preferences = Object.assign({}, root.preferences, { "accounts": accounts })
                                                root.savePreferences()
                                                root.rebuild()
                                            }
                                        }
                                    }
                                }
                            }

                            Text {
                                text: "REFRESH: " + root.preferences.refreshMinutes + " MIN"
                                color: root.contentForeground
                                font.family: Style.font.family
                                font.pixelSize: Style.font.body
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                                        var updated = Object.assign({}, root.preferences)
                                        updated.refreshMinutes = root.preferences.refreshMinutes === 15 ? 30 : 15
                                        root.preferences = updated
                                        root.savePreferences()
                                    }
                                }
                            }

                            Repeater {
                                model: root.calendarOptions
                                delegate: Rectangle {
                                    required property var modelData
                                    width: parent.width
                                    height: Style.space(30)
                                    color: "transparent"
                                    Text {
                                        text: modelData.name
                                        color: root.contentForeground
                                        font.family: Style.font.family
                                        font.pixelSize: Style.font.body
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Text {
                                        text: root.enabled(root.preferences.calendars, modelData.id) ? "ON" : "OFF"
                                        color: root.enabled(root.preferences.calendars, modelData.id) ? root.accentForeground : root.mutedForeground
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: {
                                                var calendars = Object.assign({}, root.preferences.calendars)
                                                calendars[modelData.id] = !root.enabled(calendars, modelData.id)
                                                root.preferences = Object.assign({}, root.preferences, { "calendars": calendars })
                                                root.savePreferences()
                                                root.rebuild()
                                            }
                                        }
                                    }
                                }
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
                                                visible: root.preferences.showTime
                                                text: modelData.timeLabel
                                                color: modelData.allDay ? root.accentForeground : root.mutedForeground
                                                font.family: Style.font.family
                                                font.pixelSize: Style.font.bodySmall
                                                font.bold: modelData.allDay
                                            }

                                            Text {
                                                id: eventText
                                                width: parent.width - (root.preferences.showTime ? Style.space(67) : Style.space(9))
                                                textFormat: Text.PlainText
                                                text: modelData.title
                                                    + (root.preferences.showCalendar && modelData.calendarName
                                                        ? "\n" + modelData.calendarName : "")
                                                    + (root.preferences.showLocation && modelData.location
                                                        ? "\n" + modelData.location : "")
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
