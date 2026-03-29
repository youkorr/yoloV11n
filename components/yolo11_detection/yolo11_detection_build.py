"""
Build script for YOLO11 Detection component.
Embeds the YOLO11 model in flash rodata AND compiles ESP-DL sources.
Based on the working face_detection_build.py pattern from test2_esp_video_esphome.
"""

import os
import sys
import glob
import subprocess
Import("env")

script_dir = Dir('.').srcnode().abspath
component_dir = script_dir
parent_components_dir = os.path.dirname(component_dir)

print("[YOLO11 Detection] Build script running...")

# ========================================================================
# Find ESP-DL (downloaded by PlatformIO lib_deps or local)
# ========================================================================
sys.path.insert(0, parent_components_dir)
from esp_dl_path import find_esp_dl
esp_dl_resolved_dir = find_esp_dl(env, fallback_components_dir=parent_components_dir)

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

print(f"[YOLO11 Detection] ISA target: {isa_target}")

# ========================================================================
# Add CONFIG defines
# ========================================================================
existing_defines = [d[0] if isinstance(d, tuple) else d for d in cpp_defines]

if "CONFIG_IDF_TARGET_ESP32P4" not in existing_defines and "CONFIG_IDF_TARGET_ESP32S3" not in existing_defines:
    env.Append(CPPDEFINES=[("CONFIG_IDF_TARGET_ESP32P4", "1")])

# ========================================================================
# Helper function for caching
# ========================================================================
def needs_rebuild(output_file, input_files):
    """Check if output_file needs to be rebuilt."""
    if not os.path.exists(output_file):
        return True
    output_mtime = os.path.getmtime(output_file)
    for input_file in input_files:
        if os.path.exists(input_file):
            if os.path.getmtime(input_file) > output_mtime:
                return True
    return False

sources_to_add = []

