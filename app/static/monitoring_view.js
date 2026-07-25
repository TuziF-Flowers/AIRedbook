(function exposeMonitoringView(root, factory) {
  const api = factory();
  root.MonitoringView = api;
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis === "object" ? globalThis : window, () => {
  const statuses = {
    active: { statusClass: "active", statusLabel: "监测中" },
    completed: { statusClass: "completed", statusLabel: "已完成" },
    error: { statusClass: "error", statusLabel: "更新失败" },
  };

  function orderedSnapshots(task) {
    return [...(task?.snapshots || [])].sort(
      (left, right) => new Date(left.collected_at) - new Date(right.collected_at),
    );
  }

  function metricSummary(task, metric) {
    const snapshots = orderedSnapshots(task);
    const latest = snapshots.at(-1);
    const previous = snapshots.at(-2);
    const total = Number(latest?.[metric] || 0);
    return {
      total,
      delta: previous ? total - Number(previous?.[metric] || 0) : null,
    };
  }

  function latestUpdate(task) {
    return [task?.last_collected_at, task?.last_error_at, task?.created_at]
      .filter(Boolean)
      .sort((left, right) => new Date(right) - new Date(left))[0] || null;
  }

  function taskPresentation(task) {
    const status = statuses[task?.status] || {
      statusClass: "error",
      statusLabel: "状态未知",
    };
    return {
      ...status,
      error: task?.last_error || null,
      coverUrl: task?.cover_url || null,
      createdAt: task?.created_at || null,
      updatedAt: latestUpdate(task),
    };
  }

  return { metricSummary, taskPresentation };
});
