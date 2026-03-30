"""
Build script for YOLOV11 component.
Compiles ESP-DL sources and sets up include paths.
Supports both ESP32-P4 and ESP32-S3 targets.
The model is loaded at runtime via the file component.
"""

import os
import sys
import glob
Import("env")

script_dir = Dir('.').srcnode().abspath
component_dir = script_dir
parent_components_dir = os.path.dirname(component_dir)

# Find esp-dl (downloaded by PlatformIO lib_deps or local)
sys.path.insert(0, parent_components_dir)
from esp_dl_path import find_esp_dl
esp_dl_resolved_dir = find_esp_dl(env, fallback_components_dir=parent_components_dir)

print("[YOLOV11] Build script running...")
print(f"[YOLOV11] ESP-DL resolved to: {esp_dl_resolved_dir}")

# ========================================================================
# Detect target platform from build flags
# ========================================================================
# ISA target for assembly: "esp32p4" or "tie728" (ESP32-S3)
# Chip target for FBS libs: "esp32p4" or "esp32s3"
isa_target = "esp32p4"
chip_target = "esp32p4"

cpp_defines = env.get('CPPDEFINES', [])
for define in cpp_defines:
    if isinstance(define, tuple):
        key, val = define
    else:
        key = define
        val = None
    if key == "CONFIG_IDF_TARGET_ESP32S3":
        isa_target = "tie728"
        chip_target = "esp32s3"
        break
    elif key == "CONFIG_IDF_TARGET_ESP32P4":
        isa_target = "esp32p4"
        chip_target = "esp32p4"
        break

print(f"[YOLOV11] Target: chip={chip_target}, isa={isa_target}")

# ========================================================================
# CONFIG defines (only add if not already set)
# ========================================================================
existing_defines = [d[0] if isinstance(d, tuple) else d for d in cpp_defines]
if "CONFIG_IDF_TARGET_ESP32P4" not in existing_defines and "CONFIG_IDF_TARGET_ESP32S3" not in existing_defines:
    env.Append(CPPDEFINES=[("CONFIG_IDF_TARGET_ESP32P4", "1")])

sources_to_add = []

