#!/usr/bin/env python3
"""
Auto Calibration Script for STS3215 Servos (IDs: 51, 52, 53)
Supports QinHeng (1a86:55d3) and FTDI (0403:6014) USB adapters.
"""

import sys
import time
from pathlib import Path

# ── Try to import the SCServo SDK ────────────────────────────────────────────
try:
    sys.path.insert(0, ".")  # look in CWD first (place sdk there)
    from scservo_sdk import *  # standard install name
except ImportError:
    try:
        from SCServo_Python import *  # alternate package name
    except ImportError:
        print(
            "ERROR: SCServo SDK not found. Install it or place scservo_sdk/ "
            "next to this script."
        )
        sys.exit(1)

try:
    from serial.tools import list_ports
except ImportError:
    list_ports = None

# ── Register addresses ────────────────────────────────────────────────────────
ADDR_TORQUE_SWITCH = 0x28  # dec 40  – write 128 → current pos = 2047
ADDR_ACCELERATION = 0x29  # dec 41
ADDR_GOAL_POSITION_L = 0x2A  # dec 42  (2-byte, low first)
ADDR_RUNNING_SPEED_L = 0x2E  # dec 46  (2-byte)
ADDR_LOCK_MARK = 0x37  # dec 55  – 0=unlocked (EPROM writable)
ADDR_CURRENT_POSITION_L = 0x38  # dec 56  (2-byte read-only)
ADDR_PRESENT_VOLTAGE = 0x3E  # dec 62
ADDR_PRESENT_TEMPERATURE = 0x3F  # dec 63
ADDR_SERVO_STATUS = 0x41  # dec 65  – error flags
ADDR_MOVING = 0x42  # dec 66  – 1 while moving, 0 when stopped
ADDR_PRESENT_CURRENT_L = 0x45  # dec 69
ADDR_MIN_ANGLE_L = 0x09  # dec  9  (2-byte EPROM)
ADDR_MAX_ANGLE_L = 0x0B  # dec 11  (2-byte EPROM)

# Before-calibration register writes (image 1)
#   servo: {addr: value, ...}
PRE_CALIBRATION = {
    51: {0x10: 180, 0x23: 50, 0x24: 80, 0x26: 10, 0x1C: 50, 0x09: 0, 0x0B: 4095},
    52: {0x10: 280, 0x23: 50, 0x24: 80, 0x26: 10, 0x1C: 50, 0x09: 0, 0x0B: 4095},
    53: {0x10: 600, 0x23: 120, 0x24: 80, 0x26: 100, 0x1C: 80, 0x09: 0, 0x0B: 4095},
}

# After-calibration angle limits (image 2)
POST_CALIBRATION_LIMITS = {
    51: {"min": 1900, "max": 2170},
    52: {"min": 1650, "max": 2445},
    53: {"min": 1200, "max": 2910},
}

# Per-servo calibration direction and target
SERVO_CONFIG = {
    51: {"direction": "positive", "limit_goal": 4095, "settle_goal": 1875},
    52: {"direction": "negative", "limit_goal": 0, "settle_goal": 2510},
    53: {"direction": "negative", "limit_goal": 0, "settle_goal": 3000},
}

FINAL_INIT_POSITION = 2050
CALIBRATION_SPEED = 0
POSITION_TOLERANCE = 15
STILL_TIMEOUT_SEC = 0.15  # time with no movement = mechanical limit hit
POLL_INTERVAL_SEC = 0.02  # 50 Hz polling
MOTION_STOP_HOLD_SEC = 0.2
GOAL_STEP_SIZE = 300
BACKLASH_COMPENSATION = 30
FINAL_APPROACH_STEP = 20
FINAL_APPROACH_ATTEMPTS = 20
SERVO_MIN_POSITION = 0
SERVO_MAX_POSITION = 4095
ERROR_RECOVERY_WAIT_SEC = 1.0
MIN_PROGRESS_FOR_LIMIT_DETECTION = 8
DEBUG_LOGS = True
POSITION_READ_RETRIES = 10
STATUS_READ_RETRIES = 10
ERROR_CLEAR_RETRIES = 10
FAULT_CONFIRM_READS = 2
FAULT_CONFIRM_DELAY_SEC = 0.05


# ── Error flag helpers ────────────────────────────────────────────────────────
ERROR_FLAGS = {
    0x01: "Voltage Error",
    0x02: "Angle Error",
    0x04: "Overheat Error",
    0x08: "Current Error",
    0x20: "Overload Error",
}


