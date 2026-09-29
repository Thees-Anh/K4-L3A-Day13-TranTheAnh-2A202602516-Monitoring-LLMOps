from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.metrics import percentile


LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"


def load_recent_records(path: Path = LOG_PATH, minutes: int = 60) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    records: list[dict] = []
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            timestamp = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        if timestamp >= cutoff:
            records.append(record)
    return records


def calculate_dashboard(records: list[dict]) -> dict:
    requests = [record for record in records if record.get("event") == "request_received"]
    responses = [record for record in records if record.get("event") == "response_sent"]
    failures = [record for record in records if record.get("event") == "request_failed"]
    retrievals = [
        record for record in records if isinstance(record.get("tool_success"), bool)
    ]
    request_times = [
        datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
        for record in requests
    ]
    active_minutes = (
        max(1.0, (max(request_times) - min(request_times)).total_seconds() / 60)
        if request_times
        else 1.0
    )
    latencies = [int(record["latency_ms"]) for record in responses]
    ttfts = [int(record["ttft_ms"]) for record in responses]
    qualities = [float(record["quality_score"]) for record in responses]
    error_rate = (len(failures) / len(requests) * 100) if requests else 0.0
    retrieval_success = (
        sum(record["tool_success"] for record in retrievals) / len(retrievals) * 100
        if retrievals
        else 0.0
    )
    return {
        "request_count": len(requests),
        "requests_per_minute": len(requests) / active_minutes,
        "latency_p50": percentile(latencies, 50),
        "latency_p95": percentile(latencies, 95),
        "latency_p99": percentile(latencies, 99),
        "ttft_p95": percentile(ttfts, 95),
        "latencies": latencies,
        "error_rate": error_rate,
        "error_count": len(failures),
        "retrieval_success": retrieval_success,
        "cost_total": sum(float(record["cost_usd"]) for record in responses),
        "costs": [float(record["cost_usd"]) for record in responses],
        "tokens_in": sum(int(record["tokens_in"]) for record in responses),
        "tokens_out": sum(int(record["tokens_out"]) for record in responses),
        "quality_avg": mean(qualities) if qualities else 0.0,
    }


def _sparkline(values: list[float], width: int = 360, height: int = 72) -> str:
    if not values:
        return '<div class="empty">Chưa có dữ liệu</div>'
    low, high = min(values), max(values)
    span = high - low or 1
    step = width / max(1, len(values) - 1)
    points = " ".join(
        f"{index * step:.1f},{height - 8 - ((value - low) / span) * (height - 16):.1f}"
        for index, value in enumerate(values)
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Chuỗi {len(values)} giá trị"><polyline points="{points}" /></svg>'
    )


def render_dashboard(data: dict) -> str:
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    panels = [
        (
            "Latency percentiles and TTFT",
            f'<div class="values"><b>P50 {data["latency_p50"]:.0f} ms</b><b>P95 {data["latency_p95"]:.0f} ms</b>'
            f'<b>P99 {data["latency_p99"]:.0f} ms</b><b>TTFT P95 {data["ttft_p95"]:.0f} ms</b></div>'
            + _sparkline(data["latencies"])
            + '<p>Threshold: P95 ≤ 3000 ms</p>',
        ),
        (
            "Request traffic",
            f'<div class="hero">{data["request_count"]}</div><p>requests / 60 phút · '
            f'{data["requests_per_minute"]:.2f} requests/phút</p><p>Threshold: ≥ 1 request/phút</p>',
        ),
        (
            "Error rate and retrieval success",
            f'<div class="values"><b>Error {data["error_rate"]:.1f}%</b>'
            f'<b>Retrieval {data["retrieval_success"]:.1f}%</b></div>'
            f'<p>{data["error_count"]} request lỗi · Threshold: error ≤ 2%, retrieval ≥ 90%</p>',
        ),
        (
            "Cost over time",
            f'<div class="hero">${data["cost_total"]:.4f}</div>'
            + _sparkline(data["costs"])
            + '<p>USD / 60 phút · Threshold: total ≤ $2.50</p>',
        ),
        (
            "Input and output tokens",
            f'<div class="values"><b>Input {data["tokens_in"]:,}</b>'
            f'<b>Output {data["tokens_out"]:,}</b></div>'
            f'<div class="bar"><span style="width:{min(100, (data["tokens_in"] + data["tokens_out"]) / 500):.1f}%"></span></div>'
            '<p>tokens / 60 phút · Threshold: total ≤ 50,000</p>',
        ),
        (
            "Quality proxy",
            f'<div class="hero">{data["quality_avg"]:.2f}</div>'
            f'<div class="bar"><span style="width:{data["quality_avg"] * 100:.1f}%"></span></div>'
            '<p>score 0–1 · Threshold: mean ≥ 0.75</p>',
        ),
    ]
    panel_html = "".join(
        f'<section><h2>{html.escape(title)}</h2>{content}</section>'
        for title, content in panels
    )
    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta http-equiv="refresh" content="30">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Day 13 LLMOps Dashboard</title>
<style>
:root{{--bg:#07111f;--panel:#101d30;--text:#f4f7fb;--muted:#9fb0c7;--accent:#55d6be;--line:#233653}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px system-ui;padding:28px}}
header{{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:22px}}h1{{margin:0;font-size:26px}}header p,p{{color:var(--muted);margin:7px 0 0}}
main{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}section{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px;min-height:190px}}
h2{{font-size:16px;font-weight:600;margin:0 0 18px}}.values{{display:flex;gap:16px;flex-wrap:wrap}}.hero{{font-size:34px;font-weight:650;color:var(--accent)}}
svg{{width:100%;height:72px;margin-top:12px}}polyline{{fill:none;stroke:var(--accent);stroke-width:3;stroke-linejoin:round;stroke-linecap:round}}
.bar{{height:10px;background:var(--line);border-radius:8px;margin-top:20px;overflow:hidden}}.bar span{{display:block;height:100%;background:var(--accent)}}.empty{{color:var(--muted);padding:24px 0}}
@media(max-width:900px){{main{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:600px){{body{{padding:16px}}header{{display:block}}main{{grid-template-columns:1fr}}}}
</style></head><body><header><div><h1>K4-L3A · Monitoring & LLMOps</h1><p>Time range: 60 phút · Auto refresh: 30 giây</p></div><p>Cập nhật: {html.escape(generated)}</p></header><main>{panel_html}</main></body></html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        body = render_dashboard(calculate_dashboard(load_recent_records())).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Local six-panel dashboard for Day 13")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
