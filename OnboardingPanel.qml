import QtQuick
import qs.Commons
import qs.Ui

Column {
    id: root
    required property var panel
    required property var onboarding

    anchors.fill: parent
    anchors.margins: Style.space(20)
    spacing: Style.space(16)

    Item {
        width: parent.width
        height: Style.space(36)

        Text {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: "󰃭  CALENDAR AGENDA"
            color: root.panel.contentForeground
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            font.bold: true
        }
    }

    Item { width: 1; height: Style.space(32) }

    Text {
        width: parent.width
        text: "Bring your day into focus"
        color: root.panel.contentForeground
        font.family: Style.font.family
        font.pixelSize: Style.font.title
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
    }

    Text {
        width: parent.width
        text: "Connect Google Calendar to see your day, week, and month. Calendar Agenda requests read-only access, stores tokens in Secret Service, and keeps event data on this computer."
        color: root.panel.mutedForeground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
    }

    Rectangle {
        width: parent.width
        height: privacyText.implicitHeight + Style.space(20)
        radius: Style.cornerRadius
        color: Qt.rgba(
            root.panel.contentForeground.r,
            root.panel.contentForeground.g,
            root.panel.contentForeground.b,
            0.07
        )

        Text {
            id: privacyText
            anchors.fill: parent
            anchors.margins: Style.space(10)
            text: "READ-ONLY  •  LOCAL CACHE  •  EASY TO DISCONNECT"
            color: root.panel.accentForeground
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            font.bold: true
            font.letterSpacing: 0.8
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            wrapMode: Text.Wrap
        }
    }

    Text {
        visible: !root.onboarding.configured || !root.onboarding.secretServiceAvailable
        width: parent.width
        text: !root.onboarding.configured
            ? root.onboarding.configurationError
            : "Secret Service is unavailable. Install secret-tool and unlock a Secret Service provider before connecting."
        color: root.panel.accentForeground
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
    }

    Text {
        visible: root.onboarding.lastError !== ""
        width: parent.width
        text: root.onboarding.lastError
        color: root.panel.accentForeground
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
    }

    Button {
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.onboarding.busy ? "Waiting for Google…" : "Connect Google Calendar"
        bordered: true
        enabled: root.onboarding.configured
            && root.onboarding.secretServiceAvailable
            && !root.onboarding.busy
        horizontalPadding: Style.space(14)
        verticalPadding: Style.space(8)
        onClicked: root.onboarding.addAccount()
    }

    Button {
        anchors.horizontalCenter: parent.horizontalCenter
        text: "Privacy details"
        bordered: false
        horizontalPadding: Style.space(8)
        verticalPadding: Style.space(3)
        onClicked: Qt.openUrlExternally(
            "https://calendar.alexinslc.com/privacy/"
        )
    }

    Text {
        width: parent.width
        text: "You can add more accounts or remove access at any time from Settings. Removing an account never deletes calendars or events from Google."
        color: root.panel.mutedForeground
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
    }
}
