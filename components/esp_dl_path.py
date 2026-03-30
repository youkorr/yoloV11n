"""
ESP-DL path resolver for PlatformIO/ESPHome builds.
Finds esp-dl in common locations, or downloads it via git clone.
esp-dl is an ESP-IDF component (no library.json), so PlatformIO lib_deps
cannot handle it — we download and compile it manually.
"""

import os
import subprocess


ESP_DL_REPO = "https://github.com/espressif/esp-dl.git"
ESP_DL_TAG = "v3.2.3"


def _check_esp_dl_dir(candidate):
    """Check if a directory contains esp-dl (has dl/ subdirectory)."""
    if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "dl")):
        return candidate
    # esp-dl repo has esp-dl/ subdirectory containing the actual component
    sub = os.path.join(candidate, "esp-dl")
    if os.path.isdir(sub) and os.path.exists(os.path.join(sub, "dl")):
        return sub
    return None


def _git_clone_esp_dl(dest_dir):
    """Clone esp-dl repository to dest_dir."""
    print(f"[ESP-DL] Downloading esp-dl {ESP_DL_TAG} to {dest_dir}...")
    try:
        subprocess.check_call(
            ["git", "clone", "--depth", "1", "--branch", ESP_DL_TAG,
             ESP_DL_REPO, dest_dir],
            timeout=300,
        )
        print(f"[ESP-DL] Download complete: {dest_dir}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"[ESP-DL] git clone failed: {e}")
        return False


def find_esp_dl(env, fallback_components_dir=None):
    """Find esp-dl directory. Downloads via git if not found.

    Search order:
      1. PlatformIO libdeps (in case user added it manually)
      2. ESPHome managed_components
      3. Local components/esp-dl/
      4. .cache/esp-dl/ in project dir (our download location)
      5. Download via git clone

    Args:
        env: PlatformIO SCons environment
        fallback_components_dir: Optional fallback to components/esp-dl/

    Returns:
        Path to the esp-dl component directory (containing dl/, vision/, etc.)
    """
    project_dir = None
    try:
        project_dir = env["PROJECT_DIR"]
    except (KeyError, TypeError):
        pass

    # 1. PlatformIO libdeps
    try:
        pioenv = env["PIOENV"]
        libdeps_dir = os.path.join(project_dir, ".pio", "libdeps", pioenv)
        if os.path.exists(libdeps_dir):
            for name in os.listdir(libdeps_dir):
                candidate = os.path.join(libdeps_dir, name)
                if os.path.isdir(candidate):
                    result = _check_esp_dl_dir(candidate)
                    if result:
                        print(f"[ESP-DL] Found in PlatformIO libdeps: {result}")
                        return result
    except (KeyError, OSError):
        pass

    # 2. ESPHome managed_components
    if project_dir:
        managed_dir = os.path.join(project_dir, "managed_components", "espressif__esp-dl")
        if os.path.isdir(managed_dir) and os.path.exists(os.path.join(managed_dir, "dl")):
            print(f"[ESP-DL] Found in managed_components: {managed_dir}")
            return managed_dir

    # 3. Local components/esp-dl/
    if fallback_components_dir:
        for subpath in ["esp-dl", "esp_dl"]:
            local_dir = os.path.join(fallback_components_dir, subpath)
            result = _check_esp_dl_dir(local_dir)
            if result:
                print(f"[ESP-DL] Found locally: {result}")
                return result

    # 4. Check our cache directory
    if project_dir:
        cache_dir = os.path.join(project_dir, ".cache", "esp-dl")
        result = _check_esp_dl_dir(cache_dir)
        if result:
            print(f"[ESP-DL] Found in cache: {result}")
            return result

        # 5. Download via git clone
        os.makedirs(os.path.join(project_dir, ".cache"), exist_ok=True)
        if _git_clone_esp_dl(cache_dir):
            result = _check_esp_dl_dir(cache_dir)
            if result:
                print(f"[ESP-DL] Downloaded and ready: {result}")
                return result

    raise FileNotFoundError(
        "[ESP-DL] esp-dl not found and download failed!\n"
        "  Please clone manually:\n"
        f"    git clone --depth 1 --branch {ESP_DL_TAG} {ESP_DL_REPO}\n"
        "  And place it in components/esp-dl/ or .cache/esp-dl/"
    )


def get_esp_dl_include_dirs(esp_dl_dir, isa_target="esp32p4"):
    """Return list of include directories for esp-dl."""
    dirs = [
        "dl", "dl/tool/include", f"dl/tool/isa/{isa_target}",
        "dl/tool/src", "dl/tensor/include", "dl/tensor/src",
        "dl/base", "dl/base/isa", f"dl/base/isa/{isa_target}",
        "dl/math/include", "dl/math/src", "dl/model/include",
        "dl/model/src", "dl/module/include", "dl/module/src",
        "fbs_loader/include", f"fbs_loader/lib/{isa_target}", "fbs_loader/src",
        "vision/detect", "vision/image", "vision/image/isa",
        f"vision/image/isa/{isa_target}", "vision/recognition",
        "vision/classification",
    ]

    result = []
    for d in dirs:
        path = os.path.join(esp_dl_dir, d)
        if os.path.exists(path):
            result.append(path)
    return result
