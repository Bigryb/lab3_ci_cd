import csv
import json
from collections import defaultdict
from pathlib import Path
import statistics
import sys


def main():
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("collected-reports")
    files = sorted(directory.glob("**/metrics-*.json"))
    if not files:
        print("No metrics JSON artifacts were downloaded")
        return 1
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    keys = {(r["os"], r["python"], r["shard"]) for r in rows}
    expected = {(os_name, version, shard)
                for os_name in ("ubuntu", "alpine")
                for version in ("3.9", "3.11", "3.12")
                for shard in (1, 2, 3, 4)}
    modes = {r["cache_mode"] for r in rows}
    if len(modes) != 1:
        print("Invalid, mixed cache modes:", modes)
        return 1

    directory.mkdir(parents=True, exist_ok=True)
    summary_csv = directory / "summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as fout:
        fieldnames = ["cache_mode", "os", "python", "shard", "cache_hit",
                      "download_seconds", "install_seconds", "test_seconds",
                      "script_seconds", "tests_run", "install_exit_code", "test_exit_code"]
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    groups = defaultdict(list)
    for row in rows:
        groups[(row["os"], row["python"])].append(row)
    print("\nCACHE MODE:", next(iter(modes)), "\n")
    print("Environment           jobs  cache hits  avg download  avg install  avg tests  slowest script")
    for (os_name, version), group in sorted(groups.items()):
        print("{:<9} Python {:<5}  {:>2}    {:>2}/{:<2}      {:>8.2f}s    {:>8.2f}s    {:>8.2f}s    {:>8.2f}s".format(
            os_name, version, len(group), sum(r["cache_hit"] == "true" for r in group),
            len(group), statistics.mean(r["download_seconds"] for r in group),
            statistics.mean(r["install_seconds"] for r in group),
            statistics.mean(r["test_seconds"] for r in group),
            max(r["script_seconds"] for r in group)))

    hit_count = sum(r["cache_hit"] == "true" for r in rows)
    print("\nTotal cache hits: {}/{}".format(hit_count, len(rows)))
    print("Average download: {:.3f}s".format(statistics.mean(r["download_seconds"] for r in rows)))
    print("Average install: {:.3f}s".format(statistics.mean(r["install_seconds"] for r in rows)))
    print("Average tests: {:.3f}s".format(statistics.mean(r["test_seconds"] for r in rows)))
    print("Saved:", summary_csv)

    problems = sorted(expected - keys)
    duplicates = len(keys) != len(rows)
    failures = [r for r in rows if r["install_exit_code"] != 0 or r["test_exit_code"] != 0 or r["tests_run"] != 60]
    if problems or duplicates or failures:
        print("INCOMPLETE OR FAILED MATRIX", problems, "duplicate combos:", duplicates, "failures:", failures)
        return 1
    print("SUCCESS: 24/24 jobs, 60 passed per shard, 1440 total test executions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