def decode_errors(status_byte):
    errors = []
    for mask, name in ERROR_FLAGS.items():
        if status_byte & mask:
            errors.append(name)
    unknown = status_byte & ~sum(ERROR_FLAGS.keys())
    if unknown:
        errors.append(f"Unknown Error Bits (0x{unknown:02X})")
    return errors


def debug_log(message):
    if DEBUG_LOGS:
        print(f"[debug] {message}")


# ── Low-level helpers ─────────────────────────────────────────────────────────
def read_position(scs, scs_id):
    """Return (position, comm_result, error)."""
    last_result = COMM_RX_FAIL
    last_err = 0

    for attempt in range(1, POSITION_READ_RETRIES + 1):
        pos, result, err = scs.read2ByteTxRx(scs_id, ADDR_CURRENT_POSITION_L)
        if result == COMM_SUCCESS and SERVO_MIN_POSITION <= pos <= SERVO_MAX_POSITION:
            if attempt > 1:
                debug_log(
                    f"servo={scs_id} read_position recovered attempt={attempt} pos={pos}"
                )
            return pos, result, err

        debug_log(
            f"servo={scs_id} invalid_position_read attempt={attempt} "
            f"pos={pos} result={result} err={err}"
        )
        last_result = COMM_RX_CORRUPT if result == COMM_SUCCESS else result
        last_err = err
        time.sleep(POLL_INTERVAL_SEC)

    return 0, last_result, last_err


def read_moving_state(scs, scs_id):
    """Return (moving_flag, comm_result, error)."""
    moving, result, err = scs.read1ByteTxRx(scs_id, ADDR_MOVING)
    return moving, result, err


def read_status_with_retry(scs, servo_id):
    last_result = COMM_RX_FAIL
    last_err = 0
    last_status = 0

    for attempt in range(1, STATUS_READ_RETRIES + 1):
        status, result, err = scs.read1ByteTxRx(servo_id, ADDR_SERVO_STATUS)
        if result == COMM_SUCCESS:
            if attempt > 1:
                debug_log(
                    f"servo={servo_id} read_status recovered attempt={attempt} status={status}"
                )
            return status, result, err

        debug_log(
            f"servo={servo_id} invalid_status_read attempt={attempt} "
            f"result={result} err={err}"
        )
        last_status = status
        last_result = result
        last_err = err
        time.sleep(POLL_INTERVAL_SEC)

    return last_status, last_result, last_err


def read_servo_diagnostics(scs, servo_id):
    voltage_raw, voltage_result, _ = scs.read1ByteTxRx(servo_id, ADDR_PRESENT_VOLTAGE)
    temp_raw, temp_result, _ = scs.read1ByteTxRx(servo_id, ADDR_PRESENT_TEMPERATURE)
    current_raw, current_result, _ = scs.read2ByteTxRx(servo_id, ADDR_PRESENT_CURRENT_L)

    return {
        "voltage_raw": voltage_raw if voltage_result == COMM_SUCCESS else None,
        "voltage_v": (voltage_raw / 10.0) if voltage_result == COMM_SUCCESS else None,
        "temperature_c": temp_raw if temp_result == COMM_SUCCESS else None,
        "current_raw": current_raw if current_result == COMM_SUCCESS else None,
    }


def format_diagnostics(diagnostics):
    parts = []
    if diagnostics["voltage_v"] is not None:
        parts.append(f"voltage={diagnostics['voltage_v']:.1f}V")
    if diagnostics["temperature_c"] is not None:
        parts.append(f"temp={diagnostics['temperature_c']}C")
    if diagnostics["current_raw"] is not None:
        parts.append(f"current_raw={diagnostics['current_raw']}")
    return ", ".join(parts) if parts else "no live diagnostics"


def read_confirmed_status(scs, servo_id):
    statuses = []
    last_result = COMM_RX_FAIL
    last_err = 0

    for attempt in range(FAULT_CONFIRM_READS):
        status, result, err = read_status_with_retry(scs, servo_id)
        last_result = result
        last_err = err
        if result != COMM_SUCCESS:
            return status, result, err
        statuses.append(status)
        if attempt < FAULT_CONFIRM_READS - 1:
            time.sleep(FAULT_CONFIRM_DELAY_SEC)

    if len(set(statuses)) > 1:
        debug_log(f"servo={servo_id} transient_status_reads={statuses}")
        return 0, COMM_SUCCESS, 0
    return statuses[-1], last_result, last_err


def clamp_position(goal):
    return max(SERVO_MIN_POSITION, min(SERVO_MAX_POSITION, int(goal)))


