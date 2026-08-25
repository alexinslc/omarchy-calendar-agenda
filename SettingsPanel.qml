import QtQuick
import qs.Commons

Flickable {
    id: root
    property var panel
    anchors.fill: parent
    anchors.margins: Style.space(16)
    contentWidth: width
    contentHeight: settingsContent.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    function toggleField(key) {
        var updated = Object.assign({}, panel.preferences)
        updated[key] = !panel.preferences[key]
        panel.preferences = updated
        panel.savePreferences()
    }

    Column {
        id: settingsContent
        width: root.width
        spacing: Style.space(10)

        Row {
            width: parent.width
            spacing: Style.space(8)
        Text {
            text: "SETTINGS"
            color: panel.contentForeground
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            font.bold: true
        }
        Text {
            text: "Done"
            width: parent.width - Style.space(70)
            color: panel.accentForeground
            horizontalAlignment: Text.AlignRight
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
                color: panel.contentForeground
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: panel.preferences[modelData.key] ? "ON" : "OFF"
                color: panel.preferences[modelData.key] ? panel.accentForeground : panel.mutedForeground
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                MouseArea {
                    anchors.fill: parent
                    onClicked: root.toggleField(modelData.key)
                    }
                }
        }
    }

        Text {
            text: "CALENDARS"
            color: panel.accentForeground
            font.family: Style.font.family
            font.pixelSize: Style.font.bodySmall
            font.bold: true
        }

        Repeater {
            model: panel.calendarOptions
            delegate: Rectangle {
            required property var modelData
            width: parent.width
            height: Style.space(30)
            color: "transparent"
            Text {
                text: modelData.name
                color: panel.contentForeground
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: panel.enabled(panel.preferences.calendars, modelData.id) ? "ON" : "OFF"
                color: panel.enabled(panel.preferences.calendars, modelData.id) ? panel.accentForeground : panel.mutedForeground
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        var calendars = Object.assign({}, panel.preferences.calendars)
                        calendars[modelData.id] = !panel.enabled(calendars, modelData.id)
                        panel.preferences = Object.assign({}, panel.preferences, { "calendars": calendars })
                        panel.savePreferences()
                        panel.rebuild()
                        }
                    }
            }
        }
    }

        Text {
            text: "ACCOUNTS"
            color: panel.accentForeground
            font.family: Style.font.family
            font.pixelSize: Style.font.bodySmall
            font.bold: true
        }

        Repeater {
            model: panel.accountOptions
            delegate: Rectangle {
            required property string modelData
            width: parent.width
            height: Style.space(30)
            color: "transparent"
            Text {
                text: modelData
                color: panel.contentForeground
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: panel.enabled(panel.preferences.accounts, modelData) ? "ON" : "OFF"
                color: panel.enabled(panel.preferences.accounts, modelData) ? panel.accentForeground : panel.mutedForeground
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        var accounts = Object.assign({}, panel.preferences.accounts)
                        accounts[modelData] = !panel.enabled(accounts, modelData)
                        panel.preferences = Object.assign({}, panel.preferences, { "accounts": accounts })
                        panel.savePreferences()
                        panel.rebuild()
                        }
                    }
            }
        }
    }

        Text {
            text: "REFRESH: " + panel.preferences.refreshMinutes + " MIN (CLICK TO TOGGLE 15/30)"
            color: panel.contentForeground
            font.family: Style.font.family
            font.pixelSize: Style.font.bodySmall
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    var updated = Object.assign({}, panel.preferences)
                    updated.refreshMinutes = panel.preferences.refreshMinutes === 15 ? 30 : 15
                    panel.preferences = updated
                    panel.savePreferences()
                }
            }
        }
    }
}
