from __future__ import annotations

import csv
import glob
import json
import logging
import os
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_file
from serial.tools import list_ports
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
SDK_DIR = BASE_DIR / "SCServo_Python"
if str(SDK_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_DIR))

from scservo_sdk import COMM_SUCCESS, PortHandler, sms_sts  # noqa: E402
from scservo_sdk.sms_sts import SMS_STS_TORQUE_ENABLE  # noqa: E402


DEFAULT_SERVO_CONFIG = [
    {
        "name": "right_shoulder_pitch",
        "id": 21,
        "min": 800,
        "max": 2250,
        "init": 2050,
        "speed": 1000,
        "acceleration": 50,
        "model": "SM105BLHV",
    },
    {
        "name": "right_shoulder_yaw",
        "id": 22,
        "min": 500,
        "max": 3500,
        "init": 2050,
        "speed": 100,
        "acceleration": 50,
        "model": "SM40BLHV",
    },
    {
        "name": "right_elbow_pitch",
        "id": 23,
        "min": 2050,
        "max": 3100,
        "init": 2050,
        "speed": 1000,
        "acceleration": 50,
        "model": "SM60-360M",
    },
    {
        "name": "right_elbow_yaw",
        "id": 24,
        "min": 50,
        "max": 4050,
        "init": 2050,
        "speed": 0,
        "acceleration": 50,
        "model": "STS3215",
    },
    {
        "name": "right_wrist",
        "id": 25,
        "min": 50,
        "max": 4050,
        "init": 2050,
        "speed": 0,
        "acceleration": 50,
        "model": "STS3215",
    },
]

BAUDRATE = 1_000_000
DEFAULT_SPEED = 1200
DEFAULT_ACC = 50
RECORD_INTERVAL_SECONDS = 0.1
SERIAL_BY_ID_GLOB = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_*"
USB_VENDOR_ID = 0x1A86
USB_PRODUCT_ID = 0x55D3
CALIBRATION_TORQUE_VALUE = 128

# Deploy-time hard override for which serial device to use, e.g. when
# multiple USB-serial adapters are plugged in and auto-detect/the saved
# profile port might grab the wrong one. Set via the SERVO_CONTROLLER_PORT
# env var (see deploy/docker-compose.yml) - when set, it always wins over
# whatever port is saved in the active profile.
SERVO_CONTROLLER_PORT_ENV_VAR = "SERVO_CONTROLLER_PORT"

