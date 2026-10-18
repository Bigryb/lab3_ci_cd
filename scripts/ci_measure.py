import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / ".ci_cache"
REPORTS = ROOT / "reports"


def execute(args, env=None):
    print("COMMAND:", " ".join(map(str, args)), flush=True)
    started = time.perf_counter()
    result = subprocess.run(args, cwd=str(ROOT), env=env, check=False)
    seconds = round(time.perf_counter() - started, 3)
    print("Elapsed: {:.3f} seconds, exit code {}".format(seconds, result.returncode), flush=True)
    return seconds, result.returncode


def main():
    os_name = os.environ.get("MATRIX_OS", "ubuntu")
    python_version = os.environ.get("MATRIX_PYTHON", "3.11")
    shard = int(os.environ.get("SHARD_INDEX", "1"))
    mode = os.environ.get("CACHE_MODE", "none")
    cache_hit = os.environ.get("CACHE_HIT", "false")
    if mode not in ("none", "pip", "wheelhouse"):
        raise ValueError("Unknown cache mode: " + mode)
    if os_name not in ("ubuntu", "alpine") or shard not in (1, 2, 3, 4):
        raise ValueError("Invalid OS or shard index")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "pip").mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "wheels").mkdir(parents=True, exist_ok=True)
    suffix = "{}-py{}-shard{}".format(os_name, python_version, shard)
    xml_path = REPORTS / ("junit-" + suffix + ".xml")
    json_path = REPORTS / ("metrics-" + suffix + ".json")
    print("Matrix: {}, Python {}, shard {}/4".format(os_name, python_version, shard), flush=True)
    print("Cache strategy: {}, exact cache hit: {}".format(mode, cache_hit), flush=True)
    print("Interpreter:", sys.version, flush=True)
    print("Platform:", sys.platform, flush=True)
    start = time.perf_counter()
    env = os.environ.copy()
    download_time = 0.0
    install_time = 0.0
    test_time = 0.0
    test_exit_code = -1
    install_exit_code = -1
    count = 0

    try:
        if mode == "none":
            env["PIP_NO_CACHE_DIR"] = "1"
            install_time, install_exit_code = execute(
                [sys.executable, "-m", "pip", "install", "--no-cache-dir", "-r", "requirements.txt"], env)
        elif mode == "pip":
            env["PIP_CACHE_DIR"] = str(CACHE_DIR / "pip")
            install_time, install_exit_code = execute(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], env)
        else:
            # Download only on cold cache: all wheel files remain in the cache for later runs.
            wheelhouse = CACHE_DIR / "wheels"
            if cache_hit != "true" or not any(wheelhouse.glob("*.whl")):
                download_time, result = execute(
                    [sys.executable, "-m", "pip", "download", "--only-binary=:all:", "--no-cache-dir",
                     "--dest", str(wheelhouse), "-r", "requirements.txt"], env)
                if result:
                    install_exit_code = result
            if install_exit_code == -1:
                install_time, install_exit_code = execute(
                    [sys.executable, "-m", "pip", "install", "--no-index", "--no-cache-dir",
                     "--find-links", str(wheelhouse), "-r", "requirements.txt"], env)
        if install_exit_code == 0:
            test_time, test_exit_code = execute(
                [sys.executable, "-m", "pytest", "-q", "tests/", "--total-shards", "4",
                 "--shard-index", str(shard), "--junitxml", str(xml_path)], env)
            if xml_path.exists():
                tree = ET.parse(str(xml_path))
                suites = tree.findall(".//testsuite")
                count = sum(int(s.attrib.get("tests", "0")) for s in suites)
                if not suites and tree.getroot().tag == "testsuite":
                    count = int(tree.getroot().attrib.get("tests", "0"))
            if count != 60:
                print("ERROR: Expected exactly 60 tests, actual:", count, flush=True)
                test_exit_code = test_exit_code or 1
    except Exception as exc:
        print("ERROR:", repr(exc), flush=True)
        test_exit_code = 1
    finally:
        metric = {
            "os": os_name, "python": python_version, "shard": shard,
            "cache_mode": mode, "cache_hit": cache_hit,
            "download_seconds": download_time, "install_seconds": install_time,
            "test_seconds": test_time,
            "script_seconds": round(time.perf_counter() - start, 3),
            "tests_run": count, "install_exit_code": install_exit_code,
            "test_exit_code": test_exit_code,
        }
        json_path.write_text(json.dumps(metric, ensure_ascii=False, indent=2), encoding="utf-8")
        print("METRICS:", json.dumps(metric, ensure_ascii=False), flush=True)
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
        if summary_path and Path(summary_path).exists():
            with open(summary_path, "a", encoding="utf-8") as summary:
                summary.write("\n### {} / Python {} / shard {}/4\n\n".format(os_name, python_version, shard))
                summary.write("Cache: **{}**, hit: **{}**. Tests: **{}**. ".format(mode, cache_hit, count))
                summary.write("Download: **{:.3f}s**, install: **{:.3f}s**, tests: **{:.3f}s**.\n".format(
                    download_time, install_time, test_time))
    return test_exit_code if install_exit_code == 0 else (install_exit_code or 1)


if __name__ == "__main__":
    sys.exit(main())