def write_goal_position(scs, scs_id, goal, speed, acc=15):
    """Send a motion command using the SDK's native combined position packet."""
    goal = clamp_position(goal)
    debug_log(f"servo={scs_id} write_goal goal={goal} speed={speed} acc={acc}")
    comm_result, scs_error = scs.WritePosEx(scs_id, goal, speed, acc)
    if comm_result != COMM_SUCCESS:
        debug_log(
            f"servo={scs_id} WritePosEx txrx_error=" f"{scs.getTxRxResult(comm_result)}"
        )
    elif scs_error != 0:
        debug_log(
            f"servo={scs_id} WritePosEx servo_error="
            f"{scs.getRxPacketError(scs_error)}"
        )
    return comm_result, scs_error


def set_current_pos_to_2047(scs, scs_id):
    """Write 128 to ADDR_TORQUE_SWITCH → current position becomes 2047."""
    debug_log(f"servo={scs_id} set_current_pos_to_2047")
    scs.write1ByteTxRx(scs_id, ADDR_TORQUE_SWITCH, 128)
    time.sleep(0.05)


def enable_torque_for_motion(scs, scs_id):
    """Restore normal torque mode before sending motion goals."""
    debug_log(f"servo={scs_id} enable_torque_for_motion")
    scs.write1ByteTxRx(scs_id, ADDR_TORQUE_SWITCH, 1)
    time.sleep(0.05)


def recover_from_error(scs, servo_id):
    """
    Best-effort recovery after a hard stop.
    We torque-cycle the servo, then re-check the status register.
    """
    print(f"  Attempting fault recovery on servo {servo_id} …")
    for attempt in range(1, ERROR_CLEAR_RETRIES + 1):
        debug_log(
            f"servo={servo_id} recovery_attempt={attempt} "
            f"wait={ERROR_RECOVERY_WAIT_SEC}s"
        )
        time.sleep(ERROR_RECOVERY_WAIT_SEC)
        scs.write1ByteTxRx(servo_id, ADDR_TORQUE_SWITCH, 0)
        time.sleep(0.1)
        scs.write1ByteTxRx(servo_id, ADDR_TORQUE_SWITCH, 1)
        time.sleep(0.1)

        status, result, _ = read_status_with_retry(scs, servo_id)
        if result != COMM_SUCCESS:
            print(f"  WARNING: Could not verify recovery status for servo {servo_id}.")
            continue

        if status == 0:
            print(f"  Fault recovery cleared the status for servo {servo_id}.")
            debug_log(f"servo={servo_id} recovery_status=0 attempt={attempt}")
            return True

        errors = decode_errors(status)
        print(
            f"  WARNING: Servo {servo_id} still reports errors after retry {attempt}: "
            f"{', '.join(errors)}"
        )
        debug_log(f"servo={servo_id} recovery_status={status} attempt={attempt}")

    return False


def unlock_eprom(scs, scs_id):
    scs.write1ByteTxRx(scs_id, ADDR_LOCK_MARK, 0)
    time.sleep(0.05)


def lock_eprom(scs, scs_id):
    scs.write1ByteTxRx(scs_id, ADDR_LOCK_MARK, 1)
    time.sleep(0.05)


def write_angle_limits(scs, scs_id, min_angle, max_angle):
    unlock_eprom(scs, scs_id)
    scs.write2ByteTxRx(scs_id, ADDR_MIN_ANGLE_L, min_angle)
    scs.write2ByteTxRx(scs_id, ADDR_MAX_ANGLE_L, max_angle)
    lock_eprom(scs, scs_id)


def write_eprom_register_2byte(scs, scs_id, addr, value):
    unlock_eprom(scs, scs_id)
    scs.write2ByteTxRx(scs_id, addr, value)
    lock_eprom(scs, scs_id)


def write_eprom_register_1byte(scs, scs_id, addr, value):
    unlock_eprom(scs, scs_id)
    scs.write1ByteTxRx(scs_id, addr, value)
    lock_eprom(scs, scs_id)


def reached(current, target, tol=POSITION_TOLERANCE):
    return abs(current - target) <= tol


def compensated_target(current, goal):
    goal = clamp_position(goal)
    if current is None:
        return goal
    if goal > current:
        return clamp_position(goal + BACKLASH_COMPENSATION)
    if goal < current:
        return clamp_position(goal - BACKLASH_COMPENSATION)
    return goal


def build_incremental_goals(current, goal):
    goal = clamp_position(goal)
    if current is None:
        return [goal]

    current = clamp_position(current)
    final_drive_goal = compensated_target(current, goal)
    if final_drive_goal == current:
        return [final_drive_goal]

    step = GOAL_STEP_SIZE if final_drive_goal > current else -GOAL_STEP_SIZE
    goals = list(range(current + step, final_drive_goal, step))
    goals.append(final_drive_goal)
    return [clamp_position(item) for item in goals]


