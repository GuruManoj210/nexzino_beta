const MAX_LINEAR = 0.3;
const MAX_ANGULAR = 0.3;
const HEARTBEAT_MS = 150; // keeps the server-side watchdog fed while held still
const RECONNECT_DELAY_MS = 1000;
const ENABLED_POLL_MS = 1000; // picks up toggles made from another tab/session

const base = document.getElementById("joystick-base");
const knob = document.getElementById("joystick-knob");
const connectionState = document.getElementById("connection-state");
const linearValue = document.getElementById("linear-value");
const angularValue = document.getElementById("angular-value");
const enableButton = document.getElementById("enable-toggle");

let socket = null;
let socketOpen = false;
let activePointerId = null;
let heartbeatTimer = null;
let command = { linear: 0, angular: 0 };
let publishEnabled = false;

function clamp(value, limit) {
  return Math.max(-limit, Math.min(limit, value));
}

function setConnectionUi(connected) {
  socketOpen = connected;
  connectionState.textContent = connected ? "Connected" : "Disconnected";
  connectionState.classList.toggle("connected", connected);
  connectionState.classList.toggle("disconnected", !connected);
}

function sendCommand(linear, angular) {
  command = { linear, angular };
  linearValue.textContent = linear.toFixed(2);
  angularValue.textContent = angular.toFixed(2);
  // The server is the actual authority on this (it drops commands while
  // disabled and always re-zeroes on a toggle) - this is just an extra
  // guard so a disabled client doesn't even try.
  if (socket && socketOpen && publishEnabled) {
    socket.send(JSON.stringify({ linear, angular }));
  }
}

function forceStopDrag() {
  if (activePointerId !== null) {
    try {
      base.releasePointerCapture(activePointerId);
    } catch (error) {
      // pointer may already be gone - fine, we're resetting either way
    }
    activePointerId = null;
  }
  stopHeartbeat();
  resetKnob();
}

function setEnabledUi(enabled) {
  publishEnabled = enabled;
  enableButton.disabled = false;
  enableButton.textContent = enabled ? "Disable Publishing (LIVE)" : "Enable Publishing";
  enableButton.classList.toggle("enabled-state", enabled);
  enableButton.classList.toggle("disabled-state", !enabled);
  base.classList.toggle("joystick-locked", !enabled);
  if (!enabled) {
    // Whether this came from our own click, another tab, or a poll
    // catching a server-side change mid-drag - stop immediately.
    forceStopDrag();
  }
}

async function refreshEnabledState() {
  const response = await fetch("/api/publish-enabled");
  const data = await response.json();
  if (data.enabled !== publishEnabled) {
    setEnabledUi(data.enabled);
  }
}

async function togglePublishEnabled() {
  enableButton.disabled = true;
  try {
    const response = await fetch("/api/publish-enabled", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !publishEnabled }),
    });
    const data = await response.json();
    setEnabledUi(data.enabled);
  } catch (error) {
    enableButton.disabled = false;
    console.error(error);
  }
}

function connect() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(`${protocol}//${window.location.host}/ws/cmd_vel`);

  socket.addEventListener("open", () => setConnectionUi(true));

  socket.addEventListener("close", () => {
    setConnectionUi(false);
    // The server already zeroes on disconnect (its own failsafe), but reset
    // the on-screen state too so the UI doesn't lie about what's held.
    resetKnob();
    window.setTimeout(connect, RECONNECT_DELAY_MS);
  });

  socket.addEventListener("error", () => socket.close());
}

function knobLimits() {
  const baseRect = base.getBoundingClientRect();
  return {
    centerX: baseRect.left + baseRect.width / 2,
    centerY: baseRect.top + baseRect.height / 2,
    radius: baseRect.width / 2,
  };
}

function updateKnobPosition(clientX, clientY) {
  const { centerX, centerY, radius } = knobLimits();
  let dx = clientX - centerX;
  let dy = clientY - centerY;
  const distance = Math.hypot(dx, dy);
  if (distance > radius) {
    dx = (dx / distance) * radius;
    dy = (dy / distance) * radius;
  }

  knob.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;

  // Forward drag (up, negative dy) -> positive linear.x.
  // Rightward drag (positive dx) -> turn right -> negative angular.z.
  const normX = dx / radius;
  const normY = dy / radius;
  const linear = clamp(-normY * MAX_LINEAR, MAX_LINEAR);
  const angular = clamp(-normX * MAX_ANGULAR, MAX_ANGULAR);
  sendCommand(linear, angular);
}

function resetKnob() {
  knob.style.transform = "translate(-50%, -50%)";
  knob.classList.remove("active");
  sendCommand(0, 0);
}

function startHeartbeat() {
  stopHeartbeat();
  heartbeatTimer = window.setInterval(() => {
    sendCommand(command.linear, command.angular);
  }, HEARTBEAT_MS);
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    window.clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}

function onPointerDown(event) {
  // Belt-and-suspenders on top of the joystick-locked CSS class (which
  // already blocks pointer events via pointer-events: none) and the
  // server dropping any command while disabled.
  if (!publishEnabled) return;
  if (activePointerId !== null) return;
  activePointerId = event.pointerId;
  base.setPointerCapture(activePointerId);
  knob.classList.add("active");
  updateKnobPosition(event.clientX, event.clientY);
  startHeartbeat();
}

function onPointerMove(event) {
  if (event.pointerId !== activePointerId) return;
  updateKnobPosition(event.clientX, event.clientY);
}

function endDrag(event) {
  if (event.pointerId !== activePointerId) return;
  forceStopDrag();
}

base.addEventListener("pointerdown", onPointerDown);
base.addEventListener("pointermove", onPointerMove);
base.addEventListener("pointerup", endDrag);
base.addEventListener("pointercancel", endDrag);
base.addEventListener("lostpointercapture", () => {
  if (activePointerId !== null) {
    forceStopDrag();
  }
});

enableButton.addEventListener("click", togglePublishEnabled);

// Belt-and-suspenders: if the tab is hidden/closed, stop sending motion.
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    forceStopDrag();
  }
});
window.addEventListener("beforeunload", () => {
  sendCommand(0, 0);
});

connect();
refreshEnabledState().catch((error) => console.error(error));
window.setInterval(() => {
  refreshEnabledState().catch((error) => console.error(error));
}, ENABLED_POLL_MS);
