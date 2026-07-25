from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_monitoring_page_loads_local_echarts_and_exposes_dashboard_hooks():
    template = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

    assert "/vendor/echarts/echarts.min.js" in template
    assert 'id="monitoring"' in template
    assert "function renderMonitoringChart" in script
    assert "function loadMonitoringTasks" in script


def test_monitoring_styles_respect_reduced_motion():
    styles = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")

    assert ".monitoring-chart" in styles
    assert "prefers-reduced-motion: reduce" in styles
