# tmux-namer-openai

Automatically names your tmux windows based on what you're working on with Claude.

Uses OpenAI's **gpt-5-nano** model.

## Cost

~$0.001 per rename (input: $0.05/M tokens, output: $0.40/M tokens)

## Install

```bash
export OPENAI_API_KEY="sk-..."
claude plugin marketplace add https://github.com/Aayush9029/tmux-namer-openai.git openai
claude plugin install tmux-namer-openai@openai
```

## How it works

After every other Claude interaction, your tmux window gets renamed based on your last 3 questions (to save costs).

Examples: `food-plan`, `cf-deploy`, `fix-hook`, `api-routes`, `auth-refactor`, `debug-ci`

## License

MIT - [Aayush Pokharel](https://github.com/Aayush9029)
