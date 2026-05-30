# Ai-dialog
A Python script that makes two local LLMs debate problems (e.g. DLP in ECDSA, etc.). The AI agents discuss, argue, and propose solutions with configurable roles and personalities.

Two AI models discuss unsolved mathematical problems (DLP, ECDSA, etc.)

## Features
- Run debates between any two local LLMs
- Auto-detects models and GPU configuration
- Configurable problem statements and roles
- Color-coded output
- Saves conversation history

## Requirements
- text-generation-webui running on ports 5001 and 5002
- Python 3.8+

## Installation
pip install -r requirements.txt

## Usage
python debate.py
