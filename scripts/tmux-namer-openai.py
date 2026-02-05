#!/usr/bin/env python3
"""
tmux-namer-openai.py - Rename tmux window based on user questions using OpenAI

Uses gpt-5-nano model to generate a 2-4 word phrase describing the work session.
"""

import os
import sys
import json
import subprocess
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


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

    ppid = os.getppid()

    try:
        result = subprocess.run(
            ['ps', '-o', 'tty=', '-p', str(ppid)],
            capture_output=True,
            text=True,
            check=True
        )
        claude_tty = result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

    if not claude_tty:
        return None

    if not claude_tty.startswith('/'):
        claude_tty = f'/dev/{claude_tty}'

    try:
        result = subprocess.run(
            ['tmux', 'list-panes', '-a', '-F', '#{pane_tty} #{session_name}:#{window_id}'],
            capture_output=True,
            text=True,
            check=True
        )

        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == claude_tty:
                return parts[1]
    except subprocess.CalledProcessError:
        return None

    return None


def extract_user_questions(hook_data):
    """Extract last 3 user questions from conversation."""
    questions = []

    conversation = hook_data.get('conversation', [])
    for message in conversation:
        if message.get('role') == 'user':
            content = message.get('content', [])
            for item in content:
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
        prompt = f"Generate a tmux window name based on these user questions:\n{context}\n\nRequirements: 1-2 word, lowercase, 4-30 characters. Output ONLY the phrase, nothing else."
    else:
        cwd = Path.cwd().name
        prompt = f"Generate a tmux window name for a work session in directory '{cwd}'. Requirements: 2-3 words, lowercase, 8-30 characters. Output ONLY the phrase, nothing else."

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


def should_rename(window_id):
    """Check if we should rename (every other call) for this window."""
    # Plugin root is two directories up from this script
    plugin_root = Path(__file__).parent.parent
    # Use window ID to keep counters separate per window
    safe_id = window_id.replace(':', '_').replace('@', '_')
    counter_file = plugin_root / f'.counter_{safe_id}'

    try:
        count = int(counter_file.read_text().strip()) if counter_file.exists() else 0
    except:
        count = 0

    count += 1
    counter_file.write_text(str(count))

    return count % 2 == 0


def main():
    """Main function."""
    fork_and_exit()

    window_target = get_tmux_window()
    if not window_target:
        sys.exit(0)

    # Only rename every other call to save costs
    if not should_rename(window_target):
        sys.exit(0)

    try:
        hook_data = json.load(sys.stdin)
    except json.JSONDecodeError:
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