def build_final_approach_goals(current, goal):
    goal = clamp_position(goal)
    if current is None:
        return [goal]

    current = clamp_position(current)
    if current == goal:
        return []

    step = FINAL_APPROACH_STEP if goal > current else -FINAL_APPROACH_STEP
    goals = list(range(current + step, goal, step))
    goals.append(goal)
    return [clamp_position(item) for item in goals]


def select_final_approach_goal(current, goal, attempt):
    """
    Pick a progressively deeper target toward the true goal.
    This avoids getting stuck re-sending the same tiny correction when the
    servo does not move on a small delta command.
    """
    current = clamp_position(current)
    goal = clamp_position(goal)
    if current == goal:
        return goal

    direction = 1 if goal > current else -1
    step_span = FINAL_APPROACH_STEP * max(1, attempt)
    next_goal = current + (direction * step_span)

    if direction > 0:
        next_goal = min(next_goal, goal)
    else:
        next_goal = max(next_goal, goal)

    return clamp_position(next_goal)


# ── Port detection ────────────────────────────────────────────────────────────
SUPPORTED_USB_IDS = {
    (0x1A86, 0x55D3): "QinHeng Electronics USB Single Serial",
    (0x0403, 0x6014): "FTDI FT232H Single HS USB-UART/FIFO IC",
}

BAUD_RATE = 1_000_000  # 1 M baud
SERVO_IDS = [51, 52, 53]


def discover_candidate_ports():
    """
    Return serial device paths whose USB VID:PID matches a supported adapter.
    Prefer pyserial metadata and fall back to Linux sysfs when needed.
    """
    candidates = []
    seen = set()

    if list_ports is not None:
        for port_info in list_ports.comports():
            vid = getattr(port_info, "vid", None)
            pid = getattr(port_info, "pid", None)
            device = getattr(port_info, "device", None)
            if device and (vid, pid) in SUPPORTED_USB_IDS and device not in seen:
                candidates.append((device, SUPPORTED_USB_IDS[(vid, pid)]))
                seen.add(device)

    # Linux fallback in case pyserial cannot populate VID/PID metadata.
    if sys.platform.startswith("linux"):
        tty_dirs = list(Path("/sys/class/tty").glob("ttyUSB*"))
        tty_dirs.extend(Path("/sys/class/tty").glob("ttyACM*"))
        for tty_dir in sorted(tty_dirs):
            uevent_path = tty_dir / "device" / ".." / "uevent"
            try:
                data = uevent_path.resolve().read_text(
                    encoding="utf-8", errors="ignore"
                )
            except OSError:
                continue

            product = vendor = None
            for line in data.splitlines():
                if line.startswith("PRODUCT="):
                    parts = line.split("=", 1)[1].split("/")
                    if len(parts) >= 2:
                        vendor = int(parts[0], 16)
                        product = int(parts[1], 16)
                    break

            device = f"/dev/{tty_dir.name}"
            if (vendor, product) in SUPPORTED_USB_IDS and device not in seen:
                candidates.append((device, SUPPORTED_USB_IDS[(vendor, product)]))
                seen.add(device)

    return candidates


def find_port_and_servos():
    """Return (portHandler, sms_sts_handler, found_ids) or exit."""
    found_port = None
    found_ids = []
    scs = None

    candidate_ports = discover_candidate_ports()
    if not candidate_ports:
        print("✖  No supported USB serial adapter found.")
        print("   Expected one of these USB VID:PID pairs:")
        for (vid, pid), label in SUPPORTED_USB_IDS.items():
            print(f"   - {label}: {vid:04x}:{pid:04x}")
        sys.exit(1)

    print("Detected supported USB adapter(s):")
    for device, label in candidate_ports:
        print(f"  - {device} ({label})")
    print()

    for device, label in candidate_ports:
        port = PortHandler(device)
        if not port.openPort():
            continue
        if not port.setBaudRate(BAUD_RATE):
            port.closePort()
            continue

        ph = sms_sts(port)
        ids_on_port = []
        for sid in SERVO_IDS:
            _, result, error = ph.ping(sid)
            if result == COMM_SUCCESS:
                ids_on_port.append(sid)

        if ids_on_port:
            print(f"✔  Found driver board on {device} ({label})")
            found_port = port
            found_ids = ids_on_port
            scs = ph
            break
        else:
            port.closePort()

    if found_port is None:
        print("✖  Servo driver board not found on any port.")
        sys.exit(1)

    missing = [sid for sid in SERVO_IDS if sid not in found_ids]
    if missing:
        print(f"✖  Servo(s) not detected: {missing}")
        if len(missing) == len(SERVO_IDS):
            print("   None of the servos responded.")
        sys.exit(1)

    print(f"✔  All servos detected: {found_ids}\n")
    return found_port, scs, found_ids


