import QtQuick
import QtQuick.Controls as QQC2
import qs.Commons
import qs.Ui

Flickable {
    id: root
    property var panel
    property var onboarding
    property string pendingRemovalId: ""
    anchors.fill: parent
    anchors.margins: Style.space(16)
    enabled: panel.preferencesLoaded
    contentWidth: width
    contentHeight: contentColumn.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick
    interactive: contentHeight > height
    QQC2.ScrollBar.vertical: QQC2.ScrollBar { policy: QQC2.ScrollBar.AsNeeded }

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
            text: "CONNECTED ACCOUNTS"
            color: panel.accentForeground
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            font.bold: true
            font.letterSpacing: 1.2
        }

        Text {
            visible: onboarding.actionStatus !== "" || onboarding.lastError !== ""
            width: root.width
            text: onboarding.lastError !== "" ? onboarding.lastError : onboarding.actionStatus
            color: onboarding.lastError !== "" ? panel.accentForeground : panel.mutedForeground
            font.family: Style.font.family
            font.pixelSize: Style.font.bodySmall
            wrapMode: Text.Wrap
        }

        Button {
            visible: onboarding.localRemovalAccountId !== ""
            text: "Remove locally anyway"
            bordered: true
            enabled: !onboarding.busy
            horizontalPadding: Style.space(8)
            verticalPadding: Style.space(4)
            onClicked: onboarding.removeAccount(onboarding.localRemovalAccountId, true)
        }

        Row {
            width: root.width
            spacing: Style.space(6)

            Button {
                text: onboarding.busy ? "Working…" : "Add account"
                bordered: true
                enabled: onboarding.configured && onboarding.secretServiceAvailable && !onboarding.busy
                horizontalPadding: Style.space(8)
                verticalPadding: Style.space(4)
                onClicked: onboarding.addAccount()
            }

            Button {
                text: "Sync now"
                bordered: true
                enabled: !onboarding.busy && onboarding.accounts.length > 0
                horizontalPadding: Style.space(8)
                verticalPadding: Style.space(4)
                onClicked: onboarding.syncNow()
            }
        }

        Repeater {
            model: onboarding.accounts
            delegate: Rectangle {
                required property var modelData
                width: root.width
                height: accountColumn.implicitHeight + Style.space(16)
                radius: Style.cornerRadius
                color: Qt.rgba(panel.contentForeground.r, panel.contentForeground.g, panel.contentForeground.b, 0.07)

                Column {
                    id: accountColumn
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: Style.space(8)
                    spacing: Style.space(5)

                    Text {
                        width: parent.width
                        text: modelData.email || modelData.displayName || modelData.id
                        color: panel.contentForeground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body
                        font.bold: true
                        elide: Text.ElideRight
                    }

                    Text {
                        visible: modelData.legacy === true
                        width: parent.width
                        text: "Reconnect once to finish account migration."
                        color: panel.accentForeground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.caption
                        wrapMode: Text.Wrap
                    }

                    Text {
                        visible: modelData.state === "needs-attention"
                        width: parent.width
                        text: "Needs attention  ·  " + String(modelData.lastError || "Reconnect this account.")
                        color: panel.accentForeground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.caption
                        wrapMode: Text.Wrap
                    }

                    Row {
                        spacing: Style.space(6)
                        visible: root.pendingRemovalId !== modelData.id

                        Button {
                            text: "Reconnect"
                            bordered: true
                            enabled: !onboarding.busy
                            horizontalPadding: Style.space(7)
                            verticalPadding: Style.space(3)
                            onClicked: onboarding.reconnectAccount(modelData.id)
                        }

                        Button {
                            text: "Remove"
                            bordered: true
                            enabled: !onboarding.busy
                            horizontalPadding: Style.space(7)
                            verticalPadding: Style.space(3)
                            onClicked: root.pendingRemovalId = modelData.id
                        }
                    }

                    Text {
                        visible: root.pendingRemovalId === modelData.id
                        width: parent.width
                        text: "Remove this plugin’s access and cached events? Nothing in Google Calendar will be deleted."
                        color: panel.contentForeground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.caption
                        wrapMode: Text.Wrap
                    }

                    Row {
                        spacing: Style.space(6)
                        visible: root.pendingRemovalId === modelData.id

                        Button {
                            text: "Confirm remove"
                            bordered: true
                            enabled: !onboarding.busy
                            horizontalPadding: Style.space(7)
                            verticalPadding: Style.space(3)
                            onClicked: {
                                root.pendingRemovalId = ""
                                onboarding.removeAccount(modelData.id, false)
                            }
                        }

                        Button {
                            text: "Cancel"
                            bordered: true
                            enabled: !onboarding.busy
                            horizontalPadding: Style.space(7)
                            verticalPadding: Style.space(3)
                            onClicked: root.pendingRemovalId = ""
                        }
                    }
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
            delegate: CompactToggle {
                required property var modelData
                width: root.width
                label: modelData.label
                checked: panel.preferences[modelData.key]
                onClicked: root.toggleField(modelData.key)
            }
        }

        Text {
            text: "TIME FORMAT"
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
                readonly property string preferenceKey: modelData.accountId + "::" + modelData.id
                width: root.width
                label: modelData.name + "  ·  " + modelData.accountId
                checked: panel.calendarEnabledFor(modelData.accountId, modelData.id)
                onClicked: {
                    var calendars = Object.assign({}, panel.preferences.calendars)
                    calendars[preferenceKey] = !panel.calendarEnabledFor(modelData.accountId, modelData.id)
                    panel.preferences = Object.assign({}, panel.preferences, { "calendars": calendars })
                    panel.savePreferences()
                    panel.rebuild()
                }
            }
        }

        Text {
            text: "ACCOUNT VISIBILITY"
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
                checked: panel.preferenceEnabled(panel.preferences.accounts, modelData)
                onClicked: {
                    var accounts = Object.assign({}, panel.preferences.accounts)
                    accounts[modelData] = !panel.preferenceEnabled(accounts, modelData)
                    panel.preferences = Object.assign({}, panel.preferences, { "accounts": accounts })
                    panel.savePreferences()
                    panel.rebuild()
                }
            }
        }

    }
}
