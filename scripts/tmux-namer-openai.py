#!/usr/bin/env python3
"""
tmux-namer-openai.py - Rename tmux window based on user questions using OpenAI

Uses gpt-5-nano to generate a concise 1-2 word tab name describing the work session.
Runs on PostToolUse, renames every 3 user messages.
"""

import os
import sys
import json
import subprocess
import re
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


def read_transcript(transcript_path):
    """Read user messages from the transcript JSONL file."""
    questions = []
    user_count = 0
    try:
        with open(transcript_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get('type') == 'user':
                    user_count += 1
                    content = entry.get('message', {}).get('content', '')
                    if isinstance(content, str):
                        text = content.strip()
                    elif isinstance(content, list):
                        text = ' '.join(
                            item.get('text', '') for item in content
                            if isinstance(item, dict) and item.get('type') == 'text'
                        ).strip()
                    else:
                        text = ''
                    if text:
                        # Truncate long messages to first 200 chars
                        questions.append(text[:200])
    except (OSError, json.JSONDecodeError):
        pass
    return user_count, questions[-3:] if questions else []


def call_openai(questions):
    """Call OpenAI API to generate window name."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None

    if questions:
        context = "\n".join(f"- {q}" for q in questions)
        prompt = f"Name a tmux tab for a coding session.\nRecent questions:\n{context}\n\nRules: max 2 words, all lowercase, use hyphens within words if needed. No project name.\nExamples: food-plan, cf-deploy, fix-hook, api-routes, auth-refactor, snap-tests, debug-ci, dark-mode\nOutput ONLY the tab name:"
    else:
        prompt = f"Name a tmux tab for a new coding session.\nRules: max 2 words, all lowercase, use hyphens within words if needed. No project name.\nExamples: proj-setup, init, new-session\nOutput ONLY the tab name:"

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
    name = re.sub(r'[^a-zA-Z0-9\- ]', '', name)
    if len(name) > 25:
        name = name[:25]
    return name.strip()


def main():
    """Main function."""
    try:
        hook_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = hook_data.get('transcript_path')
    if not transcript_path:
        sys.exit(0)

    fork_and_exit()

    window_target = get_tmux_window()
    if not window_target:
        sys.exit(0)

    msg_count, questions = read_transcript(transcript_path)

    # Only rename every 3 user messages
    if msg_count == 0 or msg_count % 3 != 0:
        sys.exit(0)

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
