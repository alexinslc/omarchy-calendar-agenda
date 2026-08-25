import QtQuick
import qs.Commons
import qs.Ui

Flickable {
    id: root
    property var panel
    anchors.fill: parent
    anchors.margins: Style.space(16)
    enabled: panel.preferencesLoaded
    contentWidth: width
    contentHeight: contentColumn.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    function toggleField(key) {
        var updated = Object.assign({}, panel.preferences)
        updated[key] = !panel.preferences[key]
        panel.preferences = updated
        panel.savePreferences()
    }

    Column {
        id: contentColumn
        width: root.width
        spacing: Style.space(10)

        Item {
            width: parent.width
            height: Style.space(34)
            Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "SETTINGS"
                color: panel.contentForeground
                font.family: Style.font.family
                font.pixelSize: Style.font.title
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }

            Button {
                anchors.right: parent.right
                text: "Done"
                bordered: true
                horizontalPadding: Style.space(8)
                verticalPadding: Style.space(4)
                anchors.verticalCenter: parent.verticalCenter
                onClicked: panel.settingsOpen = false
            }
        }

        Text {
            text: "DISPLAY"
            color: panel.accentForeground
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            font.bold: true
            font.letterSpacing: 1.2
        }

        Repeater {
            model: [
                { "key": "showTime", "label": "Event times" },
                { "key": "showCalendar", "label": "Calendar names" },
                { "key": "showLocation", "label": "Locations" }
            ]
            delegate: CompactToggle {
                required property var modelData
                width: root.width
                label: modelData.label
                checked: panel.preferences[modelData.key]
                onClicked: root.toggleField(modelData.key)
            }
        }

        Text {
            text: "SYNC EVERY"
            color: panel.accentForeground
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            font.bold: true
            font.letterSpacing: 1.2
        }

        ButtonGroup {
            width: root.width
            options: ["24-hour", "12-hour"]
            value: panel.preferences.timeFormat === "12" ? "12-hour" : "24-hour"
            onChanged: function(value) {
                var updated = Object.assign({}, panel.preferences)
                updated.timeFormat = value === "12-hour" ? "12" : "24"
                panel.preferences = updated
                panel.savePreferences()
            }
        }

        Text {
            text: "CALENDARS"
            color: panel.accentForeground
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            font.bold: true
            font.letterSpacing: 1.2
        }

        Repeater {
            model: panel.calendarOptions
            delegate: CompactToggle {
                required property var modelData
                width: root.width
                label: modelData.name
                checked: panel.enabled(panel.preferences.calendars, modelData.id)
                onClicked: {
                    var calendars = Object.assign({}, panel.preferences.calendars)
                    calendars[modelData.id] = !panel.enabled(calendars, modelData.id)
                    panel.preferences = Object.assign({}, panel.preferences, { "calendars": calendars })
                    panel.savePreferences()
                    panel.rebuild()
                }
            }
        }

        Text {
            text: "ACCOUNTS"
            color: panel.accentForeground
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            font.bold: true
            font.letterSpacing: 1.2
        }

        Repeater {
            model: panel.accountOptions
            delegate: CompactToggle {
                required property string modelData
                width: root.width
                label: modelData
                checked: panel.enabled(panel.preferences.accounts, modelData)
                onClicked: {
                    var accounts = Object.assign({}, panel.preferences.accounts)
                    accounts[modelData] = !panel.enabled(accounts, modelData)
                    panel.preferences = Object.assign({}, panel.preferences, { "accounts": accounts })
                    panel.savePreferences()
                    panel.rebuild()
                }
            }
        }

        ButtonGroup {
            width: root.width
            options: ["15 minutes", "30 minutes"]
            value: panel.preferences.refreshMinutes === 30 ? "30 minutes" : "15 minutes"
            onChanged: function(value) {
                var updated = Object.assign({}, panel.preferences)
                updated.refreshMinutes = value === "30 minutes" ? 30 : 15
                panel.preferences = updated
                panel.savePreferences()
            }
        }
    }
}
