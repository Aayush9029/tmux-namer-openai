# tmux-namer-openai

Cost-effective automatic tmux window naming for Claude Code sessions using OpenAI's `gpt-oss-20b` model.

Automatically generates descriptive 2-4 word names for your tmux windows based on your conversation context with Claude. Uses only user questions (not full context) for maximum cost efficiency.

## Cost Comparison

| Model | Provider | Context | Avg Cost/Call | Relative Cost |
|-------|----------|---------|---------------|---------------|
| **gpt-oss-20b** | OpenAI | Questions only | **~$0.0002** | **1x** (cheapest) |
| gpt-4o-mini | OpenAI | Questions only | ~$0.0008 | 4x |
| claude-haiku | Anthropic | Full context | $0.01-0.08 | 50-400x |

**Pricing (2026):**
- gpt-oss-20b: $0.02/M input, $0.10/M output
- gpt-4o-mini: $0.15/M input, $0.60/M output

## Features

- **Ultra-low cost**: ~$0.0002 per window rename (50-400x cheaper than Claude-based solutions)
- **Zero dependencies**: Uses OpenAI Responses API directly with Python stdlib
- **Container-based**: Runs in isolated Docker container
- **Privacy-focused**: Only sends user questions to OpenAI, not assistant responses or full context
- **Non-blocking**: Runs in background, doesn't delay your workflow
- **Cost tracking**: Logs all API calls with cost data to `~/.local/share/tmux-namer-openai/cost.log`
- **Smart context**: Uses last 3 user questions to generate relevant names

## Prerequisites

- Docker
- tmux
- Claude Code CLI
- OpenAI API key

## Installation

### 1. Set OpenAI API Key

Add to your `~/.bashrc`, `~/.zshrc`, or equivalent:

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

### 2. Install Plugin via Marketplace

```bash
# Add marketplace (if not already added)
claude plugin marketplace add https://github.com/Aayush9029/tmux-namer-openai.git

# Install plugin (will build Docker image)
claude plugin install tmux-namer-openai@tmux-namer-openai-marketplace
```

### 3. Verify Installation

```bash
claude plugin list
```

You should see `tmux-namer-openai` in the list.

```bash
# Verify Docker image
docker images | grep tmux-namer-openai
```

## Usage

Once installed, the plugin automatically runs after each Claude Code interaction (Stop event). Your tmux window will be renamed with a descriptive 2-4 word phrase.

Example window names:
- `debug login error`
- `api endpoint design`
- `tmux namer plugin`
- `swift concurrency fix`

## Cost Tracking

View your usage:

```bash
cat ~/.local/share/tmux-namer-openai/cost.log
```

Example log entry:
```
2026-02-03T12:34:56 cost=$0.000187 input=45 output=8 name="api endpoint design"
```

## Configuration

The plugin uses the `Stop` hook to trigger after each Claude interaction. Configuration is in `.claude-plugin/plugin.json`.

To adjust timeout (default 5 seconds), edit `plugin.json`:

```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "container",
        "image": "tmux-namer-openai:latest",
        "timeout": 10
      }]
    }]
  }
}
```

## How It Works

1. **Hook Trigger**: Runs on Claude Code `Stop` event (after each response)
2. **Container Execution**: Docker container starts with hook data
3. **Context Extraction**: Reads last 3 user questions from conversation
4. **API Call**: HTTP POST to OpenAI Responses API with `gpt-oss-20b` model
5. **Name Generation**: Receives 2-4 word descriptive phrase
6. **Sanitization**: Removes special characters, truncates to 40 chars
7. **Rename**: Updates tmux window name via mounted volumes
8. **Logging**: Records cost and tokens to log file

## Architecture

```
┌─────────────────┐
│  Claude Code    │
│    (Stop)       │
└────────┬────────┘
         │
         v
┌─────────────────────────────────┐
│  Docker Container                │
│  ┌───────────────────────────┐  │
│  │ tmux-namer-openai.py      │  │
│  │  - Parse hook data        │  │
│  │  - Extract questions      │  │
│  │  - HTTP POST to OpenAI    │  │
│  │  - Sanitize response      │  │
│  │  - Update tmux window     │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
         │
         v
┌─────────────────┐
│  OpenAI API     │
│  gpt-oss-20b    │
└─────────────────┘
```

## Troubleshooting

### Window not renaming

1. Check you're in a tmux session:
   ```bash
   echo $TMUX
   ```

2. Verify OpenAI API key:
   ```bash
   echo $OPENAI_API_KEY
   ```

3. Check plugin is enabled:
   ```bash
   claude plugin list
   ```

4. Verify Docker image exists:
   ```bash
   docker images | grep tmux-namer-openai
   ```

5. View logs for errors:
   ```bash
   tail ~/.local/share/tmux-namer-openai/cost.log
   ```

### Container errors

Check Docker logs:
```bash
docker ps -a | grep tmux-namer-openai
docker logs <container-id>
```

Rebuild image:
```bash
cd ~/tmux-namer-openai
docker build -t tmux-namer-openai:latest .
```

### API errors

Check log file for error messages:
```bash
grep error ~/.local/share/tmux-namer-openai/cost.log
```

Common issues:
- `OPENAI_API_KEY not set`: Export your API key in shell
- `HTTP 401`: Invalid API key
- `HTTP 429`: Rate limit exceeded
- `Network error`: Check internet connection

## Development

### Local Installation

```bash
# Clone repository
git clone https://github.com/Aayush9029/tmux-namer-openai.git
cd tmux-namer-openai

# Build Docker image
docker build -t tmux-namer-openai:latest .

# Install plugin locally
claude plugin install .
```

### Testing Container

```bash
# Test container directly
echo '{"conversation": [{"role": "user", "content": [{"type": "text", "text": "test question"}]}]}' | \
  docker run -i --rm \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e TMUX="test" \
  -v ~/.local/share/tmux-namer-openai:/root/.local/share/tmux-namer-openai \
  tmux-namer-openai:latest
```

### Testing Plugin

```bash
# Disable other tmux naming plugins
claude plugin disable tmux-window-namer@claude-tmux-namer

# Start Claude in tmux
tmux new-session -s test
claude

# Send a message and observe window rename
```

## Privacy

- **Only user questions** are sent to OpenAI's API
- Assistant responses and full conversation context are NOT transmitted
- No conversation data is stored beyond cost logs
- Container runs with minimal permissions and network access

## License

MIT License - see [LICENSE](LICENSE) file

## Author

Aayush Pokharel
- GitHub: [@Aayush9029](https://github.com/Aayush9029)
- Website: [aayush.art](https://aayush.art)

## Acknowledgments

Inspired by [tmux-window-namer](https://github.com/anthropics/claude-code/tree/main/plugins/tmux-window-namer) from the Claude Code plugin examples.

## Links

- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/chat)
- [OpenAI Pricing](https://openai.com/pricing)
- [Claude Code Documentation](https://github.com/anthropics/claude-code)
- [tmux Documentation](https://github.com/tmux/tmux/wiki)
