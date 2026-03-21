# Start with Node 20 (Required for Gemini CLI)
FROM node:20-slim

# 1. Install Python, Pip, and required tools
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. Install the Gemini CLI
RUN npm install -g @google/gemini-cli@latest

# 3. Disable the PEP 668 "externally managed environment" error
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# 4. BYPASS THE TRUST LOOP (System-Wide)
# Putting this in /etc/gemini-cli/settings.json forces it to apply globally, 
# even when we mount your personal host settings over the user directory.
RUN mkdir -p /etc/gemini-cli && \
    echo '{"security": {"folderTrust": {"enabled": false}}}' > /etc/gemini-cli/settings.json

WORKDIR /workspace
