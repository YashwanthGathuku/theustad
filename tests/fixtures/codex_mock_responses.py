"""A stand-in for the OpenAI Responses API, enough to drive `codex exec`.

Each POST /v1/responses is answered with a single assistant message, taken in
order from the script file (one message per line; the last one repeats).  An
optional `TAMPER:<path>` line deletes that file before answering, so the
"agent" tampers with the repository during its turn.  Every request body is
appended to the log as one JSON line.
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT_FILE, SCRIPT, LOG = (Path(arg) for arg in sys.argv[1:4])
_lock = threading.Lock()
_turn = {"n": 0}


def _sse(events):
    out = []
    for event in events:
        out.append(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n")
    return "".join(out).encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        body = json.dumps({"object": "list", "data": []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        with _lock:
            with LOG.open("a", encoding="utf-8") as log:
                log.write(json.dumps({"path": self.path, "body": raw.decode("utf-8", "replace")}) + "\n")
            lines = [l for l in SCRIPT.read_text(encoding="utf-8").splitlines() if l.strip()]
            index = min(_turn["n"], len(lines) - 1)
            _turn["n"] += 1
            line = lines[index]
        if not self.path.rstrip("/").endswith("/responses"):
            self.send_response(404)
            self.end_headers()
            return
        text = line
        if line.startswith("TAMPER:"):
            target, _, text = line[len("TAMPER:"):].partition("|")
            try:
                os.unlink(target)
            except FileNotFoundError:
                pass
        rid = f"resp_{index}"
        body = _sse([
            {"type": "response.created", "response": {"id": rid}},
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "message",
                    "role": "assistant",
                    "id": f"msg_{index}",
                    "content": [{"type": "output_text", "text": text}],
                },
            },
            {
                "type": "response.completed",
                "response": {
                    "id": rid,
                    "usage": {
                        "input_tokens": 0,
                        "input_tokens_details": None,
                        "output_tokens": 0,
                        "output_tokens_details": None,
                        "total_tokens": 0,
                    },
                },
            },
        ])
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
PORT_FILE.write_text(str(server.server_address[1]), encoding="utf-8")
server.serve_forever()
