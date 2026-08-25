import QtQuick
import qs.Commons
import qs.Ui

Flickable {
    id: root
    property var panel
    anchors.fill: parent
    anchors.margins: Style.space(16)
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

        Row {
            width: parent.width
            height: Style.space(34)
            spacing: Style.space(8)

            Text {
                text: "SETTINGS"
                color: panel.contentForeground
                font.family: Style.font.family
                font.pixelSize: Style.font.title
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                text: "DONE"
                width: parent.width - Style.space(80)
                color: panel.accentForeground
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                font.bold: true
                horizontalAlignment: Text.AlignRight
                anchors.verticalCenter: parent.verticalCenter
                MouseArea {
                    anchors.fill: parent
                    onClicked: panel.settingsOpen = false
                }
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
            delegate: Toggle {
                required property var modelData
                width: root.width
                label: modelData.label
                checked: panel.preferences[modelData.key]
                onClicked: root.toggleField(modelData.key)
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
            delegate: Toggle {
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
            delegate: Toggle {
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

        Toggle {
            width: root.width
            label: "Refresh interval"
            description: "Automatically reload cached events"
            checked: panel.preferences.refreshMinutes === 15
            onClicked: {
                var updated = Object.assign({}, panel.preferences)
                updated.refreshMinutes = panel.preferences.refreshMinutes === 15 ? 30 : 15
                panel.preferences = updated
                panel.savePreferences()
            }
        }
    }
}