DATA_DIR = BASE_DIR / "data"
ANIMATION_DIR = DATA_DIR / "animations"
TIMELINE_DIR = DATA_DIR / "timelines"
CONFIG_PATH = DATA_DIR / "servo_config.json"
DEV_MODE_PATH = DATA_DIR / "dev_mode.json"
LOGS_DIR = DATA_DIR / "logs"
LOG_PATH = LOGS_DIR / "actions.log"
for directory in (DATA_DIR, ANIMATION_DIR, TIMELINE_DIR, LOGS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("servo_console")
DEFAULT_PROFILE_NAME = "default"


@dataclass(frozen=True)
class ServoSpec:
    name: str
    id: int
    min: int
    max: int
    init: int
    speed: int
    acceleration: int
    model: str


def log_action(action: str, **details: Any) -> None:
    payload = {"action": action, **details}
    logger.info(json.dumps(payload, sort_keys=True))


def _atomic_write_json(path: Path, data: Any) -> None:
    # Writing straight to `path` in "w" mode truncates it to 0 bytes before
    # a single byte of new content is written - a kill (SIGKILL, power
    # loss) mid-write leaves an empty/corrupt file behind, which then
    # breaks every subsequent read of it. Write to a sibling temp file and
    # rename it into place instead: the rename is atomic, so `path` is
    # always either the old complete content or the new complete content,
    # never a partial write.
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as tmp_file:
        json.dump(data, tmp_file, indent=2)
    tmp_path.replace(path)


def _safe_name(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip()
    )
    return cleaned or f"item_{int(time.time())}"


def _ensure_servo_specs(items: list[dict[str, Any]]) -> list[ServoSpec]:
    specs: list[ServoSpec] = []
    seen_names: set[str] = set()
    seen_ids: set[int] = set()
    for item in items:
        name = _safe_name(str(item["name"]))
        servo_id = int(item["id"])
        spec = ServoSpec(
            name=name,
            id=servo_id,
            min=int(item["min"]),
            max=int(item["max"]),
            init=int(item["init"]),
            speed=int(item.get("speed", 0)),
            acceleration=int(item.get("acceleration", 0)),
            model=str(item.get("model", "")),
        )
        if spec.min > spec.max:
            raise ValueError(f"{spec.name}: min must be <= max")
        if spec.init < spec.min or spec.init > spec.max:
            raise ValueError(f"{spec.name}: init must be inside min/max")
        if name in seen_names:
            raise ValueError(f"Duplicate servo name: {name}")
        if servo_id in seen_ids:
            raise ValueError(f"Duplicate servo id: {servo_id}")
        seen_names.add(name)
        seen_ids.add(servo_id)
        specs.append(spec)
    return specs


def default_profile_data() -> dict[str, Any]:
    return {
        "port": None,
        "baudrate": BAUDRATE,
        "servos": [dict(item) for item in DEFAULT_SERVO_CONFIG],
    }


def _normalize_profile_data(profile_data: dict[str, Any]) -> dict[str, Any]:
    specs = _ensure_servo_specs(profile_data.get("servos", []))
    return {
        "port": profile_data.get("port"),
        "baudrate": int(profile_data.get("baudrate", BAUDRATE)),
        "servos": [asdict(spec) for spec in specs],
    }


def load_config_store() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        store = {
            "active_profile": DEFAULT_PROFILE_NAME,
            "profiles": {DEFAULT_PROFILE_NAME: default_profile_data()},
        }
        save_config_store(store)
        return store

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            raw_data = json.load(config_file)
    except (json.JSONDecodeError, OSError) as exc:
        log_action("config_store_corrupt", path=str(CONFIG_PATH), error=str(exc))
        store = {
            "active_profile": DEFAULT_PROFILE_NAME,
            "profiles": {DEFAULT_PROFILE_NAME: default_profile_data()},
        }
        save_config_store(store)
        return store

    if "profiles" not in raw_data:
        migrated = {
            "active_profile": DEFAULT_PROFILE_NAME,
            "profiles": {
                DEFAULT_PROFILE_NAME: {
                    "port": None,
                    "baudrate": BAUDRATE,
                    "servos": raw_data.get("servos", DEFAULT_SERVO_CONFIG),
                }
            },
        }
        save_config_store(migrated)
        return migrated

    active_profile = raw_data.get("active_profile") or DEFAULT_PROFILE_NAME
    profiles = raw_data.get("profiles", {})
    if not profiles:
        profiles = {DEFAULT_PROFILE_NAME: default_profile_data()}
        active_profile = DEFAULT_PROFILE_NAME

    normalized_profiles = {
        _safe_name(name): _normalize_profile_data(profile_data)
        for name, profile_data in profiles.items()
    }
    if active_profile not in normalized_profiles:
        active_profile = next(iter(normalized_profiles))

    store = {"active_profile": active_profile, "profiles": normalized_profiles}
    save_config_store(store)
    return store


def save_config_store(store: dict[str, Any]) -> None:
    normalized_profiles = {
        _safe_name(name): _normalize_profile_data(profile_data)
        for name, profile_data in store["profiles"].items()
    }
    active_profile = store.get("active_profile") or next(iter(normalized_profiles))
    if active_profile not in normalized_profiles:
        active_profile = next(iter(normalized_profiles))
    _atomic_write_json(
        CONFIG_PATH,
        {"active_profile": active_profile, "profiles": normalized_profiles},
    )


def get_active_profile_store() -> tuple[dict[str, Any], str, dict[str, Any]]:
    store = load_config_store()
    active_name = store["active_profile"]
    return store, active_name, store["profiles"][active_name]


def list_available_ports() -> list[dict[str, Any]]:
    ports: list[dict[str, Any]] = []
    for port in list_ports.comports():
        ports.append(
            {
                "device": port.device,
                "description": port.description,
                "manufacturer": port.manufacturer,
                "serial_number": port.serial_number,
                "vid": f"{port.vid:04x}" if port.vid is not None else None,
                "pid": f"{port.pid:04x}" if port.pid is not None else None,
                "hwid": port.hwid,
            }
        )
    return ports


def load_animation_frames(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Animation not found: {path.name}")
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def save_animation_frames(
    name: str, servo_specs: list[ServoSpec], frames: list[dict[str, Any]]
) -> Path:
    if not frames:
        raise ValueError("Animation needs at least one frame.")
    safe_name = _safe_name(name)
    path = ANIMATION_DIR / f"{safe_name}.csv"
    fieldnames = ["elapsed_seconds"] + [spec.name for spec in servo_specs]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for frame in frames:
            row = {"elapsed_seconds": round(float(frame["elapsed_seconds"]), 4)}
            for spec in servo_specs:
                if spec.name not in frame:
                    raise ValueError(
                        f"Missing servo value for {spec.name} in via point."
                    )
                row[spec.name] = int(frame[spec.name])
            writer.writerow(row)
    return path


def save_timeline(name: str, items: list[dict[str, Any]]) -> Path:
    safe_name = _safe_name(name)
    path = TIMELINE_DIR / f"{safe_name}.json"
    _atomic_write_json(path, {"name": safe_name, "items": items})
    return path


def list_saved_timelines() -> list[dict[str, Any]]:
    timelines: list[dict[str, Any]] = []
    for path in sorted(TIMELINE_DIR.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as timeline_file:
                timelines.append(json.load(timeline_file))
        except (json.JSONDecodeError, OSError) as exc:
            # One corrupt file (e.g. from a kill mid-write) shouldn't take
            # down the whole listing - skip it and keep going.
            log_action("timeline_file_corrupt", path=str(path), error=str(exc))
    return timelines


class ServoController:
    def __init__(
        self,
        servo_specs: list[ServoSpec],
        baudrate: int = BAUDRATE,
        preferred_port: str | None = None,
    ) -> None:
        self._servo_specs = list(servo_specs)
        self.baudrate = baudrate
        self.preferred_port = preferred_port
        self.lock = threading.RLock()
        # Populated by read_positions(): name -> last read error message,
        # for servos that failed to respond on the most recent poll.
        # Servos not in this dict responded fine last time.
        self.last_read_errors: dict[str, str] = {}
        self.port_path = self._detect_port()
        self.port_handler = PortHandler(self.port_path)
        self.packet_handler = sms_sts(self.port_handler)
        self._open_port()

    @property
    def servo_specs(self) -> list[ServoSpec]:
        return list(self._servo_specs)

    def replace_specs(self, servo_specs: list[ServoSpec]) -> None:
        with self.lock:
            self._servo_specs = list(servo_specs)

    def reconnect(
        self, preferred_port: str | None = None, baudrate: int | None = None
    ) -> None:
        with self.lock:
            try:
                if getattr(self, "port_handler", None) and self.port_handler.is_open:
                    self.port_handler.closePort()
            except Exception:
                pass
            if baudrate is not None:
                self.baudrate = int(baudrate)
            self.preferred_port = preferred_port
            self.port_path = self._detect_port()
            self.port_handler = PortHandler(self.port_path)
            self.packet_handler = sms_sts(self.port_handler)
            self._open_port()

    def _detect_port(self) -> str:
        if self.preferred_port:
            return self.preferred_port
        by_id_matches = sorted(glob.glob(SERIAL_BY_ID_GLOB))
        if by_id_matches:
            return by_id_matches[0]

        for port in list_ports.comports():
            if port.vid == USB_VENDOR_ID and port.pid == USB_PRODUCT_ID:
                return port.device

        raise RuntimeError(
            "Could not auto-detect the Feetech USB serial adapter. "
            "Expected /dev/serial/by-id/usb-1a86_USB_Single_Serial_* or VID:PID 1a86:55d3."
        )

    def _open_port(self) -> None:
        if not self.port_handler.openPort():
            raise RuntimeError(f"Failed to open servo port: {self.port_path}")
        if not self.port_handler.setBaudRate(self.baudrate):
            raise RuntimeError(
                f"Failed to set baudrate {self.baudrate} on {self.port_path}"
            )

    def _check_result(self, comm_result: int, error: int, servo_name: str) -> None:
        if comm_result != COMM_SUCCESS:
            raise RuntimeError(
                f"{servo_name}: {self.packet_handler.getTxRxResult(comm_result)}"
            )
        if error != 0:
            raise RuntimeError(
                f"{servo_name}: {self.packet_handler.getRxPacketError(error)}"
            )

    def _spec_by_name(self, name: str) -> ServoSpec:
        for spec in self._servo_specs:
            if spec.name == name:
                return spec
        raise KeyError(f"Unknown servo: {name}")

    def list_servos(self) -> list[dict[str, Any]]:
        return [asdict(spec) for spec in self._servo_specs]

    def read_positions(self) -> dict[str, int]:
        # One servo not responding (disconnected, powered off, bad wiring)
        # must not stop the others from being read - isolate failures
        # per-servo instead of letting the first one abort the whole poll.
        # The next poll cycle (servo_tester polls every 250ms) naturally
        # retries every servo, including ones that failed last time.
        positions: dict[str, int] = {}
        errors: dict[str, str] = {}
        with self.lock:
            for spec in self._servo_specs:
                try:
                    position, comm_result, error = self.packet_handler.ReadPos(spec.id)
                    self._check_result(comm_result, error, spec.name)
                    positions[spec.name] = int(position)
                except Exception as exc:
                    errors[spec.name] = str(exc)
            self.last_read_errors = errors
        return positions

    def write_torque_raw(self, name: str, value: int) -> None:
        spec = self._spec_by_name(name)
        with self.lock:
            comm_result, error = self.packet_handler.write1ByteTxRx(
                spec.id, SMS_STS_TORQUE_ENABLE, int(value)
            )
            self._check_result(comm_result, error, name)

    def set_torque(self, name: str, enabled: bool) -> None:
        self.write_torque_raw(name, 1 if enabled else 0)

    def set_torque_all(self, enabled: bool) -> dict[str, bool]:
        applied: dict[str, bool] = {}
        for spec in self._servo_specs:
            self.set_torque(spec.name, enabled)
            applied[spec.name] = enabled
        return applied

    def enable_calibration_mode(self, name: str) -> None:
        self.write_torque_raw(name, CALIBRATION_TORQUE_VALUE)

    def recover_servo_fault(self, name: str) -> None:
        # A quick torque cycle is a practical way to clear transient status faults
        # without taking down the whole timeline thread.
        try:
            self.write_torque_raw(name, 0)
            time.sleep(0.05)
            self.write_torque_raw(name, 1)
        except Exception as recovery_error:
            log_action("servo_recovery_failed", servo=name, error=str(recovery_error))

    def move_many(
        self,
        targets: dict[str, int],
        speed: int | None = None,
        acc: int | None = None,
        continue_on_error: bool = False,
    ) -> dict[str, int]:
        applied: dict[str, int] = {}
        with self.lock:
            for name, position in targets.items():
                spec = self._spec_by_name(name)
                clamped = max(spec.min, min(spec.max, int(position)))
                move_speed = spec.speed if speed is None else int(speed)
                move_acc = spec.acceleration if acc is None else int(acc)
                try:
                    torque_result, torque_error = self.packet_handler.write1ByteTxRx(
                        spec.id, SMS_STS_TORQUE_ENABLE, 1
                    )
                    self._check_result(torque_result, torque_error, name)
                    comm_result, error = self.packet_handler.WritePosEx(
                        spec.id, clamped, move_speed, move_acc
                    )
                    self._check_result(comm_result, error, name)
                    applied[name] = clamped
                except Exception as move_error:
                    log_action(
                        "servo_move_failed",
                        servo=name,
                        target=clamped,
                        speed=move_speed,
                        acceleration=move_acc,
                        error=str(move_error),
                    )
                    self.recover_servo_fault(name)
                    if not continue_on_error:
                        raise
        return applied

    def move_to_init_pose(
        self, speed: int | None = None, acc: int | None = None
    ) -> dict[str, int]:
        return self.move_many(
            {spec.name: spec.init for spec in self._servo_specs}, speed=speed, acc=acc
        )


class AnimationRecorder:
    def __init__(self, controller: ServoController, output_dir: Path) -> None:
        self.controller = controller
        self.output_dir = output_dir
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._current_name: str | None = None
        self._current_path: Path | None = None

    @property
    def is_recording(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "is_recording": self.is_recording,
                "name": self._current_name,
                "path": str(self._current_path) if self._current_path else None,
            }

    def start(self, name: str) -> Path:
        safe_name = _safe_name(name)
        with self._lock:
            if self.is_recording:
                raise RuntimeError("A recording is already in progress.")
            self.controller.set_torque_all(False)
            ui_state["torque_enabled"] = False
            path = self.output_dir / f"{safe_name}.csv"
            self._stop_event.clear()
            self._current_name = safe_name
            self._current_path = path
            self._thread = threading.Thread(
                target=self._record_loop, args=(path,), daemon=True
            )
            self._thread.start()
            log_action("animation_recording_started", name=safe_name, path=str(path))
            return path

    def stop(self) -> Path | None:
        with self._lock:
            if not self.is_recording:
                return self._current_path
            thread = self._thread
            self._stop_event.set()
        if thread:
            thread.join(timeout=5)
        with self._lock:
            finished_path = self._current_path
            finished_name = self._current_name
            self._thread = None
            self._current_name = None
            self._current_path = None
            self._stop_event.clear()
        if finished_path:
            log_action(
                "animation_recording_stopped",
                name=finished_name,
                path=str(finished_path),
            )
        return finished_path

    def _record_loop(self, path: Path) -> None:
        started_at = time.monotonic()
        fieldnames = ["elapsed_seconds"] + [
            spec.name for spec in self.controller.servo_specs
        ]
        with path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            while not self._stop_event.is_set():
                positions = self.controller.read_positions()
                row = {"elapsed_seconds": round(time.monotonic() - started_at, 4)}
                row.update(positions)
                writer.writerow(row)
                csv_file.flush()
                time.sleep(RECORD_INTERVAL_SECONDS)


class TimelinePlayer:
    def __init__(self, controller: ServoController, animation_dir: Path) -> None:
        self.controller = controller
        self.animation_dir = animation_dir
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._state_lock = threading.RLock()
        self._state: dict[str, Any] = {
            "is_playing": False,
            "loop": False,
            "timeline_name": None,
            "items": [],
        }

    @property
    def is_playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            return dict(self._state)

    def play(self, timeline_name: str, items: list[dict[str, Any]], loop: bool) -> None:
        with self._state_lock:
            if self.is_playing:
                raise RuntimeError("A timeline is already playing.")
            self._stop_event.clear()
            self._state = {
                "is_playing": True,
                "loop": loop,
                "timeline_name": timeline_name,
                "items": items,
            }
            self._thread = threading.Thread(
                target=self._play_loop, args=(timeline_name, items, loop), daemon=True
            )
            self._thread.start()
        log_action("timeline_started", name=timeline_name, loop=loop, items=items)

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread:
            thread.join(timeout=5)
        with self._state_lock:
            timeline_name = self._state.get("timeline_name")
            self._thread = None
            self._state = {
                "is_playing": False,
                "loop": False,
                "timeline_name": None,
                "items": [],
            }
            self._stop_event.clear()
        log_action("timeline_stopped", name=timeline_name)

    def _play_loop(
        self, timeline_name: str, items: list[dict[str, Any]], loop: bool
    ) -> None:
        try:
            while not self._stop_event.is_set():
                for item in items:
                    animation_name = item["animation"]
                    repeat = max(1, int(item.get("repeat", 1)))
                    for _ in range(repeat):
                        try:
                            self._play_animation(animation_name)
                        except Exception as playback_error:
                            log_action(
                                "timeline_animation_error",
                                timeline=timeline_name,
                                animation=animation_name,
                                error=str(playback_error),
                            )
                        if self._stop_event.is_set():
                            return
                if not loop:
                    return
        except Exception as loop_error:
            log_action(
                "timeline_loop_error", timeline=timeline_name, error=str(loop_error)
            )
        finally:
            with self._state_lock:
                self._thread = None
                self._state = {
                    "is_playing": False,
                    "loop": False,
                    "timeline_name": timeline_name,
                    "items": items,
                }
                self._stop_event.clear()

    def _play_animation(self, animation_name: str) -> None:
        frames = load_animation_frames(self.animation_dir / f"{animation_name}.csv")
        previous_time = 0.0
        for frame in frames:
            if self._stop_event.is_set():
                return
            current_time = float(frame["elapsed_seconds"])
            delay = max(0.0, current_time - previous_time)
            if delay:
                time.sleep(delay)
            targets = {
                spec.name: int(frame[spec.name])
                for spec in self.controller.servo_specs
                if spec.name in frame and frame[spec.name] not in {"", None}
            }
            self.controller.move_many(targets, continue_on_error=True)
            previous_time = current_time


runtime_lock = threading.RLock()
runtime: dict[str, Any] = {
    "controller": None,
    "recorder": None,
    "timeline_player": None,
    "profile_name": None,
}
ui_state: dict[str, Any] = {"torque_enabled": None}


def get_runtime() -> tuple[ServoController, AnimationRecorder, TimelinePlayer]:
    with runtime_lock:
        _, active_name, active_profile = get_active_profile_store()
        controller = runtime["controller"]
        recorder = runtime["recorder"]
        timeline_player = runtime["timeline_player"]
        if (
            controller
            and recorder
            and timeline_player
            and runtime["profile_name"] == active_name
        ):
            return controller, recorder, timeline_player

        if timeline_player and timeline_player.is_playing:
            timeline_player.stop()
        if recorder and recorder.is_recording:
            recorder.stop()

        specs = _ensure_servo_specs(active_profile["servos"])
        port_override = os.environ.get(SERVO_CONTROLLER_PORT_ENV_VAR) or None
        controller = ServoController(
            specs,
            baudrate=int(active_profile.get("baudrate", BAUDRATE)),
            preferred_port=port_override or active_profile.get("port"),
        )
        recorder = AnimationRecorder(controller, ANIMATION_DIR)
        timeline_player = TimelinePlayer(controller, ANIMATION_DIR)
        runtime["controller"] = controller
        runtime["recorder"] = recorder
        runtime["timeline_player"] = timeline_player
        runtime["profile_name"] = active_name
        return controller, recorder, timeline_player


def reset_runtime() -> None:
    with runtime_lock:
        recorder = runtime.get("recorder")
        timeline_player = runtime.get("timeline_player")
        if timeline_player and timeline_player.is_playing:
            timeline_player.stop()
        if recorder and recorder.is_recording:
            recorder.stop()
        runtime["controller"] = None
        runtime["recorder"] = None
        runtime["timeline_player"] = None
        runtime["profile_name"] = None
        ui_state["torque_enabled"] = None


def set_active_profile(profile_name: str) -> None:
    store = load_config_store()
    safe_name = _safe_name(profile_name)
    if safe_name not in store["profiles"]:
        raise ValueError(f"Unknown profile: {profile_name}")
    store["active_profile"] = safe_name
    save_config_store(store)
    reset_runtime()
    log_action("profile_switched", profile=safe_name)


def update_active_profile(profile_data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    store, active_name, _ = get_active_profile_store()
    store["profiles"][active_name] = _normalize_profile_data(profile_data)
    save_config_store(store)
    reset_runtime()
    log_action("active_profile_updated", profile=active_name)
    return active_name, store["profiles"][active_name]


def update_runtime_specs(specs: list[ServoSpec]) -> None:
    store, active_name, active_profile = get_active_profile_store()
    active_profile["servos"] = [asdict(spec) for spec in specs]
    store["profiles"][active_name] = _normalize_profile_data(active_profile)
    save_config_store(store)
    controller, _, _ = get_runtime()
    controller.replace_specs(specs)
    log_action("servo_config_updated", profile=active_name, servo_count=len(specs))


def load_dev_mode() -> bool:
    if not DEV_MODE_PATH.exists():
        return False
    try:
        with DEV_MODE_PATH.open("r", encoding="utf-8") as dev_mode_file:
            return bool(json.load(dev_mode_file).get("enabled", False))
    except (json.JSONDecodeError, OSError):
        return False


def save_dev_mode(enabled: bool) -> None:
    _atomic_write_json(DEV_MODE_PATH, {"enabled": bool(enabled)})


def read_logs(limit: int = 200) -> list[str]:
    if not LOG_PATH.exists():
        return []
    with LOG_PATH.open("r", encoding="utf-8") as log_file:
        lines = log_file.readlines()
    return [line.rstrip("\n") for line in lines[-limit:]]


app = Flask(__name__)


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/dev")
def dev_page() -> str:
    return render_template("dev.html")


@app.get("/api/dev-mode")
def get_dev_mode():
    return jsonify({"enabled": load_dev_mode()})


@app.post("/api/dev-mode")
def set_dev_mode():
    payload = request.get_json(force=True) or {}
    enabled = bool(payload.get("enabled", False))
    save_dev_mode(enabled)
    log_action("dev_mode_changed", enabled=enabled)
    return jsonify({"ok": True, "enabled": enabled})


@app.get("/api/config")
def get_config():
    controller, recorder, timeline_player = get_runtime()
    store, active_name, active_profile = get_active_profile_store()
    return jsonify(
        {
            "servos": controller.list_servos(),
            "connection": {
                "port": controller.port_path,
                "baudrate": controller.baudrate,
                "available_ports": list_available_ports(),
                "selected_port": active_profile.get("port"),
            },
            "defaults": {"speed": DEFAULT_SPEED, "acc": DEFAULT_ACC},
            "recording": recorder.status(),
            "timeline": timeline_player.status(),
            "logs_path": str(LOG_PATH),
            "torque_enabled": ui_state["torque_enabled"],
            "active_profile": active_name,
            "profiles": sorted(store["profiles"].keys()),
            "dev_mode": load_dev_mode(),
        }
    )


@app.get("/api/status")
def get_status():
    controller, recorder, timeline_player = get_runtime()
    positions = controller.read_positions()
    return jsonify(
        {
            "positions": positions,
            "servo_errors": controller.last_read_errors,
            "recording": recorder.status(),
            "timeline": timeline_player.status(),
            "torque_enabled": ui_state["torque_enabled"],
        }
    )


@app.get("/api/logs")
def get_logs():
    limit = int(request.args.get("limit", 200))
    return jsonify({"logs": read_logs(limit), "path": str(LOG_PATH)})


@app.get("/api/servos")
def get_servos():
    controller, _, _ = get_runtime()
    return jsonify({"servos": controller.list_servos()})


@app.get("/api/ports")
def get_ports():
    return jsonify({"ports": list_available_ports()})


@app.get("/api/profiles")
def get_profiles():
    store, active_name, _ = get_active_profile_store()
    return jsonify(
        {"profiles": sorted(store["profiles"].keys()), "active_profile": active_name}
    )


@app.post("/api/profiles/switch")
def switch_profile():
    payload = request.get_json(force=True) or {}
    profile_name = payload.get("name", "")
    if not profile_name:
        return jsonify({"ok": False, "error": "Profile name is required."}), 400
    set_active_profile(profile_name)
    controller, _, _ = get_runtime()
    return jsonify(
        {"ok": True, "active_profile": profile_name, "port": controller.port_path}
    )


@app.post("/api/profiles")
def create_or_update_profile():
    payload = request.get_json(force=True) or {}
    name = payload.get("name", "")
    if not name:
        return jsonify({"ok": False, "error": "Profile name is required."}), 400
    safe_name = _safe_name(name)
    store = load_config_store()
    profile = payload.get("profile")
    if profile:
        store["profiles"][safe_name] = _normalize_profile_data(profile)
    else:
        _, active_name, active_profile = get_active_profile_store()
        source_profile = (
            store["profiles"][active_name]
            if active_name in store["profiles"]
            else active_profile
        )
        store["profiles"][safe_name] = _normalize_profile_data(source_profile)
    if payload.get("activate", False):
        store["active_profile"] = safe_name
    save_config_store(store)
    if payload.get("activate", False):
        reset_runtime()
    log_action(
        "profile_saved",
        profile=safe_name,
        activated=bool(payload.get("activate", False)),
    )
    return jsonify(
        {
            "ok": True,
            "profiles": sorted(store["profiles"].keys()),
            "active_profile": store["active_profile"],
        }
    )


@app.delete("/api/profiles/<name>")
def delete_profile(name: str):
    safe_name = _safe_name(name)
    store = load_config_store()
    if safe_name not in store["profiles"]:
        return jsonify({"ok": False, "error": f"Profile not found: {name}"}), 404
    if len(store["profiles"]) == 1:
        return jsonify({"ok": False, "error": "At least one profile must remain."}), 400
    del store["profiles"][safe_name]
    if store["active_profile"] == safe_name:
        store["active_profile"] = next(iter(store["profiles"]))
        reset_runtime()
    save_config_store(store)
    log_action("profile_deleted", profile=safe_name)
    return jsonify(
        {
            "ok": True,
            "profiles": sorted(store["profiles"].keys()),
            "active_profile": store["active_profile"],
        }
    )


@app.get("/api/profiles/export/<name>")
def export_profile(name: str):
    safe_name = _safe_name(name)
    store = load_config_store()
    if safe_name not in store["profiles"]:
        return jsonify({"ok": False, "error": f"Profile not found: {name}"}), 404
    export_path = DATA_DIR / f"{safe_name}_profile.json"
    with export_path.open("w", encoding="utf-8") as export_file:
        json.dump(
            {"name": safe_name, "profile": store["profiles"][safe_name]},
            export_file,
            indent=2,
        )
    log_action("profile_exported", profile=safe_name, path=str(export_path))
    return send_file(
        export_path,
        as_attachment=True,
        download_name=export_path.name,
        mimetype="application/json",
    )


@app.post("/api/profiles/import")
def import_profile():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return (
            jsonify({"ok": False, "error": "Choose a profile JSON file to import."}),
            400,
        )
    imported = json.load(upload.stream)
    name = _safe_name(imported.get("name", Path(secure_filename(upload.filename)).stem))
    profile = _normalize_profile_data(imported.get("profile", imported))
    store = load_config_store()
    store["profiles"][name] = profile
    if imported.get("activate", False):
        store["active_profile"] = name
        reset_runtime()
    save_config_store(store)
    log_action("profile_imported", profile=name)
    return jsonify(
        {
            "ok": True,
            "profiles": sorted(store["profiles"].keys()),
            "active_profile": store["active_profile"],
        }
    )


@app.post("/api/connection")
def update_connection():
    payload = request.get_json(force=True) or {}
    port = payload.get("port")
    baudrate = int(payload.get("baudrate", BAUDRATE))
    store, active_name, active_profile = get_active_profile_store()
    active_profile["port"] = port or None
    active_profile["baudrate"] = baudrate
    store["profiles"][active_name] = _normalize_profile_data(active_profile)
    save_config_store(store)
    reset_runtime()
    controller, _, _ = get_runtime()
    log_action(
        "connection_updated",
        profile=active_name,
        port=controller.port_path,
        baudrate=controller.baudrate,
    )
    return jsonify(
        {"ok": True, "port": controller.port_path, "baudrate": controller.baudrate}
    )


@app.post("/api/servos/config")
def save_servos_config():
    payload = request.get_json(force=True) or {}
    specs = _ensure_servo_specs(payload.get("servos", []))
    update_runtime_specs(specs)
    store, active_name, _ = get_active_profile_store()
    return jsonify(
        {
            "ok": True,
            "servos": [asdict(spec) for spec in specs],
            "active_profile": active_name,
            "profiles": sorted(store["profiles"].keys()),
        }
    )


@app.post("/api/servos/config/add")
def add_servo_config():
    controller, _, _ = get_runtime()
    payload = request.get_json(force=True) or {}
    existing = [asdict(spec) for spec in controller.servo_specs]
    existing.append(payload)
    specs = _ensure_servo_specs(existing)
    update_runtime_specs(specs)
    log_action("servo_added", servo=_safe_name(str(payload.get("name", ""))))
    store, active_name, _ = get_active_profile_store()
    return jsonify(
        {
            "ok": True,
            "servos": [asdict(spec) for spec in specs],
            "active_profile": active_name,
            "profiles": sorted(store["profiles"].keys()),
        }
    )


@app.delete("/api/servos/<name>")
def delete_servo_config(name: str):
    controller, _, _ = get_runtime()
    filtered = [asdict(spec) for spec in controller.servo_specs if spec.name != name]
    if len(filtered) == len(controller.servo_specs):
        return jsonify({"ok": False, "error": f"Servo not found: {name}"}), 404
    specs = _ensure_servo_specs(filtered)
    update_runtime_specs(specs)
    log_action("servo_deleted", servo=name)
    store, active_name, _ = get_active_profile_store()
    return jsonify(
        {
            "ok": True,
            "servos": [asdict(spec) for spec in specs],
            "active_profile": active_name,
            "profiles": sorted(store["profiles"].keys()),
        }
    )


@app.post("/api/servos/move")
def move_servos():
    controller, _, _ = get_runtime()
    payload = request.get_json(force=True) or {}
    targets = payload.get("targets", {})
    speed = payload.get("speed")
    acc = payload.get("acc")
    applied = controller.move_many(
        targets,
        speed=int(speed) if speed is not None else None,
        acc=int(acc) if acc is not None else None,
    )
    ui_state["torque_enabled"] = True
    return jsonify({"ok": True, "applied": applied})


@app.post("/api/servos/home")
def move_home():
    controller, _, _ = get_runtime()
    payload = request.get_json(silent=True) or {}
    speed = payload.get("speed")
    acc = payload.get("acc")
    applied = controller.move_to_init_pose(
        speed=int(speed) if speed is not None else None,
        acc=int(acc) if acc is not None else None,
    )
    ui_state["torque_enabled"] = True
    log_action("servos_moved_home", targets=applied)
    return jsonify({"ok": True, "applied": applied})


@app.post("/api/servos/torque")
def set_torque():
    controller, _, _ = get_runtime()
    payload = request.get_json(force=True) or {}
    enabled = bool(payload.get("enabled", False))
    names = payload.get("names")
    if names:
        applied = {}
        for name in names:
            controller.set_torque(name, enabled)
            applied[name] = enabled
    else:
        applied = controller.set_torque_all(enabled)
        ui_state["torque_enabled"] = enabled
    log_action("servo_torque_changed", enabled=enabled, names=names or "all")
    return jsonify({"ok": True, "applied": applied, "enabled": enabled})


@app.post("/api/servos/set-init/<name>")
def set_servo_init(name: str):
    controller, _, _ = get_runtime()
    controller.enable_calibration_mode(name)
    current_positions = controller.read_positions()
    if name not in current_positions:
        detail = controller.last_read_errors.get(name, "no response")
        raise RuntimeError(f"{name}: failed to read position ({detail})")
    new_mid = int(current_positions[name])
    specs = []
    for spec in controller.servo_specs:
        if spec.name == name:
            if new_mid < spec.min or new_mid > spec.max:
                raise ValueError(f"{name}: mid position must stay within min/max")
            specs.append(
                ServoSpec(
                    name=spec.name,
                    id=spec.id,
                    min=spec.min,
                    max=spec.max,
                    init=new_mid,
                    speed=spec.speed,
                    acceleration=spec.acceleration,
                    model=spec.model,
                )
            )
        else:
            specs.append(spec)
    update_runtime_specs(specs)
    log_action(
        "servo_init_updated",
        servo=name,
        init=new_mid,
        torque_value=CALIBRATION_TORQUE_VALUE,
    )
    return jsonify(
        {
            "ok": True,
            "servo": name,
            "init": new_mid,
            "servos": [asdict(spec) for spec in specs],
        }
    )


@app.post("/api/animations/start")
def start_animation_recording():
    _, recorder, _ = get_runtime()
    payload = request.get_json(force=True) or {}
    name = payload.get("name", "")
    if not name:
        return jsonify({"ok": False, "error": "Animation name is required."}), 400
    path = recorder.start(name)
    return jsonify({"ok": True, "path": str(path), "recording": recorder.status()})


@app.post("/api/animations/stop")
def stop_animation_recording():
    _, recorder, _ = get_runtime()
    path = recorder.stop()
    return jsonify(
        {
            "ok": True,
            "path": str(path) if path else None,
            "recording": recorder.status(),
        }
    )


@app.post("/api/animations/via-points")
def save_via_point_animation():
    controller, _, _ = get_runtime()
    payload = request.get_json(force=True) or {}
    name = payload.get("name", "")
    frames = payload.get("frames", [])
    if not name:
        return jsonify({"ok": False, "error": "Animation name is required."}), 400
    path = save_animation_frames(name, controller.servo_specs, frames)
    log_action(
        "via_point_animation_saved",
        name=_safe_name(name),
        frame_count=len(frames),
        path=str(path),
    )
    return jsonify({"ok": True, "path": str(path), "name": _safe_name(name)})


@app.get("/api/animations")
def list_animations():
    animations = []
    for path in sorted(ANIMATION_DIR.glob("*.csv")):
        animations.append(
            {
                "name": path.stem,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "updated_at": path.stat().st_mtime,
            }
        )
    return jsonify({"animations": animations})


@app.get("/api/animations/export/<name>")
def export_animation(name: str):
    path = ANIMATION_DIR / f"{_safe_name(name)}.csv"
    if not path.exists():
        return jsonify({"ok": False, "error": f"Animation not found: {name}"}), 404
    log_action("animation_exported", animation=name)
    return send_file(
        path, as_attachment=True, download_name=path.name, mimetype="text/csv"
    )


@app.post("/api/animations/import")
def import_animation():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return (
            jsonify({"ok": False, "error": "Choose a CSV animation file to import."}),
            400,
        )
    safe_name = _safe_name(Path(secure_filename(upload.filename)).stem)
    target_path = ANIMATION_DIR / f"{safe_name}.csv"
    upload.save(target_path)
    log_action("animation_imported", animation=safe_name, path=str(target_path))
    return jsonify({"ok": True, "name": safe_name, "path": str(target_path)})


@app.delete("/api/animations/<name>")
def delete_animation(name: str):
    path = ANIMATION_DIR / f"{_safe_name(name)}.csv"
    if not path.exists():
        return jsonify({"ok": False, "error": f"Animation not found: {name}"}), 404
    path.unlink()
    log_action("animation_deleted", animation=name)
    return jsonify({"ok": True, "deleted": name})


@app.post("/api/animations/play/<name>")
def play_animation(name: str):
    _, _, timeline_player = get_runtime()
    if timeline_player.is_playing:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Stop the active timeline before playing a single animation.",
                }
            ),
            409,
        )
    timeline_player.play(
        name, [{"animation": _safe_name(name), "repeat": 1}], loop=False
    )
    log_action("animation_play_requested", animation=name)
    return jsonify({"ok": True, "timeline": timeline_player.status()})


@app.get("/api/timelines")
def get_timelines():
    return jsonify({"timelines": list_saved_timelines()})


@app.delete("/api/timelines/<name>")
def delete_timeline(name: str):
    path = TIMELINE_DIR / f"{_safe_name(name)}.json"
    if not path.exists():
        return jsonify({"ok": False, "error": f"Timeline not found: {name}"}), 404
    path.unlink()
    log_action("timeline_deleted", timeline=name)
    return jsonify({"ok": True, "deleted": name})


@app.post("/api/timelines")
def create_timeline():
    payload = request.get_json(force=True) or {}
    name = payload.get("name", "")
    items = payload.get("items", [])
    if not name:
        return jsonify({"ok": False, "error": "Timeline name is required."}), 400
    if not items:
        return (
            jsonify({"ok": False, "error": "Timeline needs at least one animation."}),
            400,
        )
    path = save_timeline(name, items)
    log_action("timeline_saved", timeline=_safe_name(name), items=items)
    return jsonify({"ok": True, "path": str(path)})


@app.post("/api/timelines/play")
def play_timeline():
    _, _, timeline_player = get_runtime()
    payload = request.get_json(force=True) or {}
    name = payload.get("name", "timeline")
    items = payload.get("items", [])
    loop = bool(payload.get("loop", False))
    if not items:
        return (
            jsonify({"ok": False, "error": "Timeline needs at least one animation."}),
            400,
        )
    timeline_player.play(name, items, loop)
    return jsonify({"ok": True, "timeline": timeline_player.status()})


@app.post("/api/timelines/stop")
def stop_timeline():
    _, _, timeline_player = get_runtime()
    timeline_player.stop()
    return jsonify({"ok": True, "timeline": timeline_player.status()})


@app.errorhandler(Exception)
def handle_error(error: Exception):
    log_action("error", message=str(error))
    return jsonify({"ok": False, "error": str(error)}), 500


if __name__ == "__main__":
    log_action("app_started", started_at=datetime.now().isoformat())
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