# ── Pre-calibration setup ─────────────────────────────────────────────────────
def apply_pre_calibration(scs, port, servo_id):
    print(f"  Applying pre-calibration register values for servo {servo_id} …")
    regs = PRE_CALIBRATION[servo_id]

    # Addresses that are 2-byte (from memory table)
    TWO_BYTE = {0x10, 0x1C, 0x09, 0x0B}

    unlock_eprom(scs, servo_id)
    for addr, value in regs.items():
        if addr in TWO_BYTE:
            scs.write2ByteTxRx(servo_id, addr, value)
        else:
            scs.write1ByteTxRx(servo_id, addr, value)
        time.sleep(0.02)
    lock_eprom(scs, servo_id)
    print(f"  Done.\n")


# ── Error check ───────────────────────────────────────────────────────────────
def check_servo_errors(scs, servo_id):
    status, result, _ = read_confirmed_status(scs, servo_id)
    if result != COMM_SUCCESS:
        print(f"  WARNING: Could not read status register for servo {servo_id}.")
        return True  # treat as error
    if status == 0:
        return False  # no errors
    errors = decode_errors(status)
    diagnostics = read_servo_diagnostics(scs, servo_id)
    print(
        f"  ✖ Servo {servo_id} has errors: {', '.join(errors)} ({format_diagnostics(diagnostics)})"
    )
    return True


def check_and_recover_servo_errors(scs, servo_id):
    """
    Return True when the servo is clear to continue.
    If a fault is present, attempt a best-effort recovery first.
    """
    status, result, _ = read_confirmed_status(scs, servo_id)
    if result != COMM_SUCCESS:
        print(f"  WARNING: Could not read status register for servo {servo_id}.")
        return False

    if status == 0:
        return True

    errors = decode_errors(status)
    diagnostics = read_servo_diagnostics(scs, servo_id)
    print(
        f"  Servo {servo_id} reported errors: {', '.join(errors)} ({format_diagnostics(diagnostics)})"
    )
    return recover_from_error(scs, servo_id)


def recover_if_servo_faulted(scs, servo_id, prefix="  "):
    status, result, _ = read_confirmed_status(scs, servo_id)
    if result != COMM_SUCCESS:
        print(f"{prefix}WARNING: Could not read status register for servo {servo_id}.")
        return False
    if status == 0:
        return True
    errors = decode_errors(status)
    diagnostics = read_servo_diagnostics(scs, servo_id)
    print(
        f"{prefix}Servo {servo_id} reported errors: {', '.join(errors)} ({format_diagnostics(diagnostics)})"
    )
    return recover_from_error(scs, servo_id)


def wait_for_goal(scs, servo_id, goal, timeout=10.0):
    deadline = time.time() + timeout
    still_since = None
    last_pos = None

    while time.time() < deadline:
        pos, result, _ = read_position(scs, servo_id)
        moving, moving_result, _ = read_moving_state(scs, servo_id)
        if result == COMM_SUCCESS:
            debug_log(
                f"servo={servo_id} wait_for_goal pos={pos} target={goal} "
                f"moving={moving if moving_result == COMM_SUCCESS else 'read-fail'}"
            )

        if result == COMM_SUCCESS and reached(pos, goal):
            return True

        if result == COMM_SUCCESS:
            if last_pos is not None and abs(pos - last_pos) <= 1:
                if still_since is None:
                    still_since = time.time()
                elif time.time() - still_since >= MOTION_STOP_HOLD_SEC:
                    return reached(
                        pos, goal, tol=max(POSITION_TOLERANCE, BACKLASH_COMPENSATION)
                    )
            else:
                still_since = None
            last_pos = pos

        if not recover_if_servo_faulted(scs, servo_id):
            return False
        time.sleep(POLL_INTERVAL_SEC)
    return False


