#!/usr/bin/env python3
"""Small command-line to-do app.

Usage:
    python todo.py add "buy milk"
    python todo.py list
    python todo.py done 1
"""
import argparse
import json
import os
import sys

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.json")


def load_tasks(path=DEFAULT_PATH):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        return []  # empty file counts as no tasks
    try:
        tasks = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError(f"Could not read {path}: file is not valid JSON.")
    if not isinstance(tasks, list) or not all(
        isinstance(t, dict) and isinstance(t.get("id"), int) and "text" in t and "done" in t
        for t in tasks
    ):
        raise ValueError(f"Could not read {path}: unexpected task format.")
    return tasks


def save_tasks(tasks, path=DEFAULT_PATH):
    # Write to a temp file then replace, so a crash can't leave a half-written file.
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)
    os.replace(tmp_path, path)


def add_task(text, path=DEFAULT_PATH):
    text = text.strip()
    if not text:
        raise ValueError("Task text must not be empty.")
    tasks = load_tasks(path)
    new_id = max((t["id"] for t in tasks), default=0) + 1
    task = {"id": new_id, "text": text, "done": False}
    tasks.append(task)
    save_tasks(tasks, path)
    return task


def list_tasks(path=DEFAULT_PATH):
    return load_tasks(path)


def mark_done(task_id, path=DEFAULT_PATH):
    tasks = load_tasks(path)
    for task in tasks:
        if task["id"] == task_id:
            task["done"] = True
            save_tasks(tasks, path)
            return task
    raise KeyError(f"No task with ID {task_id}.")


def format_task(task):
    return f"{task['id']}. [{'x' if task['done'] else ' '}] {task['text']}"


def build_parser():
    parser = argparse.ArgumentParser(description="Simple to-do list.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_add = sub.add_parser("add", help="add a task")
    p_add.add_argument("text")
    sub.add_parser("list", help="list tasks")
    p_done = sub.add_parser("done", help="mark a task done")
    p_done.add_argument("id", type=int)
    return parser


def main(argv=None, path=DEFAULT_PATH):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "add":
            task = add_task(args.text, path)
            print(f"Added: {format_task(task)}")
        elif args.command == "list":
            tasks = list_tasks(path)
            if not tasks:
                print("No tasks.")
            for task in tasks:
                print(format_task(task))
        elif args.command == "done":
            task = mark_done(args.id, path)
            print(f"Done: {format_task(task)}")
    except (ValueError, KeyError) as e:
        print(f"Error: {e.args[0]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
