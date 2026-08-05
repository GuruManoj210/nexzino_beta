async function api(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok || (data && data.ok === false)) {
    throw new Error((data && data.error) || `Request failed for ${path}`);
  }
  return data;
}

function render(enabled) {
  const stateLabel = document.getElementById("dev-mode-state");
  const toggle = document.getElementById("dev-mode-toggle");
  stateLabel.textContent = enabled ? "Enabled" : "Disabled";
  toggle.textContent = enabled ? "Disable Developer Mode" : "Enable Developer Mode";
}

async function refresh() {
  const data = await api("/api/dev-mode");
  render(data.enabled);
  return data.enabled;
}

async function init() {
  let enabled = await refresh();
  document.getElementById("dev-mode-toggle").addEventListener("click", async () => {
    enabled = !enabled;
    const data = await api("/api/dev-mode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    render(data.enabled);
    enabled = data.enabled;
  });
}

init().catch((error) => {
  console.error(error);
  alert(error.message);
});
