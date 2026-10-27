"""Telegram access: sending messages from the agent to your chat.

The bot token and your chat ID live in .env. The bot only ever talks to that one chat.
"""
import os

import requests
from dotenv import load_dotenv

from src.config import ROOT

load_dotenv(ROOT / ".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")   # The bot's password (secret)
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")   # Your chat: the only place the bot sends to
MAX_LENGTH = 4096                         # Telegram's limit on characters per message


def _api(method, payload):
    """Call one Telegram Bot API method (e.g. "sendMessage") and return Telegram's reply as a dictionary.
    The token is part of the address, so the address must never be printed or logged."""
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    reply = requests.post(url, json=payload, timeout=15).json()   # json= sends the payload as JSON; timeout = give up after 15s
    if not reply.get("ok"):
        # A readable error that leaves out the address, so the token never appears in an error message
        raise RuntimeError(f"Telegram {method} failed: {reply.get('description')}")
    return reply


def send_message(text):
    """Send plain text to your chat. Text longer than Telegram's limit is split into several messages."""
    # range(0, len(text), MAX_LENGTH) counts 0, 4096, 8192, ... so each slice is at most 4096 characters
    for start in range(0, len(text), MAX_LENGTH):
        _api("sendMessage", {"chat_id": CHAT_ID, "text": text[start:start + MAX_LENGTH]})