# ========================================================================
# ESP-DL: Include paths + Source compilation
# ========================================================================
esp_dl_dir = esp_dl_resolved_dir
if os.path.exists(esp_dl_dir):
    # Include directories - cover all ISA variants so headers resolve
    esp_dl_include_dirs = [
        "dl",
        "dl/tool/include",
        f"dl/tool/isa/{isa_target}",
        "dl/tool/isa/esp32p4",
        "dl/tool/isa/tie728",
        "dl/tool/isa/xtensa",
        "dl/tool/src",
        "dl/tensor/include",
        "dl/tensor/src",
        "dl/base",
        "dl/base/isa",
        f"dl/base/isa/{isa_target}",
        "dl/base/isa/esp32p4",
        "dl/base/isa/tie728",
        "dl/base/isa/xtensa",
        "dl/math/include",
        "dl/math/src",
        "dl/model/include",
        "dl/model/src",
        "dl/module/include",
        "dl/module/src",
        "fbs_loader/include",
        f"fbs_loader/lib/{chip_target}",
        "fbs_loader/src",
        "vision/detect",
        "vision/image",
        "vision/image/isa",
        f"vision/image/isa/{isa_target}",
        "vision/recognition",
        "vision/classification",
    ]

    for inc_dir in esp_dl_include_dirs:
        inc_path = os.path.join(esp_dl_dir, inc_dir)
        if os.path.exists(inc_path):
            env.Append(CPPPATH=[inc_path])

    print("[YOLOV11] ESP-DL include paths added")

    # ====================================================================
    # Compile ESP-DL source files
    # ====================================================================
    # Core directories (always needed)
    esp_dl_source_dirs = [
        "dl/tensor/src",
        "dl/model/src",
        "dl/module/src",
        "dl/tool/src",
        "dl/math/src",
        "fbs_loader/src",
        "vision/image",      # Image preprocessing (required)
        "vision/detect",     # Detection postprocessors (YOLO11)
    ]

    # Files to exclude (audio/ is NOT in source dirs - not needed for YOLO11)
    esp_dl_exclude = [
        "dl_base_dotprod.cpp",                  # Use custom no-DSP implementation
        "dl_image_jpeg.cpp",                    # JPEG not used
        "dl_image_bmp.cpp",                     # BMP not used
        # Exclude non-YOLO11 postprocessors
        "dl_detect_msr_postprocessor.cpp",      # Face detection specific
        "dl_detect_mnp_postprocessor.cpp",      # Face detection specific
        "dl_pose_yolo11_postprocessor.cpp",     # Pose only
    ]

    # Directories to skip entirely (even if found by recursive glob)
    esp_dl_exclude_dirs = ["audio", "examples", "docs", "test"]

    sources_count = {"base": 0, "isa": 0, "core": 0, "vision": 0}

    # Add sources from specific directories
    for src_dir in esp_dl_source_dirs:
        src_dir_path = os.path.join(esp_dl_dir, src_dir)
        if os.path.exists(src_dir_path):
            if src_dir.startswith("vision/"):
                # Recursive glob for vision subdirectories
                pattern = os.path.join(src_dir_path, "**", "*.cpp")
                for src_file in glob.glob(pattern, recursive=True):
                    # Skip excluded directories (audio/, examples/, etc.)
                    skip = False
                    for excl_dir in esp_dl_exclude_dirs:
                        if os.sep + excl_dir + os.sep in src_file or src_file.endswith(os.sep + excl_dir):
                            skip = True
                            break
                    if skip or os.path.basename(src_file) in esp_dl_exclude:
                        continue
                    sources_to_add.append(src_file)
                    sources_count["vision"] += 1
            else:
                for src_file in glob.glob(os.path.join(src_dir_path, "*.cpp")):
                    if os.path.basename(src_file) not in esp_dl_exclude:
                        sources_to_add.append(src_file)
                        sources_count["core"] += 1

    # Add ALL dl/base/*.cpp files (required for neural network operations)
    dl_base_dir = os.path.join(esp_dl_dir, "dl", "base")
    if os.path.exists(dl_base_dir):
        for src_file in glob.glob(os.path.join(dl_base_dir, "*.cpp")):
            if os.path.basename(src_file) not in esp_dl_exclude:
                sources_to_add.append(src_file)
                sources_count["base"] += 1

    # Add ISA-specific files (optimized assembly for target platform)
    isa_dirs = [
        (f"dl/base/isa/{isa_target}", "*.S"),
        (f"dl/base/isa/{isa_target}", "*.cpp"),
        (f"dl/tool/isa/{isa_target}", "*.S"),
        (f"vision/image/isa/{isa_target}", "*.S"),
    ]

    for isa_dir, pattern in isa_dirs:
        isa_path = os.path.join(esp_dl_dir, isa_dir)
        if os.path.exists(isa_path):
            for asm_file in glob.glob(os.path.join(isa_path, pattern)):
                sources_to_add.append(asm_file)
                sources_count["isa"] += 1

    esp_dl_total = sum(sources_count.values())
    print(f"[YOLOV11] ESP-DL: {esp_dl_total} files "
          f"(base:{sources_count['base']} isa:{sources_count['isa']} "
          f"core:{sources_count['core']} vision:{sources_count['vision']})")

    # Add prebuilt FBS model loader library
    fbs_lib_dir = os.path.join(esp_dl_dir, "fbs_loader", "lib", chip_target)
    fbs_lib = os.path.join(fbs_lib_dir, "libfbs_model.a")
    if os.path.exists(fbs_lib):
        env.Append(LIBPATH=[fbs_lib_dir])
        env.Prepend(LIBS=["fbs_model"])
        print(f"[YOLOV11] Added libfbs_model.a ({chip_target})")
    else:
        print(f"[YOLOV11] WARNING: libfbs_model.a not found at {fbs_lib}")
else:
    print(f"[YOLOV11] ERROR: ESP-DL not found at {esp_dl_dir}")

# ========================================================================
# Add local stub files
# ========================================================================
dotprod_file = os.path.join(component_dir, "dl_base_dotprod_no_dsp.cpp")
if os.path.exists(dotprod_file):
    sources_to_add.append(dotprod_file)
    print("[YOLOV11] + dl_base_dotprod_no_dsp.cpp")

mbedtls_stub = os.path.join(component_dir, "mbedtls_aes_stub.c")
if os.path.exists(mbedtls_stub):
    sources_to_add.append(mbedtls_stub)
    print("[YOLOV11] + mbedtls_aes_stub.c")

env.Append(CPPPATH=[component_dir])

# ========================================================================
# Compile all sources into static library
# ========================================================================
if sources_to_add:
    objects = []
    for src_file in sources_to_add:
        try:
            obj = env.Object(src_file)
            objects.extend(obj)
        except Exception as e:
            print(f"[YOLOV11] Failed to compile {os.path.basename(src_file)}: {e}")

    if objects:
        lib = env.StaticLibrary(
            os.path.join("$BUILD_DIR", "libyolov11_esp_dl"),
            objects
        )

        env.Append(LINKFLAGS=["-Wl,--start-group"])
        env.Prepend(LIBS=[lib])
        env.Append(LINKFLAGS=["-Wl,--end-group"])

        env.Append(PIOBUILDFILES=objects)

        print(f"[YOLOV11] {len(sources_to_add)} source files -> libyolov11_esp_dl.a")
else:
    print("[YOLOV11] WARNING: No sources to compile!")

print("[YOLOV11] Build script completed")
