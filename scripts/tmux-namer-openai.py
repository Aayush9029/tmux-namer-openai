#!/usr/bin/env python3
"""
tmux-namer-openai.py - Rename tmux window based on user questions using OpenAI

Uses gpt-5-nano to generate a 2-word phrase describing the work session.
Runs on PostToolUse, renames every 3 user messages.
"""

import os
import sys
import json
import subprocess
import re
from pathlib import Path
from urllib.request import Request, urlopen


def fork_and_exit():
    """Fork process to run in background without blocking."""
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except AttributeError:
        pass


def get_tmux_window():
    """Find the tmux window where Claude is running."""
    if not os.environ.get('TMUX'):
        return None

    pane_id = os.environ.get('TMUX_PANE')
    if not pane_id:
        return None

    try:
        result = subprocess.run(
            ['tmux', 'list-panes', '-a', '-F', '#{pane_id} #{session_name}:#{window_id}'],
            capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == pane_id:
                return parts[1]
    except subprocess.CalledProcessError:
        return None

    return None


def count_user_messages(hook_data):
    """Count total user messages in conversation."""
    count = 0
    for message in hook_data.get('conversation', []):
        if message.get('role') == 'user':
            count += 1
    return count


def extract_user_questions(hook_data):
    """Extract last 3 user questions from conversation."""
    questions = []
    for message in hook_data.get('conversation', []):
        if message.get('role') == 'user':
            for item in message.get('content', []):
                if isinstance(item, dict) and item.get('type') == 'text':
                    text = item.get('text', '').strip()
                    if text:
                        questions.append(text)
    return questions[-3:] if questions else []


def call_openai(questions):
    """Call OpenAI API to generate window name."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None

    if questions:
        context = "\n".join(f"- {q}" for q in questions)
        prompt = f"Summarize this work session in exactly 2 lowercase words separated by a space:\n{context}\n\nExamples: tmux config, fix auth, api routes, swift tests\nOutput ONLY two words:"
    else:
        cwd = Path.cwd().name
        prompt = f"Summarize a work session in '{cwd}' in exactly 2 lowercase words separated by a space.\nExamples: tmux config, fix auth, api routes\nOutput ONLY two words:"

    payload = {
        "model": "gpt-5-nano",
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": 50,
        "reasoning_effort": "minimal"
    }

    try:
        req = Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )
        with urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
        return result['choices'][0]['message']['content'].strip()
    except:
        return None


def sanitize_name(name):
    """Sanitize name to alphanumeric and spaces only."""
    if not name:
        return ""
    name = re.sub(r'[^a-zA-Z0-9 ]', '', name)
    if len(name) > 40:
        name = name[:40]
    return name.strip()


def main():
    """Main function."""
    try:
        hook_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    fork_and_exit()

    window_target = get_tmux_window()
    if not window_target:
        sys.exit(0)

    # Only rename every 3 user messages
    msg_count = count_user_messages(hook_data)
    if msg_count == 0 or msg_count % 3 != 0:
        sys.exit(0)

    questions = extract_user_questions(hook_data)
    name = call_openai(questions)

    if not name:
        sys.exit(0)

    name = sanitize_name(name)

    if name:
        try:
            subprocess.run(
                ['tmux', 'rename-window', '-t', window_target, name],
                check=True
            )
        except subprocess.CalledProcessError:
            pass


if __name__ == '__main__':
    main()