def wait_until_motion_stops(
    scs, servo_id, timeout=15.0, settle_time=MOTION_STOP_HOLD_SEC
):
    """
    Wait until the servo stops moving, using the moving flag first and
    falling back to stable position detection if needed.
    Returns (stopped, final_position).
    """
    deadline = time.time() + timeout
    still_since = None
    last_pos = None
    final_pos = None

    while time.time() < deadline:
        pos, pos_result, _ = read_position(scs, servo_id)
        moving, moving_result, _ = read_moving_state(scs, servo_id)
        now = time.time()

        if pos_result == COMM_SUCCESS:
            final_pos = pos
            debug_log(
                f"servo={servo_id} wait_motion pos={pos} "
                f"moving={moving if moving_result == COMM_SUCCESS else 'read-fail'}"
            )

        if pos_result == COMM_SUCCESS:
            if last_pos is not None and abs(pos - last_pos) <= 1:
                if still_since is None:
                    still_since = now
                elif now - still_since >= settle_time:
                    return True, final_pos
            else:
                still_since = None
            last_pos = pos

        if not recover_if_servo_faulted(scs, servo_id):
            return False, final_pos

        time.sleep(POLL_INTERVAL_SEC)

    return False, final_pos


def move_incrementally_to_goal(scs, servo_id, goal, speed, timeout=15.0, label=None):
    """
    Approach the goal in small bounded steps, then drive slightly past the goal
    to take up backlash. All commanded positions are clamped to 0..4095.
    Returns (success, final_position).
    """
    current_pos, result, _ = read_position(scs, servo_id)
    if result != COMM_SUCCESS:
        print(
            f"  WARNING: Could not read current position for servo {servo_id} after retries."
        )
        return False, None

    requested_goal = clamp_position(goal)
    incremental_goals = build_incremental_goals(current_pos, requested_goal)
    if label:
        print(
            f"    {label}: incremental goals {incremental_goals[0]} → {incremental_goals[-1]}"
        )

    enable_torque_for_motion(scs, servo_id)
    for step_goal in incremental_goals:
        debug_log(
            f"servo={servo_id} incremental_step_goal={step_goal} requested_goal={requested_goal}"
        )
        write_goal_position(scs, servo_id, step_goal, speed)
        stopped, final_pos = wait_until_motion_stops(scs, servo_id, timeout=timeout)
        if not stopped:
            return False, final_pos

    final_pos, result, _ = read_position(scs, servo_id)
    if result != COMM_SUCCESS:
        print(
            f"  WARNING: Could not read final position for servo {servo_id} after retries."
        )
        return False, None

    attempts = 0
    while not reached(final_pos, requested_goal) and attempts < FINAL_APPROACH_ATTEMPTS:
        attempts += 1
        if final_pos is None:
            break

        next_goal = select_final_approach_goal(final_pos, requested_goal, attempts)
        if next_goal == final_pos:
            break
        debug_log(
            f"servo={servo_id} final_approach_attempt={attempts} "
            f"current={final_pos} next_goal={next_goal} target={requested_goal}"
        )
        write_goal_position(scs, servo_id, next_goal, speed)
        stopped, final_pos = wait_until_motion_stops(scs, servo_id, timeout=timeout)
        if not stopped or final_pos is None:
            return False, final_pos

    final_pos, result, _ = read_position(scs, servo_id)
    if result != COMM_SUCCESS:
        print(
            f"  WARNING: Could not read final position for servo {servo_id} after retries."
        )
        return False, None

    return (
        reached(
            final_pos,
            requested_goal,
            tol=max(POSITION_TOLERANCE, BACKLASH_COMPENSATION),
        ),
        final_pos,
    )


