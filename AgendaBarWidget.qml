import QtQuick
import qs.Commons
import qs.Ui

BarWidget {
    id: root
    moduleName: "io.github.alexinslc.calendar-agenda"

    function injectPanel() {
        if (!panelLoader.item) return
        panelLoader.item.bar = root.bar
        panelLoader.item.settings = root.settings
        panelLoader.item.anchorItem = button
        panelLoader.item.hostWidget = root
    }

    readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
    readonly property bool popoutSwitchClosing: panelLoader.item
        ? panelLoader.item.popoutSwitchClosing === true
        : false

    function open() {
        if (panelLoader.item) panelLoader.item.open()
    }

    function close() {
        if (panelLoader.item) panelLoader.item.close()
    }

    function closeForPopoutSwitch() {
        if (panelLoader.item) panelLoader.item.closeForPopoutSwitch()
    }

    function toggle() {
        if (opened) close()
        else open()
    }

    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    onBarChanged: injectPanel()
    onSettingsChanged: injectPanel()

    Loader {
        id: panelLoader
        active: true
        source: Qt.resolvedUrl("AgendaPanel.qml")
        visible: false
        onLoaded: {
            root.injectPanel()
            Qt.callLater(root.injectPanel)
        }
    }

    BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: "󰃭"
        slotSize: Style.bar.statusSlot
        tooltipText: "Calendar agenda"

        onPressed: function(button) {
            if (button === Qt.LeftButton) root.toggle()
        }
    }
}
