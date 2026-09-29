from __future__ import annotations

import json
from pathlib import Path

from scripts.dashboard import calculate_dashboard, load_recent_records, render_dashboard


def test_runtime_dashboard_renders_six_populated_panels(tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    records = [
        {
            "ts": "2999-01-01T00:00:00Z",
            "event": "request_received",
        },
        {
            "ts": "2999-01-01T00:00:01Z",
            "event": "response_sent",
            "latency_ms": 500,
            "ttft_ms": 50,
            "cost_usd": 0.002,
            "tokens_in": 20,
            "tokens_out": 80,
            "quality_score": 0.9,
            "tool_success": True,
        },
    ]
    log_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
    )

    data = calculate_dashboard(load_recent_records(log_path))
    dashboard = render_dashboard(data)

    assert dashboard.count("<section>") == 6
    assert "P95 500 ms" in dashboard
    assert "Retrieval 100.0%" in dashboard
    assert "Quality proxy" in dashboard
