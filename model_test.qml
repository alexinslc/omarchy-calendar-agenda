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
        var bounded = AgendaModel.parseEvents({
            events: [{
                title: "Untrusted long event",
                start: "1900-01-01",
                end: "9999-12-31",
                allDay: true
            }]
        })
        if (bounded.length !== 32) {
            console.error("all-day expansion bound test failed")
            Qt.exit(1)
            return
        }
        var cache = AgendaModel.parseCache({
            schemaVersion: 1,
            generatedAt: "2026-08-24T15:00:00Z",
            rangeStart: "2026-08-24T15:00:00Z",
            rangeEnd: "2026-09-21T15:00:00Z",
            accounts: [{ id: "personal" }],
            calendars: [{
                accountId: "personal",
                id: "primary",
                name: "Personal",
                color: "#4285f4"
            }],
            events: [{
                title: "Review",
                start: "2026-08-24T09:00:00-06:00",
                end: "2026-08-24T10:00:00-06:00",
                allDay: false,
                location: "",
                accountId: "personal",
                calendarId: "primary",
                calendarName: "Personal"
            }]
        })
        if (cache.events.length !== 1
                || cache.calendars.length !== 1
                || AgendaModel.calendarKey("personal", "primary") !== "personal::primary") {
            console.error("cache contract test failed")
            Qt.exit(1)
            return
        }
        var clippedCache = AgendaModel.parseCache({
            schemaVersion: 1,
            generatedAt: "2026-08-24T15:00:00Z",
            rangeStart: "2026-08-24T15:00:00Z",
            rangeEnd: "2026-09-21T15:00:00Z",
            accounts: [{ id: "personal" }],
            calendars: [{
                accountId: "personal",
                id: "primary",
                name: "<img src='https://attacker.invalid/calendar'>"
            }],
            events: [{
                title: "<img src='https://attacker.invalid/event'>",
                start: "1900-01-01",
                end: "9999-12-31",
                allDay: true,
                location: "",
                accountId: "personal",
                calendarId: "primary",
                calendarName: "<img src='https://attacker.invalid/calendar'>"
            }]
        })
        if (clippedCache.events.length !== 29
                || clippedCache.events[0].dateKey !== "2026-08-24"
                || clippedCache.events[28].dateKey !== "2026-09-21") {
            console.error("cache-range expansion bound test failed")
            Qt.exit(1)
            return
        }
        var invalidCacheRejected = false
        try {
            AgendaModel.parseCache({ events: [] })
        } catch (error) {
            invalidCacheRejected = true
        }
        if (!invalidCacheRejected
                || !isNaN(AgendaModel.dateForKey("2026-02-31").getTime())) {
            console.error("cache validation test failed")
            Qt.exit(1)
            return
        }
        console.log("agenda model tests passed")
        Qt.exit(0)
    }
}
