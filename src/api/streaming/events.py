import json
from dataclasses import dataclass


@dataclass
class SSEEvent:
    event: str
    data: dict | list


def format_sse(event: SSEEvent) -> str:
    payload = json.dumps(event.data, ensure_ascii=False)
    return f"event: {event.event}\ndata: {payload}\n\n"
