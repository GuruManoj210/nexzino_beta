#!/usr/bin/env python3
"""
Continuous live view from the IMX708 (RPi Camera Module 3) on Jetson Orin NX,
using the linuxpy library for V4L2 capture and OpenCV for demosaic + display.

Performance notes (this version):
    - Avoids the bytes(frame) full-buffer copy — reads directly off the
      frame's own buffer via memoryview.
    - Live preview downsizes BEFORE white balance / gamma / rotate, since
      those are the expensive per-pixel steps. Full-res processing only
      happens when you press 's' to save.
    - Prints measured FPS every 30 frames so you can see actual throughput
      instead of guessing from how it feels.

Usage:
    python3 imx708_live_view_linuxpy.py [sensor_mode]

sensor_mode (driver ignores width/height passed to set_format — resolution
comes from this control instead):
    0 = 4608x2592 @ ~14fps   (default if omitted -- heaviest to process)
    1 = 2304x1296 @ ~55fps
    2 = 1536x864  @ ~90fps   (recommended for smooth live view)

Keys:
    's' = save current frame (full-res, fully processed) as a timestamped PNG
    'w' = toggle auto white balance
    'q' = quit
"""

import os
import sys
import time
import cv2
import numpy as np
from linuxpy.video.device import Device, BufferType

BAYER_CODE = cv2.COLOR_BayerBG2BGR  # confirmed correct phase for this rig
ROTATE_MODE = cv2.ROTATE_180        # confirmed orientation for this mount
GAMMA = 2.2
CAPTURE_DIR = "captures"
DISPLAY_WIDTH = 1280  # live preview is downsized to this width before AWB/gamma

_gamma_lut = np.array([((i / 255.0) ** (1.0 / GAMMA)) * 255
                        for i in range(256)]).astype(np.uint8)


def get_bytesperline(fmt, data_len, height):
    for attr_path in (
        lambda f: f.bytes_per_line,
        lambda f: f.bytesperline,
        lambda f: f.fmt.pix.bytesperline,
        lambda f: f.plane_fmt[0].bytesperline,
    ):
        try:
            bpl = attr_path(fmt)
            if bpl and bpl > 0:
                return bpl
        except (AttributeError, IndexError, TypeError):
            continue
    return data_len // height


def unpack_rg10_rows(raw_buf, width, height, stride_bytes):
    """raw_buf can be any buffer-protocol object (memoryview, bytes, mmap) --
    no copy is forced here beyond what np.frombuffer needs."""
    row_pixel_bytes = width * 2
    if stride_bytes == row_pixel_bytes:
        return np.frombuffer(raw_buf, dtype='<u2', count=width * height).reshape((height, width))
    rows = np.empty((height, width), dtype='<u2')
    raw_bytes = bytes(raw_buf)  # only copy here if we actually need row-slicing
    for y in range(height):
        start = y * stride_bytes
        rows[y] = np.frombuffer(raw_bytes[start:start + row_pixel_bytes], dtype='<u2', count=width)
    return rows


def demosaic_rg10_8bit(raw_buf, width, height, stride_bytes):
    raw16 = unpack_rg10_rows(raw_buf, width, height, stride_bytes)
    raw8 = (raw16 >> 8).astype(np.uint8)  # 10-bit data is MSB-aligned in bits [15:6]
    return cv2.cvtColor(raw8, BAYER_CODE)


def gray_world_white_balance(img):
    img = img.astype(np.float32)
    b, g, r = cv2.split(img)
    b_mean, g_mean, r_mean = b.mean(), g.mean(), r.mean()
    k = (b_mean + g_mean + r_mean) / 3.0
    b = b * (k / b_mean) if b_mean > 0 else b
    g = g * (k / g_mean) if g_mean > 0 else g
    r = r * (k / r_mean) if r_mean > 0 else r
    balanced = cv2.merge([b, g, r])
    return np.clip(balanced, 0, 255).astype(np.uint8)


def apply_gamma(img):
    return cv2.LUT(img, _gamma_lut)


def process_full(img, awb_on):
    """Full pipeline at native resolution -- only used for saved frames."""
    if awb_on:
        img = gray_world_white_balance(img)
    img = apply_gamma(img)
    if ROTATE_MODE is not None:
        img = cv2.rotate(img, ROTATE_MODE)
    return img


def save_frame(raw_bgr_full, awb_on):
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    img = process_full(raw_bgr_full, awb_on)
    filename = os.path.join(CAPTURE_DIR, f"capture_{time.strftime('%Y%m%d_%H%M%S')}.png")
    ok = cv2.imwrite(filename, img)
    if ok:
        print(f"Saved {filename}")
    else:
        print(f"FAILED to save {filename} -- check that '{CAPTURE_DIR}' is writable.")


def main():
    sensor_mode = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if sensor_mode == 0:
        print("Note: sensor_mode 0 is full 4608x2592 res -- heaviest to process. "
              "Pass '2' for the 1536x864 mode if you want a smoother live feed.")

    with Device.from_id(0) as cam:
        try:
            cam.controls["sensor_mode"].value = sensor_mode
        except Exception as e:
            print(f"Could not set sensor_mode control ({e}), continuing with current mode")

        cam.set_format(BufferType.VIDEO_CAPTURE, 4608, 2592, "RG10")
        fmt = cam.get_format(BufferType.VIDEO_CAPTURE)
        print(f"Negotiated format: {fmt}")

        width, height = fmt.width, fmt.height
        stride_bytes = None  # resolved on first frame

        window_name = "IMX708 Live"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        display_w = min(DISPLAY_WIDTH, width)
        display_h = int(display_w * height / width)
        cv2.resizeWindow(window_name, display_w, display_h)

        print("Streaming... 's' = save frame, 'w' = toggle white balance, 'q' = quit.")
        awb_on = True

        frame_count = 0
        fps_timer = time.time()

        for frame in cam:
            if stride_bytes is None:
                first_bytes = bytes(frame)
                stride_bytes = get_bytesperline(fmt, len(first_bytes), height)
                print(f"Row stride = {stride_bytes} bytes (expected {width * 2})")

            # Demosaic at full native resolution (required for correct color
            # reconstruction).
            img_full = demosaic_rg10_8bit(bytes(frame), width, height, stride_bytes)

            # Downsize FIRST for the live preview -- do the expensive per-pixel
            # AWB/gamma/rotate work on the small image, not the full-res one.
            preview = cv2.resize(img_full, (display_w, display_h), interpolation=cv2.INTER_AREA)
            if awb_on:
                preview = gray_world_white_balance(preview)
            preview = apply_gamma(preview)
            if ROTATE_MODE is not None:
                preview = cv2.rotate(preview, ROTATE_MODE)

            frame_count += 1
            elapsed = time.time() - fps_timer
            if elapsed >= 2.0:
                measured_fps = frame_count / elapsed
                print(f"Measured live-view FPS: {measured_fps:.1f}")
                frame_count = 0
                fps_timer = time.time()

            label = f"AWB: {'on' if awb_on else 'off'}"
            cv2.putText(preview, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1,
                        (0, 255, 0), 2, cv2.LINE_AA)
            cv2.imshow(window_name, preview)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('w'):
                awb_on = not awb_on
                print(f"White balance {'ON' if awb_on else 'OFF'}")
            elif key == ord('s'):
                save_frame(img_full, awb_on)  # full-res, fully processed on demand

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()