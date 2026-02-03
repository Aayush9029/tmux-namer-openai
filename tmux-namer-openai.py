#!/usr/bin/env python3
"""
tmux-namer-openai.py - Rename tmux window based on user questions using OpenAI Responses API

Uses gpt-oss-20b model via OpenAI Responses API to generate a 2-4 word phrase,
then renames the tmux window where Claude is actually running.
"""

import os
import sys
import json
import subprocess
import re
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def fork_and_exit():
    """Fork process to run in background without blocking."""
    try:
        pid = os.fork()
        if pid > 0:
            # Parent exits immediately
            sys.exit(0)
        # Child continues
    except AttributeError:
        # Windows doesn't support fork, just continue
        pass


def get_tmux_window():
    """Find the tmux window where Claude is running."""
    # Check if running in tmux
    if not os.environ.get('TMUX'):
        return None

    # Get parent PID (Claude process)
    ppid = os.getppid()

    # Get its TTY
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

    # Normalize TTY path (Linux: pts/N, macOS: ttysNNN)
    if not claude_tty.startswith('/'):
        claude_tty = f'/dev/{claude_tty}'

    # Find the tmux pane with this TTY and get its window
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

    # Return last 3 questions
    return questions[-3:] if questions else []


def call_openai_responses(questions):
    """Call OpenAI Responses API to generate window name."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None, "OPENAI_API_KEY not set", None, None, None

    # Create prompt from questions
    if questions:
        context = "\n".join(f"- {q}" for q in questions)
        prompt = f"Based on these user questions:\n{context}\n\nGenerate a 2-4 word lowercase phrase describing this work session. Output ONLY the phrase, nothing else."
    else:
        # Fallback: use current directory
        cwd = Path.cwd().name
        prompt = f"Generate a 2-4 word lowercase phrase for a work session in directory '{cwd}'. Output ONLY the phrase, nothing else."

    # Prepare request payload
    payload = {
        "model": "gpt-oss-20b",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 20,
        "temperature": 0.7
    }

    # Make HTTP request
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

        name = result['choices'][0]['message']['content'].strip()

        # Calculate cost
        usage = result.get('usage', {})
        input_tokens = usage.get('prompt_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0)

        # gpt-oss-20b pricing: $0.02/M input, $0.10/M output
        cost = (input_tokens / 1_000_000 * 0.02) + (output_tokens / 1_000_000 * 0.10)

        return name, None, cost, input_tokens, output_tokens

    except HTTPError as e:
        error_msg = f"HTTP {e.code}: {e.reason}"
        try:
            error_body = json.loads(e.read().decode('utf-8'))
            error_msg = error_body.get('error', {}).get('message', error_msg)
        except:
            pass
        return None, error_msg, None, None, None

    except URLError as e:
        return None, f"Network error: {e.reason}", None, None, None

    except Exception as e:
        return None, str(e), None, None, None


def sanitize_name(name):
    """Sanitize name to alphanumeric and spaces only."""
    if not name:
        return ""

    # Remove non-alphanumeric characters (keep spaces)
    name = re.sub(r'[^a-zA-Z0-9 ]', '', name)

    # Truncate if too long (40 char limit)
    if len(name) > 40:
        name = name[:40]

    return name.strip()


def log_cost(name, cost, input_tokens, output_tokens, error=None):
    """Log cost to file."""
    log_dir = Path.home() / '.local' / 'share' / 'tmux-namer-openai'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'cost.log'

    timestamp = datetime.now().isoformat()

    if error:
        log_line = f'{timestamp} error="{error}"\n'
    else:
        # Escape quotes in name
        safe_name = name.replace('"', '\\"')
        log_line = f'{timestamp} cost=${cost:.6f} input={input_tokens} output={output_tokens} name="{safe_name}"\n'

    with open(log_file, 'a') as f:
        f.write(log_line)


def main():
    """Main function."""
    # Fork immediately to avoid blocking
    fork_and_exit()

    # Find tmux window
    window_target = get_tmux_window()
    if not window_target:
        sys.exit(0)

    # Read hook data from stdin
    try:
        hook_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        log_cost(None, None, None, None, error="Invalid JSON from stdin")
        sys.exit(0)

    # Extract user questions
    questions = extract_user_questions(hook_data)

    # Call OpenAI Responses API
    name, error, cost, input_tokens, output_tokens = call_openai_responses(questions)

    if error:
        log_cost(None, None, None, None, error=error)
        sys.exit(0)

    # Sanitize name
    name = sanitize_name(name)

    # Log cost
    log_cost(name, cost, input_tokens, output_tokens)

    # Rename window if we got a non-empty result
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