# ── Mechanical-limit detection ───────────────────────────────────────────────
def find_mechanical_limit(scs, servo_id, limit_goal):
    """
    Drive toward limit_goal.  If position reaches limit_goal without stopping,
    re-home and try again.  Return True when mechanical limit is detected
    (position unchanged for STILL_TIMEOUT_SEC).
    """
    config = SERVO_CONFIG[servo_id]

    while True:
        current_pos, result, _ = read_position(scs, servo_id)
        if result != COMM_SUCCESS:
            time.sleep(POLL_INTERVAL_SEC)
            continue

        print(
            f"    → Driving servo {servo_id} toward {limit_goal} in {GOAL_STEP_SIZE}-tick steps …"
        )
        last_pos = current_pos
        still_since = None
        enable_torque_for_motion(scs, servo_id)
        for step_goal in build_incremental_goals(current_pos, limit_goal):
            write_goal_position(scs, servo_id, step_goal, CALIBRATION_SPEED)
            debug_log(
                f"servo={servo_id} limit_search_step_goal={step_goal} start_pos={current_pos}"
            )

            while True:
                pos, result, _ = read_position(scs, servo_id)
                moving, moving_result, _ = read_moving_state(scs, servo_id)
                if result != COMM_SUCCESS:
                    time.sleep(POLL_INTERVAL_SEC)
                    continue

                now = time.time()
                debug_log(
                    f"servo={servo_id} limit_search pos={pos} step_goal={step_goal} "
                    f"moving={moving if moving_result == COMM_SUCCESS else 'read-fail'}"
                )

                if reached(pos, step_goal, tol=max(POSITION_TOLERANCE, GOAL_STEP_SIZE)):
                    last_pos = pos
                    still_since = None
                    break

                # Check if servo has reached the software limit (no physical stop yet)
                if reached(pos, limit_goal):
                    print(
                        f"    Position reached software limit {limit_goal}, re-homing …"
                    )
                    set_current_pos_to_2047(scs, servo_id)
                    time.sleep(0.3)
                    break

                # Detect mechanical limit from stable position only.
                stable = last_pos is not None and abs(pos - last_pos) <= 1
                progressed = abs(pos - current_pos) >= MIN_PROGRESS_FOR_LIMIT_DETECTION
                if progressed and stable:
                    if still_since is None:
                        still_since = now
                    elif now - still_since >= STILL_TIMEOUT_SEC:
                        print(f"    Mechanical limit detected at position {pos}.")
                        return True
                else:
                    still_since = None

                last_pos = pos

                if not recover_if_servo_faulted(scs, servo_id, prefix="    "):
                    return False

                time.sleep(POLL_INTERVAL_SEC)

            if reached(last_pos or current_pos, limit_goal):
                break


# ── Single-servo calibration ─────────────────────────────────────────────────
def calibrate_servo(scs, servo_id):
    config = SERVO_CONFIG[servo_id]
    limit_goal = config["limit_goal"]
    settle_goal = config["settle_goal"]
    limits = POST_CALIBRATION_LIMITS[servo_id]

    print(f"\n{'='*60}")
    print(f"  Calibrating Servo {servo_id}")
    print(f"{'='*60}")

    # 1. Check for errors
    wait_for_enter(f"Servo {servo_id} Step 1: Check servo status/errors.")
    if not check_and_recover_servo_errors(scs, servo_id):
        print(
            f"  ✖ Aborting calibration for servo {servo_id} due to persistent errors."
        )
        return False

    # 2. Home: set current position = 2047
    print(f"  Step 1: Homing servo {servo_id} → position 2047 …")
    wait_for_enter(f"Servo {servo_id} Step 1: Press ENTER to home to position 2047.")
    set_current_pos_to_2047(scs, servo_id)
    time.sleep(0.3)
    enable_torque_for_motion(scs, servo_id)

    # 3. Drive to mechanical limit
    print(f"  Step 2: Finding mechanical limit …")
    wait_for_enter(
        f"Servo {servo_id} Step 2: Press ENTER to drive toward the mechanical limit."
    )
    if not find_mechanical_limit(scs, servo_id, limit_goal):
        print(
            f"  ✖ Servo {servo_id} did not complete the mechanical limit search cleanly."
        )
        return False

    # 4. Re-home at mechanical limit
    print(f"  Step 3: Re-homing at mechanical limit …")
    wait_for_enter(
        f"Servo {servo_id} Step 3: Press ENTER to re-home at the mechanical limit."
    )
    set_current_pos_to_2047(scs, servo_id)
    time.sleep(0.3)
    enable_torque_for_motion(scs, servo_id)
    print("  Step 3A: Checking for any latched error after hard-stop re-home …")
    if not check_and_recover_servo_errors(scs, servo_id):
        print(
            f"  ✖ Servo {servo_id} is still in an error state after the mechanical limit."
        )
        return False

    # 5. Move to settle position
    print(f"  Step 4: Moving to settle position {settle_goal} …")
    wait_for_enter(
        f"Servo {servo_id} Step 4: Press ENTER to move to settle position {settle_goal}."
    )
    settled, final_pos = move_incrementally_to_goal(
        scs, servo_id, settle_goal, CALIBRATION_SPEED, timeout=15.0, label="Settle move"
    )
    if not settled:
        print(f"  ✖ Servo {servo_id} did not finish the settle move cleanly.")
        return False
    if final_pos is None:
        print(f"  ✖ Servo {servo_id} stopped, but position could not be read.")
        return False
    print(
        f"    Motion stopped at position {final_pos} while moving toward {settle_goal}."
    )

    # 6. Re-home again from settle position
    print(f"  Step 5: Final home (position → 2047) …")
    wait_for_enter(
        f"Servo {servo_id} Step 5: Press ENTER for the final home to position 2047."
    )
    set_current_pos_to_2047(scs, servo_id)
    time.sleep(0.3)

    # 7. Write angle limits to EPROM
    print(
        f"  Step 6: Writing angle limits — min={limits['min']}, max={limits['max']} …"
    )
    wait_for_enter(
        f"Servo {servo_id} Step 6: Press ENTER to write angle limits to EPROM."
    )
    write_angle_limits(scs, servo_id, limits["min"], limits["max"])
    time.sleep(0.1)

    # 8. Verification: move min → max, check servo moves freely
    print(f"  Step 7: Verification sweep min→max …")
    wait_for_enter(
        f"Servo {servo_id} Step 7A: Press ENTER to move to min limit {limits['min']}."
    )
    reached_min, final_pos = move_incrementally_to_goal(
        scs,
        servo_id,
        limits["min"],
        CALIBRATION_SPEED,
        timeout=10.0,
        label="Verification min",
    )
    if not reached_min:
        print(f"  ✖ Servo {servo_id} calibration FAILED (could not reach min limit).")
        return False

    wait_for_enter(
        f"Servo {servo_id} Step 7B: Press ENTER to move to max limit {limits['max']}."
    )
    reached_max, final_pos = move_incrementally_to_goal(
        scs,
        servo_id,
        limits["max"],
        CALIBRATION_SPEED,
        timeout=10.0,
        label="Verification max",
    )
    if not reached_max:
        print(f"  ✖ Servo {servo_id} calibration FAILED (could not reach max limit).")
        return False

    # Return to center
    wait_for_enter(
        f"Servo {servo_id} Step 7C: Press ENTER to return to init position {FINAL_INIT_POSITION}."
    )
    returned_to_init, final_pos = move_incrementally_to_goal(
        scs,
        servo_id,
        FINAL_INIT_POSITION,
        CALIBRATION_SPEED,
        timeout=10.0,
        label="Return to init",
    )
    if not returned_to_init:
        print(
            f"  ✖ Servo {servo_id} calibration FAILED "
            f"(could not return to init position {FINAL_INIT_POSITION})."
        )
        return False

    print(f"  ✔ Servo {servo_id} calibration SUCCESSFUL!\n")
    return True


