FROM python:3.11-slim

WORKDIR /app

# Copy script
COPY tmux-namer-openai.py .

# Make executable
RUN chmod +x tmux-namer-openai.py

ENTRYPOINT ["python3", "/app/tmux-namer-openai.py"]
