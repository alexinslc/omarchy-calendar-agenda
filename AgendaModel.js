.pragma library

var DAY_NAMES = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
var MONTH_NAMES = [
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"
]

function pad(value) {
    return value < 10 ? "0" + value : String(value)
}

function keyForDate(date) {
    return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate())
}

function dateForKey(key) {
    var parts = String(key).split("-")
    return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
}

function dateOnlyKey(value) {
    var text = String(value || "")
    return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : keyForDate(new Date(text))
}

function timeLabel(value, twelveHour) {
    var date = new Date(value)
    if (isNaN(date.getTime())) return ""
    if (twelveHour) {
        var hour = date.getHours()
        var suffix = hour >= 12 ? " PM" : " AM"
        hour = hour % 12 || 12
        return hour + ":" + pad(date.getMinutes()) + suffix
    }
    return pad(date.getHours()) + ":" + pad(date.getMinutes())
}

function normalizeEvent(event) {
    if (!event || !event.title || !event.start) return null
    var allDay = event.allDay === true
    var start = allDay ? dateOnlyKey(event.start) : String(event.start)
    var date = allDay ? dateForKey(start) : new Date(start)
    if (isNaN(date.getTime())) return null

    return {
        title: String(event.title),
        allDay: allDay,
        start: start,
        end: event.end ? String(event.end) : "",
        location: event.location ? String(event.location) : "",
        accountId: event.accountId ? String(event.accountId) : "",
        calendarId: event.calendarId ? String(event.calendarId) : "",
        calendarName: event.calendarName ? String(event.calendarName) : "",
        calendarColor: event.calendarColor ? String(event.calendarColor) : "",
        dateKey: allDay ? start : keyForDate(date),
        timeLabel: allDay ? "ALL DAY" : timeLabel(start),
        sortTime: date.getTime()
    }
}

function activeDateKeys(event) {
    var start = event.allDay ? dateForKey(event.start) : new Date(event.start)
    if (isNaN(start.getTime()) || !event.end) return [event.dateKey]

    var end = event.allDay ? dateForKey(dateOnlyKey(event.end)) : new Date(event.end)
    if (isNaN(end.getTime()) || end <= start) return [event.dateKey]
    if (event.allDay || (end.getHours() === 0 && end.getMinutes() === 0
            && end.getSeconds() === 0 && end.getMilliseconds() === 0)) {
        end.setDate(end.getDate() - 1)
    }

    var keys = []
    var cursor = new Date(start.getFullYear(), start.getMonth(), start.getDate())
    var last = new Date(end.getFullYear(), end.getMonth(), end.getDate())
    while (cursor <= last) {
        keys.push(keyForDate(cursor))
        cursor.setDate(cursor.getDate() + 1)
    }
    return keys
}

function parseEvents(data) {
    var source = data && data.events instanceof Array ? data.events : []
    var result = []
    for (var i = 0; i < source.length; i++) {
        var event = normalizeEvent(source[i])
        if (!event) continue
        var dates = activeDateKeys(event)
        for (var j = 0; j < dates.length; j++) {
            var occurrence = Object.assign({}, event)
            occurrence.dateKey = dates[j]
            result.push(occurrence)
        }
    }
    return result
}

function compareEvents(a, b) {
    if (a.allDay !== b.allDay) return a.allDay ? -1 : 1
    if (a.sortTime !== b.sortTime) return a.sortTime - b.sortTime
    return a.title.localeCompare(b.title)
}

function sortedEvents(events) {
    var result = events.slice()
    result.sort(compareEvents)
    return result
}

function startOfWeek(date) {
    var result = new Date(date.getFullYear(), date.getMonth(), date.getDate())
    var daysFromMonday = (result.getDay() + 6) % 7
    result.setDate(result.getDate() - daysFromMonday)
    return result
}

function rangeFor(mode, anchor) {
    var start
    var end
    if (mode === "week") {
        start = startOfWeek(anchor)
        end = new Date(start)
        end.setDate(end.getDate() + 7)
    } else if (mode === "month") {
        start = new Date(anchor.getFullYear(), anchor.getMonth(), 1)
        end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 1)
    } else {
        start = new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate())
        end = new Date(start)
        end.setDate(end.getDate() + 1)
    }
    return { start: start, end: end }
}

function groupLabel(key, mode, todayKey) {
    if (mode === "day" && key === todayKey) return "TODAY"
    var date = dateForKey(key)
    return DAY_NAMES[date.getDay()] + " " + MONTH_NAMES[date.getMonth()] + " " + date.getDate()
}

function groupedEvents(events, mode, anchor) {
    var range = rangeFor(mode, anchor)
    var todayKey = keyForDate(new Date())
    var groups = {}
    var keys = []

    for (var i = 0; i < events.length; i++) {
        var event = events[i]
        var eventDate = dateForKey(event.dateKey)
        if (eventDate < range.start || eventDate >= range.end) continue
        if (!groups[event.dateKey]) {
            groups[event.dateKey] = []
            keys.push(event.dateKey)
        }
        groups[event.dateKey].push(event)
    }

    keys.sort()
    var result = []
    for (var j = 0; j < keys.length; j++) {
        var key = keys[j]
        result.push({
            key: key,
            label: groupLabel(key, mode, todayKey),
            events: sortedEvents(groups[key])
        })
    }
    return result
}

function moveAnchor(anchor, mode, amount) {
    var result = new Date(anchor)
    if (mode === "week") result.setDate(result.getDate() + amount * 7)
    else if (mode === "month") result = new Date(result.getFullYear(), result.getMonth() + amount, 1)
    else result.setDate(result.getDate() + amount)
    return result
}

function viewTitle(mode, anchor) {
    if (mode === "month")
        return MONTH_NAMES[anchor.getMonth()] + " " + anchor.getFullYear()
    if (mode === "week") {
        var range = rangeFor(mode, anchor)
        var last = new Date(range.end)
        last.setDate(last.getDate() - 1)
        var startLabel = MONTH_NAMES[range.start.getMonth()] + " " + range.start.getDate()
        var endLabel = MONTH_NAMES[last.getMonth()] + " " + last.getDate()
        if (range.start.getFullYear() !== last.getFullYear()) {
            startLabel += ", " + range.start.getFullYear()
            endLabel += ", " + last.getFullYear()
        } else {
            endLabel += ", " + last.getFullYear()
        }
        return startLabel + " – " + endLabel
    }
    return MONTH_NAMES[anchor.getMonth()] + " " + anchor.getDate() + ", " + anchor.getFullYear()
}
