#!/usr/bin/env python3
"""Codex lifecycle observer and tmux agent popup (Python standard library only).

Hooks only observe events: stdout is always {}, never an approval or decision.
SQLite serializes concurrent hooks. Each tmux-launched CLI runs without the shared
daemon so TMUX/TMUX_PANE identify its actual terminal, including in subagents.
"""
import argparse
import curses
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import subprocess
import sys
import time


EVENTS = {
    "SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse",
    "PostToolUse", "PermissionRequest", "SubagentStart", "SubagentStop",
    "Stop", "Interrupt",
}
BADGES = {"approval": "[approve]", "question": "[question]",
          "done": "[done]", "interrupted": "[paused]", "running": "[run]"}


def clean(value, limit=240):
    return " ".join("".join(c for c in str(value or "") if c.isprintable() or c == "\n").split())[:limit]


def context():
    socket = os.environ.get("TMUX", "").split(",")[0]
    pane = os.environ.get("TMUX_PANE", "")
    if not socket or not re.fullmatch(r"%\d+", pane):
        return None
    return socket, pane


def db_path():
    return Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "codex-tmux/state.sqlite3"


def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(path, timeout=0.4)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS agents (
        id TEXT PRIMARY KEY, parent TEXT NOT NULL DEFAULT '',
        socket TEXT NOT NULL, pane TEXT NOT NULL, cwd TEXT NOT NULL DEFAULT '',
        state TEXT NOT NULL DEFAULT 'idle', task TEXT NOT NULL DEFAULT '',
        detail TEXT NOT NULL DEFAULT '', updated REAL NOT NULL)""")
    return db


def tmux(socket, *args):
    result = subprocess.run(["tmux", "-S", socket, *args], text=True,
                            capture_output=True, timeout=0.5, check=True)
    return result.stdout.strip()


def badge(rows):
    for state in ("approval", "question"):
        if any(row["state"] == state for row in rows):
            return BADGES[state]
    roots = [row for row in rows if not row["parent"]]
    for state in ("done", "interrupted", "running"):
        if any(row["state"] == state for row in roots):
            return BADGES[state]
    return ""


def publish(db, socket, pane):
    # Query the current window, so moving panes and multiple Codex panes work.
    window = tmux(socket, "display-message", "-p", "-t", pane, "#{window_id}")
    panes = tmux(socket, "list-panes", "-t", window, "-F", "#{pane_id}").splitlines()
    rows = [row for row in db.execute("SELECT * FROM agents WHERE socket=?", (socket,))
            if row["pane"] in panes]
    tmux(socket, "set-option", "-w", "-t", window, "@codex_badge", badge(rows))


def ensure_agent(db, identity, socket, pane, cwd):
    db.execute("""INSERT INTO agents (id, socket, pane, cwd, updated)
        VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET
        socket=excluded.socket, pane=excluded.pane, cwd=excluded.cwd""",
               (identity, socket, pane, clean(cwd, 500), time.time()))


def update(db, identity, state, detail):
    db.execute("UPDATE agents SET state=?, detail=?, updated=? WHERE id=?",
               (state, clean(detail), time.time(), identity))


def tool_kind(event):
    return str(event.get("tool_name", "")).split(".")[-1]


def response_object(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def record(db, event, socket, pane):
    name = event.get("hook_event_name")
    identity = event.get("session_id")
    if name not in EVENTS or not isinstance(identity, str) or not identity:
        return
    ensure_agent(db, identity, socket, pane, event.get("cwd", ""))
    tool = tool_kind(event)
    inputs = event.get("tool_input")
    inputs = inputs if isinstance(inputs, dict) else {}
    if name == "SessionStart":
        # Compaction is in the middle of work; it must not clear waiting badges.
        if event.get("source") not in ("compact", "fork"):
            update(db, identity, "idle", "Session opened")
    elif name == "UserPromptSubmit":
        update(db, identity, "running", "Working")
    elif name in ("PreToolUse", "PostToolUse"):
        asking = tool in ("request_user_input", "request_user_input_async")
        update(db, identity, "question" if asking else "running",
               "Waiting for your answer" if asking else tool)
        if name == "PostToolUse" and tool == "request_user_input":
            update(db, identity, "running", "Answer received")
        if name == "PostToolUse" and tool in ("spawn_agent", "Agent"):
            response = response_object(event.get("tool_response"))
            child = response.get("agent_id")
            if isinstance(child, str) and child:
                ensure_agent(db, child, socket, pane, event.get("cwd", ""))
                db.execute("UPDATE agents SET parent=?, task=? WHERE id=?",
                           (identity, clean(inputs.get("message", inputs.get("prompt", ""))), child))
    elif name == "PermissionRequest":
        update(db, identity, "approval", "Approval requested: " + tool)
    elif name in ("SubagentStart", "SubagentStop"):
        child = event.get("agent_id")
        if isinstance(child, str) and child and child != identity:
            ensure_agent(db, child, socket, pane, event.get("cwd", ""))
            db.execute("UPDATE agents SET parent=? WHERE id=?", (identity, child))
            starting = name == "SubagentStart"
            update(db, child, "running" if starting else "done",
                   event.get("agent_type", "Subagent") if starting else
                   event.get("last_assistant_message") or "Subagent finished")
    elif name == "Stop":
        update(db, identity, "done", "Turn finished; ready for you")
    elif name == "Interrupt":
        update(db, identity, "interrupted", "Turn interrupted")
    elif name == "SessionEnd":
        update(db, identity, "closed", "Session closed")
        # Close descendants as well, including nested subagents.
        db.execute("""WITH RECURSIVE children(id) AS (
            SELECT id FROM agents WHERE parent=? UNION
            SELECT agents.id FROM agents JOIN children ON agents.parent=children.id)
            UPDATE agents SET state='closed' WHERE id IN (SELECT id FROM children)""", (identity,))


def handle_hook(event):
    location = context()
    if os.environ.get("CODEX_TMUX_MONITOR") != "1" or not location:
        return
    socket, pane = location
    db = connect()
    try:
        with db:
            db.execute("DELETE FROM agents WHERE updated < ?", (time.time() - 7 * 86400,))
            record(db, event, socket, pane)
            publish(db, socket, pane)
    finally:
        db.close()


def clear():
    location = context()
    if not location:
        return
    socket, pane = location
    db = connect()
    try:
        with db:
            db.execute("DELETE FROM agents WHERE socket=? AND pane=?", (socket, pane))
            publish(db, socket, pane)
    finally:
        db.close()


def snapshot():
    if not db_path().exists():
        return []
    db = sqlite3.connect(db_path().as_uri() + "?mode=ro", uri=True, timeout=0.2)
    db.row_factory = sqlite3.Row
    try:
        # Popups do not necessarily inherit a pane id from tmux's job environment.
        socket = os.environ.get("CODEX_TMUX_SOCKET", os.environ.get("TMUX", "").split(",")[0])
        return [dict(row) for row in db.execute(
            "SELECT * FROM agents WHERE socket=? AND state != 'closed' ORDER BY updated DESC", (socket,))]
    finally:
        db.close()


def lines_for(rows):
    lines = []
    by_id = {row["id"]: row for row in rows}
    seen = set()

    def add(row, depth):
        if row["id"] in seen:
            return
        seen.add(row["id"])
        indent = "  " * min(depth, 8)
        age = max(0, int(time.time() - row["updated"]))
        label = "agent " + row["id"][:12] if row["parent"] else row["cwd"]
        lines.append(f"{indent}{clean(row['pane'])}  {clean(row['state']).upper():11}  {clean(label, 500)}  ({age}s ago)")
        if row["task"]:
            lines.append(indent + "  Task: " + clean(row["task"]))
        lines.append(indent + "  " + clean(row["detail"]))
        for child in rows:
            if child["parent"] == row["id"]:
                add(child, depth + 1)

    for row in rows:
        if row["parent"] not in by_id:
            add(row, 0)
    for row in rows:
        add(row, 0)
    return lines


def dashboard(screen):
    # Disable terminal flow control so Ctrl+Q reaches the popup as a key.
    curses.raw()
    curses.curs_set(0)
    screen.timeout(1000)
    offset = 0
    while True:
        screen.erase()
        height, width = screen.getmaxyx()
        try:
            rows = snapshot()
            lines = lines_for(rows) if rows else [
                "No tracked Codex sessions on this tmux server.",
                "Open a new Zsh shell, start codex, and trust the hooks with /hooks."]
        except sqlite3.Error:
            lines = ["Waiting for the next hook update..."]
        offset = min(offset, max(0, len(lines) - max(1, height - 3)))
        display = ["Codex agents | q / Esc / Ctrl+Q close | arrows scroll | refresh 1s", ""]
        display += lines[offset:offset + max(0, height - 3)]
        for y, line in enumerate(display[:max(0, height - 1)]):
            try:
                screen.addnstr(y, 0, line, max(0, width - 1))
            except curses.error:
                pass
        screen.refresh()
        key = screen.getch()
        if key in (ord("q"), 27, 17):
            return
        if key in (curses.KEY_DOWN, ord("j")):
            offset += 1
        elif key in (curses.KEY_UP, ord("k")):
            offset = max(0, offset - 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("hook", "clear", "popup", "dashboard", "list"))
    parser.add_argument("--client")
    parser.add_argument("--socket")
    args = parser.parse_args()
    if args.action in ("hook", "clear"):
        try:
            if args.action == "hook":
                event = json.load(sys.stdin)
                if isinstance(event, dict):
                    handle_hook(event)
            else:
                clear()
        except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError):
            # Monitoring must never block work or decide an approval.
            pass
        if args.action == "hook":
            print("{}")
    elif args.action == "list":
        print("\n".join(lines_for(snapshot())))
    elif args.action == "dashboard":
        curses.wrapper(dashboard)
    else:
        socket = args.socket or os.environ.get("TMUX", "").split(",")[0]
        if not socket or not args.client:
            parser.error("popup requires a tmux socket and --client")
        tmux_args = ["display-popup", "-c", args.client, "-E", "-w", "90%", "-h", "75%",
                     "-e", "CODEX_TMUX_SOCKET=" + socket,
                     "-e", "XDG_STATE_HOME=" + str(db_path().parent.parent),
                     "-b", "rounded", "-s", "bg=#232136,fg=#e0def4",
                     "-S", "bg=#232136,fg=#c4a7e7", "-T", " Codex agents ",
                     shlex.join([sys.executable, str(Path(__file__).resolve()), "dashboard"])]
        # Popup remains open until its command exits; no short subprocess timeout.
        subprocess.run(["tmux", "-S", socket, *tmux_args], check=True)


if __name__ == "__main__":
    main()
