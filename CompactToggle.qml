import QtQuick
import qs.Commons
import qs.Ui

BorderSurface {
    id: root
    property string label: ""
    property bool checked: false
    property color foreground: Color.foreground
    property color accent: Color.accent
    signal clicked()

    implicitHeight: Style.space(38)
    radius: Style.cornerRadius
    color: mouse.containsMouse
        ? Style.controlFill(false, true, foreground, accent)
        : Style.controlFill(false, false, foreground, accent)
    borderSpec: Border.controlSpec(mouse.containsMouse ? "hover-cursor" : "normal", foreground, accent)

    Text {
        anchors.left: parent.left
        anchors.leftMargin: root.borderLeft + Style.spacing.rowPaddingX
        anchors.verticalCenter: parent.verticalCenter
        textFormat: Text.PlainText
        text: root.label
        color: root.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        elide: Text.ElideRight
    }

    ToggleSwitch {
        id: switchControl
        anchors.right: parent.right
        anchors.rightMargin: root.borderRight + Style.spacing.rowPaddingX
        anchors.verticalCenter: parent.verticalCenter
        trackHeight: 18
        checked: root.checked
        interactive: false
        foreground: root.foreground
        accent: root.accent
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
