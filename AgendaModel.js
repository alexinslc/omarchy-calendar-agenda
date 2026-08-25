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
    if (parts.length !== 3) return new Date(NaN)
    var date = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
    return keyForDate(date) === String(key) ? date : new Date(NaN)
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

function parseCache(data) {
    if (!data || typeof data !== "object" || data instanceof Array)
        throw new Error("cache root must be an object")
    if (data.schemaVersion !== 1)
        throw new Error("cache schema version is unsupported")
    if (!(data.events instanceof Array))
        throw new Error("cache events must be an array")
    if (!(data.accounts instanceof Array) || !(data.calendars instanceof Array))
        throw new Error("cache account and calendar metadata must be arrays")

    var generatedAt = new Date(data.generatedAt)
    var rangeStart = new Date(data.rangeStart)
    var rangeEnd = new Date(data.rangeEnd)
    if (isNaN(generatedAt.getTime()) || isNaN(rangeStart.getTime())
            || isNaN(rangeEnd.getTime()) || rangeEnd <= rangeStart)
        throw new Error("cache timestamps are invalid")

    var accounts = []
    var accountIds = []
    for (var i = 0; i < data.accounts.length; i++) {
        var account = data.accounts[i]
        if (!account || typeof account !== "object" || !account.id)
            throw new Error("cache contains invalid account metadata")
        var accountId = String(account.id)
        if (accountIds.indexOf(accountId) !== -1)
            throw new Error("cache contains duplicate account metadata")
        accountIds.push(accountId)
        accounts.push({ "id": accountId })
    }

    var calendars = []
    var calendarKeys = []
    for (var j = 0; j < data.calendars.length; j++) {
        var calendar = data.calendars[j]
        if (!calendar || typeof calendar !== "object" || !calendar.accountId
                || !calendar.id || !calendar.name)
            throw new Error("cache contains invalid calendar metadata")
        var key = calendarKey(calendar.accountId, calendar.id)
        if (accountIds.indexOf(String(calendar.accountId)) === -1
                || calendarKeys.indexOf(key) !== -1)
            throw new Error("cache calendar metadata is inconsistent")
        calendarKeys.push(key)
        calendars.push({
            "accountId": String(calendar.accountId),
            "id": String(calendar.id),
            "name": String(calendar.name),
            "color": calendar.color ? String(calendar.color) : ""
        })
    }

    for (var k = 0; k < data.events.length; k++) {
        var rawEvent = data.events[k]
        if (!rawEvent || typeof rawEvent !== "object"
                || typeof rawEvent.title !== "string"
                || typeof rawEvent.start !== "string"
                || typeof rawEvent.end !== "string"
                || typeof rawEvent.allDay !== "boolean"
                || typeof rawEvent.location !== "string"
                || typeof rawEvent.accountId !== "string"
                || typeof rawEvent.calendarId !== "string"
                || typeof rawEvent.calendarName !== "string"
                || calendarKeys.indexOf(calendarKey(
                    rawEvent.accountId, rawEvent.calendarId)) === -1
                || !normalizeEvent(rawEvent))
            throw new Error("cache contains an invalid event at index " + k)
    }

    return {
        "events": parseEvents(data),
        "accounts": accounts,
        "calendars": calendars,
        "generatedAt": String(data.generatedAt),
        "rangeStart": String(data.rangeStart),
        "rangeEnd": String(data.rangeEnd)
    }
}

function calendarKey(accountId, calendarId) {
    return String(accountId || "") + "::" + String(calendarId || "")
}

function shortDate(value) {
    var date = new Date(value)
    if (isNaN(date.getTime())) return ""
    return MONTH_NAMES[date.getMonth()] + " " + date.getDate() + ", " + date.getFullYear()
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