# ── Pause helper ─────────────────────────────────────────────────────────────
def wait_for_enter(message):
    print(f"\n  {'─'*56}")
    print(f"  ⏸  {message}")
    print(f"  {'─'*56}")
    input("     Press ENTER to continue …")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  STS3215 Auto Calibration Tool")
    print("  Order: Servo 53 → 52 → 51")
    print("=" * 60)

    port, scs, found_ids = find_port_and_servos()

    results = {}

    # ── PHASE 1: Write pre-calibration registers for ALL servos first ──────────
    print("\n" + "=" * 60)
    print("  PHASE 1 — Writing pre-calibration registers (all servos)")
    print("=" * 60)

    for servo_id in [53, 52, 51]:
        if servo_id not in found_ids:
            print(f"  Skipping servo {servo_id} — not detected.")
            results[servo_id] = "SKIPPED"
            continue
        apply_pre_calibration(scs, port, servo_id)

    # ── Gate: confirm before any motion begins ─────────────────────────────────
    wait_for_enter(
        "Pre-calibration registers written for all servos.\n"
        "  Inspect the robot, make sure it is safe to move.\n"
        "  Calibration will start with Servo 53."
    )

    # ── PHASE 2: Calibrate one by one: 53 → 52 → 51 ───────────────────────────
    print("\n" + "=" * 60)
    print("  PHASE 2 — Servo Calibration")
    print("=" * 60)

    calibration_order = [53, 52, 51]

    for idx, servo_id in enumerate(calibration_order):
        if results.get(servo_id) == "SKIPPED":
            print(f"  Skipping servo {servo_id} — not detected earlier.")
            continue

        # Gate before each servo (except the very first which was gated above)
        if idx > 0:
            next_label = f"Servo {servo_id}"
            wait_for_enter(
                f"Ready to calibrate {next_label}.\n"
                "  Check robot position / clearance before proceeding."
            )

        ok = calibrate_servo(scs, servo_id)
        results[servo_id] = "SUCCESS" if ok else "FAILED"

    port.closePort()

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Calibration Summary")
    print("=" * 60)
    for sid in [53, 52, 51]:
        status = results.get(sid, "NOT RUN")
        icon = "✔" if status == "SUCCESS" else ("–" if status == "SKIPPED" else "✖")
        print(f"  {icon}  Servo {sid}: {status}")
    print()


if __name__ == "__main__":
    main()
