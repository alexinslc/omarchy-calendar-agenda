import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: root

    property bool loaded: false
    property bool configured: false
    property bool secretServiceAvailable: false
    property bool cacheAvailable: false
    property var accounts: []
    property string configurationError: ""
    property string actionStatus: ""
    property string statusError: ""
    property string actionError: ""
    readonly property string lastError: actionError || statusError
    property string activeAction: ""
    property string activeAccountId: ""
    property string localRemovalAccountId: ""
    readonly property bool busy: statusProcess.running || actionProcess.running
    readonly property string helperPath: Quickshell.env("HOME")
        + "/.config/omarchy/plugins/io.github.alexinslc.calendar-agenda/calendar_agenda.py"

    property string _statusOutput: ""
    property string _statusError: ""
    property string _actionOutput: ""
    property string _actionError: ""

    signal cacheChanged()
    signal actionCompleted(bool ok, string message)

    function cleanMessage(value, fallback) {
        var text = String(value || "").replace(/\s+/g, " ").trim()
        if (!text) text = fallback
        return text.length > 240 ? text.substring(0, 237) + "…" : text
    }

    function parseResult(raw) {
        try {
            var value = JSON.parse(String(raw || ""))
            return value && typeof value === "object" ? value : null
        } catch (error) {
            return null
        }
    }

    function resultDetails(parsed) {
        if (!parsed || typeof parsed !== "object") return ""
        var details = []
        if (parsed.warnings instanceof Array) {
            for (var i = 0; i < parsed.warnings.length; i++) {
                if (parsed.warnings[i]) details.push(String(parsed.warnings[i]))
            }
        }
        if (parsed.sync && parsed.sync.errors instanceof Array) {
            for (var j = 0; j < parsed.sync.errors.length; j++) {
                var syncError = parsed.sync.errors[j]
                if (syncError && syncError.message)
                    details.push(String(syncError.message))
            }
        }
        return root.cleanMessage(details.join(" · "), "")
    }

    function refresh() {
        if (statusProcess.running || actionProcess.running) return
        root._statusOutput = ""
        root._statusError = ""
        statusProcess.command = ["/usr/bin/python3", root.helperPath, "--status"]
        statusProcess.running = true
    }

    function runAction(name, args, progress) {
        if (root.busy) return
        root._actionOutput = ""
        root._actionError = ""
        root.activeAction = name
        root.localRemovalAccountId = ""
        root.actionError = ""
        root.actionStatus = progress
        actionProcess.command = ["/usr/bin/python3", root.helperPath].concat(args)
        actionProcess.running = true
    }

    function addAccount() {
        runAction("add", ["--add-account"], "Waiting for Google authorization…")
    }

    function syncNow() {
        runAction("sync", ["--sync", "--json"], "Synchronizing calendars…")
    }

    function reconnectAccount(accountId) {
        root.activeAccountId = String(accountId)
        runAction(
            "reconnect",
            ["--reconnect-account", String(accountId)],
            "Waiting for Google authorization…"
        )
    }

    function removeAccount(accountId, localOnly) {
        root.activeAccountId = String(accountId)
        var args = ["--remove-account", String(accountId)]
        if (localOnly === true) args.push("--local-only")
        runAction("remove", args, "Removing Google account access…")
    }

    Component.onCompleted: refresh()

    Process {
        id: statusProcess
        running: false
        command: []
        stdout: StdioCollector {
            id: statusStdout
            waitForEnd: true
            onStreamFinished: root._statusOutput = text
        }
        stderr: StdioCollector {
            id: statusStderr
            waitForEnd: true
            onStreamFinished: root._statusError = text
        }
        onExited: function(exitCode) {
            var parsed = root.parseResult(statusStdout.text || root._statusOutput)
            root.loaded = true
            if (!parsed) {
                root.statusError = root.cleanMessage(
                    statusStderr.text || root._statusError,
                    "Could not read calendar connection status."
                )
                return
            }
            root.configured = parsed.configured === true
            root.secretServiceAvailable = parsed.secretServiceAvailable === true
            root.cacheAvailable = parsed.cacheAvailable === true
            root.configurationError = String(parsed.configurationError || "")
            root.accounts = parsed.accounts instanceof Array ? parsed.accounts : []
            if (exitCode !== 0 && !root.configurationError) {
                root.statusError = root.cleanMessage(
                    parsed.error || statusStderr.text || root._statusError,
                    "Could not read calendar connection status."
                )
            } else {
                root.statusError = ""
            }
        }
    }

    Process {
        id: actionProcess
        running: false
        command: []
        stdout: StdioCollector {
            id: actionStdout
            waitForEnd: true
            onStreamFinished: root._actionOutput = text
        }
        stderr: StdioCollector {
            id: actionStderr
            waitForEnd: true
            onStreamFinished: root._actionError = text
        }
        onExited: function(exitCode) {
            var completedAction = root.activeAction
            var completedAccountId = root.activeAccountId
            var parsed = root.parseResult(actionStdout.text || root._actionOutput)
            var ok = exitCode === 0 && parsed && parsed.ok === true
            var details = root.resultDetails(parsed)
            var message = parsed
                ? String(parsed.error || parsed.message || "")
                : root.cleanMessage(
                    actionStderr.text || root._actionError,
                    "Calendar account action failed."
                )
            root.actionStatus = ok
                ? root.cleanMessage(
                    message + (details ? " · " + details : ""),
                    "Calendar account action completed."
                )
                : ""
            root.actionError = ok ? "" : root.cleanMessage(
                (parsed && parsed.error) ? parsed.error : (details || message),
                "Calendar account action failed."
            )
            if (completedAction === "remove") {
                root.localRemovalAccountId = ok ? "" : completedAccountId
            }
            root.activeAction = ""
            root.activeAccountId = ""
            root.cacheChanged()
            root.actionCompleted(ok, ok ? root.actionStatus : root.actionError)
            Qt.callLater(root.refresh)
        }
    }
}
