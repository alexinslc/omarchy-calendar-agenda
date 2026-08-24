import QtQuick
import "./AgendaModel.js" as AgendaModel

QtObject {
    Component.onCompleted: {
        var data = {
            events: [
                { title: "Timed late", start: "2026-08-24T14:00:00-06:00" },
                { title: "All day", start: "2026-08-24", allDay: true },
                { title: "Timed early", start: "2026-08-24T09:00:00-06:00" }
            ]
        }
        var events = AgendaModel.parseEvents(data)
        var groups = AgendaModel.groupedEvents(events, "day", new Date(2026, 7, 24))
        if (groups.length !== 1
                || groups[0].events[0].title !== "All day"
                || groups[0].events[1].title !== "Timed early"
                || groups[0].events[2].title !== "Timed late") {
            console.error("agenda model ordering test failed")
            Qt.quit()
            return
        }
        if (AgendaModel.moveAnchor(new Date(2026, 7, 24), "week", 1).getDate() !== 31) {
            console.error("agenda model navigation test failed")
            Qt.quit()
            return
        }
        console.log("agenda model tests passed")
        Qt.quit()
    }
}