# ========================================================================
# Embed YOLO11 Detection Model in flash rodata
# ========================================================================
yolo11_detect_dir = os.path.join(parent_components_dir, "yolo11_detect")
if os.path.exists(yolo11_detect_dir):
    models_dir = os.path.join(yolo11_detect_dir, "models", "p4")
    pack_script = os.path.join(yolo11_detect_dir, "pack_model.py")

    if os.path.exists(models_dir):
        yolo11_model = os.path.join(models_dir, "yolo11_detect_s8_v1.espdl")

        if os.path.exists(yolo11_model):
            embed_c_file = os.path.join(component_dir, "yolo11_detect_espdl_embed.c")

            if needs_rebuild(embed_c_file, [yolo11_model]):
                model_file = yolo11_model

                # Try pack_model.py first
                if os.path.exists(pack_script):
                    print("[YOLO11 Detection] Packing yolo11_detect model...")
                    packed_model = os.path.join(component_dir, "yolo11_detect.espdl")
                    try:
                        cmd = [
                            "python3", pack_script,
                            "--model_path", yolo11_model,
                            "--out_file", packed_model
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                        if result.returncode == 0 and os.path.exists(packed_model):
                            model_file = packed_model
                        else:
                            print(f"[YOLO11 Detection] pack_model.py failed, using raw model")
                    except Exception as e:
                        print(f"[YOLO11 Detection] pack_model.py error: {e}, using raw model")

                # Generate C embed file
                with open(model_file, 'rb') as f:
                    model_data = f.read()

                c_content = '// Auto-generated - embedded yolo11_detect model\n'
                c_content += '#include <stddef.h>\n'
                c_content += '#include <stdint.h>\n\n'
                c_content += '__attribute__((aligned(16)))\n'
                c_content += 'const uint8_t _binary_yolo11_detect_espdl_start[] = {\n'

                for i in range(0, len(model_data), 16):
                    chunk = model_data[i:i+16]
                    hex_bytes = ', '.join(f'0x{b:02x}' for b in chunk)
                    c_content += f'    {hex_bytes},\n'

                c_content += '};\n\n'
                c_content += f'const uint8_t *_binary_yolo11_detect_espdl_end = '
                c_content += f'_binary_yolo11_detect_espdl_start + {len(model_data)};\n'
                c_content += f'const size_t _binary_yolo11_detect_espdl_size = {len(model_data)};\n'

                with open(embed_c_file, 'w') as f:
                    f.write(c_content)
                print(f"[YOLO11 Detection] Model embedded: {len(model_data)} bytes -> {embed_c_file}")
            else:
                print("[YOLO11 Detection] Model embed cached (skip)")

            if os.path.exists(embed_c_file):
                sources_to_add.append(embed_c_file)
                print(f"[YOLO11 Detection] + yolo11_detect_espdl_embed.c")
        else:
            print(f"[YOLO11 Detection] WARNING: Model not found: {yolo11_model}")
    else:
        print(f"[YOLO11 Detection] WARNING: Models dir not found: {models_dir}")
else:
    print(f"[YOLO11 Detection] WARNING: yolo11_detect dir not found: {yolo11_detect_dir}")

# ========================================================================
# ESP-DL Sources - Compile all necessary files (like face_detection_build.py)
# ========================================================================
esp_dl_dir = esp_dl_resolved_dir
if os.path.exists(esp_dl_dir):
    # Add include directories
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

    print("[YOLO11 Detection] ESP-DL include paths added")

    # ESP-DL source directories - core (always needed)
    esp_dl_source_dirs = [
        "dl/tensor/src",
        "dl/model/src",
        "dl/module/src",
        "dl/tool/src",
        "dl/math/src",
        "fbs_loader/src",
        "vision/image",      # Image processing (required)
        "vision/detect",     # Detection postprocessors
    ]

    print("[YOLO11 Detection] Including: vision/detect (YOLO11)")

    # Files to exclude
    esp_dl_exclude = [
        "dl_base_dotprod.cpp",       # Use custom no-DSP implementation
        "dl_image_jpeg.cpp",         # JPEG not used
        "dl_image_bmp.cpp",          # BMP not used
        # Exclude non-YOLO11 postprocessors
        "dl_detect_msr_postprocessor.cpp",      # Face detection specific
        "dl_detect_mnp_postprocessor.cpp",      # Face detection specific
        "dl_pose_yolo11_postprocessor.cpp",     # Pose only
    ]

    # Count files by category
    sources_count = {"base": 0, "isa": 0, "core": 0, "vision": 0}

    # Add sources from specific directories
    for src_dir in esp_dl_source_dirs:
        src_dir_path = os.path.join(esp_dl_dir, src_dir)
        if os.path.exists(src_dir_path):
            # Use recursive glob for vision/* directories
            if src_dir.startswith("vision/"):
                pattern = os.path.join(src_dir_path, "**", "*.cpp")
                for src_file in glob.glob(pattern, recursive=True):
                    if os.path.basename(src_file) not in esp_dl_exclude:
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

    # Add ISA-specific files (optimized assembly)
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
    print(f"[YOLO11 Detection] ESP-DL: {esp_dl_total} files "
          f"(base:{sources_count['base']} isa:{sources_count['isa']} "
          f"core:{sources_count['core']} vision:{sources_count['vision']})")

    # Add prebuilt FBS library
    fbs_lib_dir = os.path.join(esp_dl_dir, "fbs_loader", "lib", isa_target)
    fbs_lib = os.path.join(fbs_lib_dir, "libfbs_model.a")
    if os.path.exists(fbs_lib):
        env.Append(LIBPATH=[fbs_lib_dir])
        env.Prepend(LIBS=["fbs_model"])
        print(f"[YOLO11 Detection] Added libfbs_model.a from {fbs_lib_dir}")
    else:
        print(f"[YOLO11 Detection] WARNING: libfbs_model.a not found at {fbs_lib}")

else:
    print(f"[YOLO11 Detection] ERROR: ESP-DL not found at {esp_dl_dir}")

# ========================================================================
# Add local stub files
# ========================================================================
# Custom dotprod implementation (no DSP version)
dotprod_file = os.path.join(component_dir, "dl_base_dotprod_no_dsp.cpp")
if os.path.exists(dotprod_file):
    sources_to_add.append(dotprod_file)
    print("[YOLO11 Detection] + dl_base_dotprod_no_dsp.cpp")

# mbedTLS stub (for unencrypted models)
mbedtls_stub = os.path.join(component_dir, "mbedtls_aes_stub.c")
if os.path.exists(mbedtls_stub):
    sources_to_add.append(mbedtls_stub)
    print("[YOLO11 Detection] + mbedtls_aes_stub.c")

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
            print(f"[YOLO11 Detection] Failed to compile {os.path.basename(src_file)}: {e}")

    if objects:
        # Create static library (libyolo11_esp_dl.a)
        lib = env.StaticLibrary(
            os.path.join("$BUILD_DIR", "libyolo11_esp_dl"),
            objects
        )

        # Add library with proper linking flags for circular dependencies
        env.Append(LINKFLAGS=["-Wl,--start-group"])
        env.Prepend(LIBS=[lib])
        env.Append(LINKFLAGS=["-Wl,--end-group"])

        # Also add objects directly to ensure they're linked
        env.Append(PIOBUILDFILES=objects)

        print(f"[YOLO11 Detection] {len(sources_to_add)} source files compiled")
        print(f"[YOLO11 Detection] {len(objects)} object files created")
        print("[YOLO11 Detection] libyolo11_esp_dl.a created and linked")
else:
    print("[YOLO11 Detection] WARNING: No sources to compile!")

print("[YOLO11 Detection] Build script completed")
