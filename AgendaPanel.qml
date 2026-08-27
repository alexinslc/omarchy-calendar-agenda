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
    readonly property var barIdentity: hostWidget || root
    property date anchorDate: new Date()
    property string viewMode: "day"
    property var events: []
    property var groups: []
    property string dataState: "loading"
    property string dataMessage: "Loading calendar data..."
    property string cacheGeneratedAt: ""
    property string cacheRangeStart: ""
    property string cacheRangeEnd: ""
    property bool settingsOpen: false
    property bool preferencesLoaded: false
    property var preferences: ({
        "showTime": true,
        "showCalendar": true,
        "showLocation": true,
        "timeFormat": "24",
        "accounts": {},
        "calendars": {}
    })
    property var accountOptions: []
    property var calendarOptions: []
    property alias onboarding: onboardingService
    readonly property string cachePath: Quickshell.env("HOME") + "/.local/state/omarchy/calendar-agenda/events.json"
    readonly property string settingsPath: Quickshell.env("HOME") + "/.local/state/omarchy/calendar-agenda/settings.json"

    readonly property color contentForeground: bar ? bar.foreground : Color.foreground
    readonly property color contentBackground: Color.background
    readonly property color mutedForeground: Qt.rgba(contentForeground.r, contentForeground.g, contentForeground.b, 0.58)
    readonly property color accentForeground: Color.accent
    readonly property string title: AgendaModel.viewTitle(viewMode, anchorDate)
    readonly property string rangeAvailability: availabilityFor(viewMode, anchorDate)
    readonly property string syncSummary: cacheGeneratedAt && cacheRangeEnd
        ? "Synced " + AgendaModel.timeLabel(cacheGeneratedAt, true)
            + "  •  Through " + AgendaModel.shortDate(cacheRangeEnd)
        : ""

    onOpenedChanged: if (opened) {
        Qt.callLater(function() { keyCatcher.forceActiveFocus() })
    }

    function loadEvents(text) {
        var data
        try {
            data = JSON.parse(text)
        } catch (error) {
            console.error(
                "calendar cache contains invalid JSON:",
                error.message
            )
            root.clearEvents()
            root.dataState = "error"
            root.dataMessage = "Calendar data is unavailable. Run a sync to refresh it."
            return
        }
        var cache
        try {
            cache = AgendaModel.parseCache(data)
        } catch (error) {
            console.error("calendar cache is invalid:", error.message)
            root.clearEvents()
            root.dataState = "error"
            root.dataMessage = "Calendar data is incompatible or incomplete. Run a sync to refresh it."
            return
        }
        root.events = cache.events
        root.cacheGeneratedAt = cache.generatedAt
        root.cacheRangeStart = cache.rangeStart
        root.cacheRangeEnd = cache.rangeEnd
        if (new Date(root.cacheRangeEnd) <= new Date()) {
            root.clearEvents()
            root.dataState = "error"
            root.dataMessage = "Calendar data has expired. Run a sync to refresh it."
            return
        }
        root.accountOptions = cache.accounts.slice().sort(function(a, b) {
            return root.accountLabel(a).localeCompare(root.accountLabel(b))
        })
        root.calendarOptions = cache.calendars.slice().sort(function(a, b) {
            var accountOrder = root.accountLabelForId(a.accountId).localeCompare(
                root.accountLabelForId(b.accountId)
            )
            return accountOrder !== 0 ? accountOrder : a.name.localeCompare(b.name)
        })
        root.dataState = "ready"
        root.dataMessage = ""
        rebuild()
    }

    function clearEvents() {
        root.events = []
        root.groups = []
        root.accountOptions = []
        root.calendarOptions = []
        root.cacheGeneratedAt = ""
        root.cacheRangeStart = ""
        root.cacheRangeEnd = ""
    }

    function preferenceEnabled(map, key) {
        return !map || map[key] !== false
    }

    function accountLabel(account) {
        return String(account.email || account.displayName || account.id)
    }

    function accountLabelForId(accountId) {
        for (var i = 0; i < root.accountOptions.length; i++) {
            if (root.accountOptions[i].id === String(accountId))
                return root.accountLabel(root.accountOptions[i])
        }
        return String(accountId)
    }

    function savePreferences() {
        settingsFile.setText(JSON.stringify(root.preferences, null, 2) + "\n")
    }

    function validatedPreferences(value) {
        var accounts = value.accounts
        var calendars = value.calendars
        return {
            "showTime": value.showTime !== false,
            "showCalendar": value.showCalendar !== false,
            "showLocation": value.showLocation !== false,
            "timeFormat": value.timeFormat === "12" ? "12" : "24",
            "accounts": accounts && typeof accounts === "object"
                && !(accounts instanceof Array) ? accounts : {},
            "calendars": calendars && typeof calendars === "object"
                && !(calendars instanceof Array) ? calendars : {}
        }
    }

    function calendarEnabled(event) {
        return root.calendarEnabledFor(event.accountId, event.calendarId)
    }

    function calendarEnabledFor(accountId, calendarId) {
        var map = root.preferences.calendars
        var key = AgendaModel.calendarKey(accountId, calendarId)
        if (map && map[key] !== undefined) return map[key] !== false
        // Honor settings written by the pre-schema cache until the user changes them.
        return root.preferenceEnabled(map, calendarId)
    }

    function rebuild() {
        var visible = root.events.filter(function(event) {
            return root.preferenceEnabled(root.preferences.accounts, event.accountId)
                && root.calendarEnabled(event)
        })
        root.groups = AgendaModel.groupedEvents(visible, root.viewMode, root.anchorDate)
    }

    function availabilityFor(mode, anchor) {
        if (!root.cacheRangeStart || !root.cacheRangeEnd) return "unknown"
        var cacheStart = new Date(root.cacheRangeStart)
        var cacheEnd = new Date(root.cacheRangeEnd)
        var range = AgendaModel.rangeFor(mode, anchor)
        if (range.end <= cacheStart || range.start >= cacheEnd) return "outside"
        if (range.end > cacheEnd) return "partial-end"
        if (range.start < cacheStart) return "partial-start"
        return "complete"
    }

    function canMove(direction) {
        var candidate = AgendaModel.moveAnchor(root.anchorDate, root.viewMode, direction)
        return root.dataState !== "ready"
            || root.availabilityFor(root.viewMode, candidate) !== "outside"
    }

    function setMode(mode) {
        root.viewMode = mode
        root.rebuild()
    }

    function move(direction) {
        if (!root.canMove(direction)) return
        root.anchorDate = AgendaModel.moveAnchor(root.anchorDate, root.viewMode, direction)
        root.rebuild()
    }

    function goToToday() {
        root.anchorDate = new Date()
        root.viewMode = "day"
        root.rebuild()
    }

    function open() {
        onboardingService.refresh()
        cacheFile.reload()
        root.controller.show()
    }

    function close() {
        root.settingsOpen = false
        root.controller.hide()
    }

    function toggle() {
        if (root.opened) root.close()
        else root.open()
    }

    function switchPanel(direction) {
        if (root.bar && typeof root.bar.switchPanelFrom === "function")
            return root.bar.switchPanelFrom(root.barIdentity, direction)
        return false
    }

    FileView {
        id: settingsFile
        path: root.settingsPath
        atomicWrites: true
        printErrors: false
        onLoaded: {
            try {
                var parsed = JSON.parse(text())
                if (parsed && typeof parsed === "object" && !(parsed instanceof Array))
                    root.preferences = root.validatedPreferences(parsed)
            } catch (error) {
                console.warn("calendar settings could not be loaded:", error)
            }
            root.preferencesLoaded = true
            root.rebuild()
        }
        onLoadFailed: {
            root.preferencesLoaded = true
            root.rebuild()
        }
    }

    OnboardingService {
        id: onboardingService
        onCacheChanged: cacheFile.reload()
    }

    FileView {
        id: cacheFile
        path: root.cachePath
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.loadEvents(text())
        onLoadFailed: {
            root.clearEvents()
            root.dataState = "error"
            root.dataMessage = "No calendar data is available. Run a sync to refresh it."
        }
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
            onTabRequested: function(direction) { root.switchPanel(direction) }
            onTextKey: function(text) {
                if (text === "[" || text === "{") root.move(-1)
                else if (text === "]" || text === "}") root.move(1)
                else if (text === "t" || text === "T") root.goToToday()
                else if (text === "d" || text === "D") root.setMode("day")
                else if (text === "w" || text === "W") root.setMode("week")
                else if (text === "m" || text === "M") root.setMode("month")
                else if (text === "s" || text === "S") root.settingsOpen = true
            }

            OnboardingPanel {
                visible: onboardingService.loaded && onboardingService.accounts.length === 0
                panel: root
                onboarding: onboardingService
            }

            SettingsPanel {
                visible: root.settingsOpen && onboardingService.accounts.length > 0
                panel: root
                onboarding: onboardingService
            }

            Column {
                id: agendaColumn
                visible: !root.settingsOpen
                    && (!onboardingService.loaded || onboardingService.accounts.length > 0)
                anchors.fill: parent
                anchors.margins: Style.space(16)
                spacing: Style.space(10)

                Item {
                    width: parent.width
                    height: Style.space(32)

                    Text {
                        textFormat: Text.PlainText
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: "󰃭"
                        color: root.accentForeground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body * 1.4
                    }

                    Text {
                        textFormat: Text.PlainText
                        anchors.left: parent.left
                        anchors.leftMargin: Style.space(32)
                        anchors.verticalCenter: parent.verticalCenter
                        text: "CALENDAR AGENDA"
                        color: root.contentForeground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.bodySmall
                        font.bold: true
                    }

                    Button {
                        id: settingsButton
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        iconText: "󰒓"
                        tooltipText: "Calendar settings"
                        bordered: true
                        horizontalPadding: Style.space(7)
                        verticalPadding: Style.space(4)
                        onClicked: root.settingsOpen = true
                    }

                    Button {
                        anchors.right: settingsButton.left
                        anchors.rightMargin: Style.space(6)
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Today"
                        tooltipText: "Return to today"
                        bordered: true
                        horizontalPadding: Style.space(8)
                        verticalPadding: Style.space(4)
                        onClicked: root.goToToday()
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
                                textFormat: Text.PlainText
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
                        textFormat: Text.PlainText
                        text: "‹"
                        width: Style.space(30)
                        color: root.canMove(-1) ? root.contentForeground : root.mutedForeground
                        font.pixelSize: Style.font.body * 1.6
                        horizontalAlignment: Text.AlignHCenter
                        MouseArea {
                            anchors.fill: parent
                            enabled: root.canMove(-1)
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: root.move(-1)
                        }
                    }

                    Text {
                        textFormat: Text.PlainText
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
                        textFormat: Text.PlainText
                        text: "›"
                        width: Style.space(30)
                        color: root.canMove(1) ? root.contentForeground : root.mutedForeground
                        font.pixelSize: Style.font.body * 1.6
                        horizontalAlignment: Text.AlignHCenter
                        MouseArea {
                            anchors.fill: parent
                            enabled: root.canMove(1)
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: root.move(1)
                        }
                    }
                }

                Text {
                    textFormat: Text.PlainText
                    visible: root.dataState !== "ready" && root.dataMessage !== ""
                    width: parent.width
                    text: root.dataMessage
                    color: root.dataState === "error" ? root.accentForeground : root.mutedForeground
                    font.family: Style.font.family
                    font.pixelSize: Style.font.bodySmall
                    wrapMode: Text.Wrap
                }

                Text {
                    textFormat: Text.PlainText
                    visible: root.dataState === "ready" && root.syncSummary !== ""
                    width: parent.width
                    text: root.syncSummary
                        + (root.rangeAvailability === "partial-end"
                            ? "\nThis view continues beyond the cached range." : "")
                    color: root.rangeAvailability === "partial-end"
                        ? root.accentForeground : root.mutedForeground
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    wrapMode: Text.Wrap
                    horizontalAlignment: Text.AlignHCenter
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
                                    textFormat: Text.PlainText
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
                                                textFormat: Text.PlainText
                                                width: Style.space(58)
                                                visible: root.preferences.showTime
                                                text: modelData.allDay
                                                    ? modelData.timeLabel
                                                    : (root.preferences.timeFormat === "12"
                                                        ? AgendaModel.timeLabel(modelData.start, true)
                                                        : modelData.timeLabel)
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
                            textFormat: Text.PlainText
                            visible: root.dataState === "ready" && root.groups.length === 0
                            width: parent.width
                            text: root.rangeAvailability === "partial-end"
                                ? "No events in the cached portion of this range."
                                : (root.rangeAvailability === "partial-start"
                                    ? "No upcoming events in this range."
                                    : "No events in this range.")
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
