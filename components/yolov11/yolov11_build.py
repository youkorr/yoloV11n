"""
Build script for YOLOV11 component.
Sets up include paths for ESP-DL headers.
ESP-DL sources are compiled in libyolo11_esp_dl.a by yolo11_detection_build.py.
Model data is loaded at runtime via the file component.
"""

import os
import sys
Import("env")

script_dir = Dir('.').srcnode().abspath
component_dir = script_dir
parent_components_dir = os.path.dirname(component_dir)

# Find esp-dl (downloaded by PlatformIO lib_deps or local)
sys.path.insert(0, parent_components_dir)
from esp_dl_path import find_esp_dl
esp_dl_resolved_dir = find_esp_dl(env, fallback_components_dir=parent_components_dir)

print("[YOLOV11] Build script running...")

# ========================================================================
# Detect ISA target from build flags
# ========================================================================
isa_target = "esp32p4"  # default
cpp_defines = env.get('CPPDEFINES', [])
for define in cpp_defines:
    if isinstance(define, tuple):
        key, val = define
    else:
        key = define
        val = None
    if key == "CONFIG_IDF_TARGET_ESP32S3":
        isa_target = "tie728"
        break
    elif key == "CONFIG_IDF_TARGET_ESP32P4":
        isa_target = "esp32p4"
        break

print(f"[YOLOV11] ISA target: {isa_target}")

# ========================================================================
# CONFIG defines (only add if not already set)
# ========================================================================
existing_defines = [d[0] if isinstance(d, tuple) else d for d in cpp_defines]
if "CONFIG_IDF_TARGET_ESP32P4" not in existing_defines and "CONFIG_IDF_TARGET_ESP32S3" not in existing_defines:
    env.Append(CPPDEFINES=[("CONFIG_IDF_TARGET_ESP32P4", "1")])

# ========================================================================
# ESP-DL Include paths (sources are compiled in libyolo11_esp_dl.a)
# ========================================================================
esp_dl_dir = esp_dl_resolved_dir
if os.path.exists(esp_dl_dir):
    esp_dl_include_dirs = [
        "dl", "dl/tool/include", f"dl/tool/isa/{isa_target}",
        "dl/tool/isa/tie728", "dl/tool/isa/xtensa", "dl/tool/isa/esp32p4",
        "dl/tool/src", "dl/tensor/include", "dl/tensor/src",
        "dl/base", "dl/base/isa", f"dl/base/isa/{isa_target}",
        "dl/base/isa/tie728", "dl/base/isa/xtensa", "dl/base/isa/esp32p4",
        "dl/math/include", "dl/math/src", "dl/model/include",
        "dl/model/src", "dl/module/include", "dl/module/src",
        "fbs_loader/include", f"fbs_loader/lib/{isa_target}", "fbs_loader/src",
        "vision/detect", "vision/image", "vision/image/isa",
        f"vision/image/isa/{isa_target}",
        "vision/recognition", "vision/classification",
    ]

    for inc_dir in esp_dl_include_dirs:
        inc_path = os.path.join(esp_dl_dir, inc_dir)
        if os.path.exists(inc_path):
            env.Append(CPPPATH=[inc_path])

    print("[YOLOV11] ESP-DL includes added (sources compiled via libyolo11_esp_dl.a)")

env.Append(CPPPATH=[component_dir])

print("[YOLOV11] Build script completed")
