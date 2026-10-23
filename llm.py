"""Small helpers for talking to Claude, shared by the agent's modules."""

import json
import os

import config


def get_client():
    """Return an Anthropic client, or None if no API key is set."""
    import anthropic
    from dotenv import load_dotenv

    load_dotenv()
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip().strip('"\'')  # tolerate stray spaces or quotes
    return anthropic.Anthropic(api_key=key) if key else None


def ask_json(client, prompt, max_tokens=4000, model=None):
    """Send a prompt and return the JSON object in Claude's reply."""
    msg = client.messages.create(
        model=model or config.MODEL,
        max_tokens=max_tokens,  # leaves room for the model's thinking as well as its answer
        messages=[{"role": "user", "content": prompt}],
    )
    # The reply can contain several blocks (e.g. thinking first); use only the text ones.
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError(f"no JSON in reply (stop_reason={msg.stop_reason})")
    return json.loads(text[start : end + 1])
