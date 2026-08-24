import QtQuick
import "./AgendaModel.js" as AgendaModel

QtObject {
    Component.onCompleted: {
        var early = new Date(2026, 7, 24, 9, 0)
        var late = new Date(2026, 7, 24, 14, 0)
        var data = {
            events: [
                { title: "Timed late", start: late.toISOString() },
                { title: "All day", start: "2026-08-24", allDay: true },
                { title: "Timed early", start: early.toISOString() }
            ]
        }
        var events = AgendaModel.parseEvents(data)
        var groups = AgendaModel.groupedEvents(events, "day", new Date(2026, 7, 24))
        if (groups.length !== 1
                || groups[0].events[0].title !== "All day"
                || groups[0].events[1].title !== "Timed early"
                || groups[0].events[2].title !== "Timed late") {
            console.error("agenda model ordering test failed")
                Qt.exit(1)
            return
        }
        if (AgendaModel.moveAnchor(new Date(2026, 7, 24), "week", 1).getDate() !== 31) {
            console.error("agenda model navigation test failed")
                Qt.exit(1)
            return
        }
        var spanning = AgendaModel.parseEvents({
                events: [{ title: "Spanning", start: "2026-08-24", end: "2026-08-26", allDay: true }]
        })
        if (spanning.length !== 2
                    || spanning[0].dateKey !== "2026-08-24"
                    || spanning[1].dateKey !== "2026-08-25") {
                console.error("spanning event test failed")
                Qt.exit(1)
                return
        }
        console.log("agenda model tests passed")
        Qt.exit(0)
    }
}
