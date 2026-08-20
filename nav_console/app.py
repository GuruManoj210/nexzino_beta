#!/usr/bin/env python3

from __future__ import annotations

import json
import shutil
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
# Persisted RTAB-Map .db files, one per saved map - this is the actual map
# data navigation.launch loads via database_path. Separate from the .pgm/
# .yaml/.png below, which are only a visual thumbnail for the web UI.
MAPS_DB_DIR = DATA_DIR / "maps_db"
MAPS_REGISTRY_PATH = DATA_DIR / "maps.json"
STATIC_MAPS_DIR = BASE_DIR / "static" / "maps"
# Working database while a mapping session is active. mapping.launch's
# --delete_db_on_start wipes this fresh every time "Start Mapping" runs.
SCRATCH_DB_PATH = DATA_DIR / "mapping_session.db"

for directory in (DATA_DIR, MAPS_DB_DIR, STATIC_MAPS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)


def _atomic_write_json(path: Path, data: Any) -> None:
    # Same pattern as servo_tester/app.py: write to a sibling temp file and
    # rename it into place, so a kill mid-write can never leave `path`
    # truncated/corrupt (`json.load` on an empty file breaks every reader).
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as tmp_file:
        json.dump(data, tmp_file, indent=2)
    tmp_path.replace(path)


def _safe_name(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip()
    )
    return cleaned or f"map_{int(time.time())}"


def load_maps() -> list[dict[str, Any]]:
    if not MAPS_REGISTRY_PATH.exists():
        return []
    try:
        with MAPS_REGISTRY_PATH.open("r", encoding="utf-8") as registry_file:
            return json.load(registry_file).get("maps", [])
    except (json.JSONDecodeError, OSError):
        return []


def save_maps(maps: list[dict[str, Any]]) -> None:
    _atomic_write_json(MAPS_REGISTRY_PATH, {"maps": maps})


class RoslaunchProcess:
    """Owns the single currently-running mapping/navigation roslaunch.

    Only one of mapping/navigation ever runs at a time - the frontend always
    stops one before starting the other (see /navigation/gotomapping and
    /navigation/loadmap), matching the original app's flow.
    """

    process: subprocess.Popen | None = None
    mode: str | None = None  # "mapping" | "navigation"

    @classmethod
    def start_mapping(cls) -> None:
        cls.process = subprocess.Popen(
            [
                "roslaunch",
                "nexzino_nav",
                "mapping.launch",
                "start_motor_driver:=false",
                "open_rviz:=false",
                "database_path:=" + str(SCRATCH_DB_PATH),
            ]
        )
        cls.mode = "mapping"

    @classmethod
    def start_navigation(cls, db_path: str) -> None:
        cls.process = subprocess.Popen(
            [
                "roslaunch",
                "nexzino_nav",
                "navigation.launch",
                "start_motor_driver:=false",
                "open_rviz:=false",
                "database_path:=" + db_path,
            ]
        )
        cls.mode = "navigation"

    @classmethod
    def stop(cls) -> None:
        # Bounded wait, not an indefinite one: a stuck roslaunch here
        # shouldn't be able to hang the request forever.
        if cls.process is None:
            return
        cls.process.send_signal(signal.SIGINT)
        try:
            cls.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait(timeout=5)
        cls.process = None
        cls.mode = None


@app.route("/")
def index():
    return render_template("index.html", title="Index", maps=load_maps())


@app.route("/index/<variable>", methods=["GET", "POST"])
def index_action(variable: str):
    if variable == "navigation-precheck":
        return jsonify(mapcount=len(load_maps()))

    if variable == "gotonavigation":
        mapname = request.get_data().decode("utf-8")
        maps_by_name = {m["name"]: m for m in load_maps()}
        if mapname not in maps_by_name:
            return jsonify(ok=False, error=f"Unknown map: {mapname}"), 404
        RoslaunchProcess.start_navigation(maps_by_name[mapname]["db_path"])
        return "success"

    return jsonify(ok=False, error=f"Unknown action: {variable}"), 404


@app.route("/navigation", methods=["GET", "POST"])
def navigation():
    return render_template("navigation.html", maps=load_maps())


@app.route("/navigation/deletemap", methods=["POST"])
def deletemap():
    mapname = _safe_name(request.get_data().decode("utf-8"))
    maps = load_maps()
    remaining = [m for m in maps if m["name"] != mapname]
    if len(remaining) != len(maps):
        (MAPS_DB_DIR / f"{mapname}.db").unlink(missing_ok=True)
        for suffix in (".pgm", ".yaml", ".png"):
            (STATIC_MAPS_DIR / f"{mapname}{suffix}").unlink(missing_ok=True)
        save_maps(remaining)
    return "successfully deleted map"


@app.route("/navigation/<variable>", methods=["GET", "POST"])
def navigation_action(variable: str):
    if variable == "index":
        RoslaunchProcess.start_mapping()
    elif variable == "gotomapping":
        RoslaunchProcess.stop()
        time.sleep(2)
        RoslaunchProcess.start_mapping()
    return "success"


@app.route("/navigation/loadmap", methods=["POST"])
def loadmap():
    mapname = _safe_name(request.get_data().decode("utf-8"))
    maps_by_name = {m["name"]: m for m in load_maps()}
    if mapname not in maps_by_name:
        return jsonify(ok=False, error=f"Unknown map: {mapname}"), 404
    RoslaunchProcess.stop()
    time.sleep(2)
    RoslaunchProcess.start_navigation(maps_by_name[mapname]["db_path"])
    return "success"


@app.route("/navigation/stop", methods=["POST"])
def stop_robot():
    # -1: publish once and exit, rather than needing to be killed.
    subprocess.run(
        [
            "rostopic",
            "pub",
            "-1",
            "/move_base/cancel",
            "actionlib_msgs/GoalID",
            "--",
            "{}",
        ],
        check=False,
        timeout=5,
    )
    return "stopped the robot"


@app.route("/mapping")
def mapping():
    return render_template("mapping.html", maps=load_maps())


@app.route("/mapping/cutmapping", methods=["POST"])
def stop_mapping():
    RoslaunchProcess.stop()
    return "killed the mapping node"


@app.route("/mapping/savemap", methods=["POST"])
def savemap():
    mapname = _safe_name(request.get_data().decode("utf-8"))
    map_base = STATIC_MAPS_DIR / mapname

    # Order matters: map_saver needs /map still being published, which
    # requires rtabmap (still running) - so snapshot the thumbnail FIRST,
    # then stop mapping (flushes/closes the db cleanly), then copy the db.
    # Copying a sqlite file that's still open for writing risks grabbing an
    # inconsistent snapshot mid-transaction.
    try:
        subprocess.run(
            ["rosrun", "map_server", "map_saver", "-f", str(map_base)],
            check=False,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        pass

    pgm_path = map_base.with_suffix(".pgm")
    png_path = map_base.with_suffix(".png")
    if pgm_path.exists():
        Image.open(pgm_path).save(png_path)

    RoslaunchProcess.stop()

    if not SCRATCH_DB_PATH.exists():
        return jsonify(ok=False, error="No active mapping session to save."), 400

    db_dest = MAPS_DB_DIR / f"{mapname}.db"
    shutil.copyfile(SCRATCH_DB_PATH, db_dest)

    maps = [m for m in load_maps() if m["name"] != mapname]
    maps.append(
        {
            "name": mapname,
            "db_path": str(db_dest),
            "saved_at": datetime.now().isoformat(),
        }
    )
    save_maps(maps)

    return "success"


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)
