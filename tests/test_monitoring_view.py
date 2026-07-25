import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_monitoring_view_presents_enum_status_error_and_metric_delta():
    script = """
const view = require("./app/static/monitoring_view.js");
const task = {
  status: "error",
  last_error: "登录失效，请重新登录",
  cover_url: "https://sns-webpic-qc.xhscdn.com/cover.webp",
  created_at: "2026-07-24T09:00:00+08:00",
  last_collected_at: "2026-07-25T10:00:00+08:00",
  snapshots: [
    { collected_at: "2026-07-24T10:00:00+08:00", likes: 100 },
    { collected_at: "2026-07-25T10:00:00+08:00", likes: 135 },
  ],
};
process.stdout.write(JSON.stringify({
  status: view.taskPresentation(task),
  metric: view.metricSummary(task, "likes"),
}));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    rendered = json.loads(completed.stdout)
    assert rendered == {
        "status": {
            "statusClass": "error",
            "statusLabel": "更新失败",
            "error": "登录失效，请重新登录",
            "coverUrl": "https://sns-webpic-qc.xhscdn.com/cover.webp",
            "createdAt": "2026-07-24T09:00:00+08:00",
            "updatedAt": "2026-07-25T10:00:00+08:00",
        },
        "metric": {"total": 135, "delta": 35},
    }
