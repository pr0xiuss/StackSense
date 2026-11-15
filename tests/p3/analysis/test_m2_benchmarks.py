"""Benchmark harness for M2 parsing, memory, and cap proposals."""

from __future__ import annotations

import json
import resource
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path
from uuid import UUID, uuid4

from backend.platform.analysis.inspection.model import _serialize_json_value
from backend.platform.analysis.syntax.base import ParserRequest, ParserResult
from backend.platform.analysis.syntax.executor import ParserExecutor
from backend.platform.analysis.syntax.javascript import TreeSitterJsTsAdapter
from backend.platform.analysis.syntax.python import PythonAstAdapter


def _generate_synthetic_python(size_bytes: int) -> bytes:
    """Generate deterministic valid Python source code of approximate target size."""
    chunks = ["# Synthetic Python Benchmark File\n\n"]
    curr_size = len(chunks[0].encode("utf-8"))
    idx = 0
    while curr_size < size_bytes:
        chunk = (
            f"def func_{idx}(arg_a: int, arg_b: str) -> bool:\n"
            f'    """Docstring for function {idx}."""\n'
            f"    return arg_a > len(arg_b)\n\n"
        )
        chunks.append(chunk)
        curr_size += len(chunk.encode("utf-8"))
        idx += 1
    return "".join(chunks).encode("utf-8")


def _generate_synthetic_javascript(size_bytes: int) -> bytes:
    """Generate deterministic valid JavaScript source of approximate target size."""
    chunks = ["// Synthetic JavaScript Benchmark File\n\n"]
    curr_size = len(chunks[0].encode("utf-8"))
    idx = 0
    while curr_size < size_bytes:
        chunk = (
            f"function computeValue_{idx}(val, factor) {{\n"
            f"  const res = val * factor;\n"
            f"  return res;\n"
            f"}}\n\n"
        )
        chunks.append(chunk)
        curr_size += len(chunk.encode("utf-8"))
        idx += 1
    return "".join(chunks).encode("utf-8")


def _linux_peak_rss_bytes() -> int:
    """Read this process's address-space high-water RSS from procfs."""
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("Linux procfs did not expose VmHWM")


def _run_isolated_memory_case(
    name: str, language: str, size_bytes: int, artifact_id: str
) -> None:
    """Child entry point emitting one parser workload measurement as JSON."""
    content = (
        _generate_synthetic_python(size_bytes)
        if language == "python"
        else _generate_synthetic_javascript(size_bytes)
    )
    adapter = PythonAstAdapter() if language == "python" else TreeSitterJsTsAdapter()
    result = adapter.parse(
        ParserRequest(
            artifact_id=UUID(artifact_id),
            path=f"synthetic/{name}",
            content=content,
            language=language,
        )
    )
    document = result.document
    serialized_bytes = (
        len(json.dumps(_serialize_json_value(document), sort_keys=True))
        if document is not None
        else 0
    )
    print(
        json.dumps(
            {
                "success": result.success,
                "fact_count": len(document.facts) if document is not None else 0,
                "serialized_bytes": serialized_bytes,
                "peak_rss_bytes": _linux_peak_rss_bytes(),
            },
            sort_keys=True,
        )
    )


def _measure_isolated_peak_rss(
    name: str, language: str, size_bytes: int, artifact_id: UUID
) -> dict[str, int | bool]:
    """Measure a workload in a clean exec address space, independent of pytest."""
    if sys.platform != "linux":
        raise RuntimeError("Isolated parser RSS measurement requires Linux procfs")
    script = (
        "from tests.p3.analysis.test_m2_benchmarks import "
        "_run_isolated_memory_case; "
        f"_run_isolated_memory_case({name!r}, {language!r}, {size_bytes}, "
        f"{str(artifact_id)!r})"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        text=True,
        timeout=60.0,
    )
    assert completed.returncode == 0, completed.stderr
    output = json.loads(completed.stdout)
    assert isinstance(output, dict)
    return output


def test_m2_benchmark_representative_fixtures() -> None:
    """Benchmark representative Python, JS, TS, and TSX files."""
    fixtures_dir = (
        Path(__file__).resolve().parent.parent.parent / "fixtures" / "p3" / "m2"
    )
    assert fixtures_dir.is_dir()

    targets = [
        ("sample_python.py", "python"),
        ("sample_js.js", "javascript"),
        ("sample_ts.ts", "typescript"),
        ("sample_tsx.tsx", "tsx"),
    ]

    py_adapter = PythonAstAdapter()
    js_adapter = TreeSitterJsTsAdapter()

    results = []

    for filename, language in targets:
        filepath = fixtures_dir / filename
        assert filepath.is_file()
        content = filepath.read_bytes()

        adapter = py_adapter if language == "python" else js_adapter
        req = ParserRequest(
            artifact_id=uuid4(),
            path=f"fixtures/{filename}",
            content=content,
            language=language,
        )

        tracemalloc.start()
        start_time = time.perf_counter()

        res1: ParserResult = adapter.parse(req)
        exec_time = time.perf_counter() - start_time
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert res1.success is True
        assert res1.document is not None

        # Re-run for determinism verification
        res2: ParserResult = adapter.parse(req)
        assert res2.document is not None
        assert len(res1.document.facts) == len(res2.document.facts)

        serialized_bytes = len(
            json.dumps(_serialize_json_value(res1.document), sort_keys=True)
        )

        results.append(
            {
                "file": filename,
                "language": language,
                "file_size_bytes": len(content),
                "fact_count": len(res1.document.facts),
                "serialized_bytes": serialized_bytes,
                "exec_time_ms": round(exec_time * 1000, 2),
                "peak_mem_kb": round(peak_mem / 1024, 2),
            }
        )

    print("\n--- M2 Representative Fixture Benchmark Results ---")
    for r in results:
        print(
            f"File: {r['file']} ({r['language']}) | "
            f"Size: {r['file_size_bytes']} B | "
            f"Facts: {r['fact_count']} | "
            f"JSON: {r['serialized_bytes']} B | "
            f"Time: {r['exec_time_ms']} ms | "
            f"Peak RAM: {r['peak_mem_kb']} KB"
        )
    print("---------------------------------------------------\n")


def test_m2_benchmark_synthetic_and_boundary_files() -> None:
    """Benchmark small/median files and 1 MiB high-fact-density stress cases."""
    if sys.platform != "linux":
        import pytest

        pytest.skip("Independent parser RSS measurement requires Linux procfs")

    py_adapter = PythonAstAdapter()
    js_adapter = TreeSitterJsTsAdapter()

    cases = [
        ("small_python_1kb", "python", _generate_synthetic_python(1024)),
        ("small_js_1kb", "javascript", _generate_synthetic_javascript(1024)),
        ("median_python_50kb", "python", _generate_synthetic_python(50 * 1024)),
        ("median_js_50kb", "javascript", _generate_synthetic_javascript(50 * 1024)),
        ("boundary_python_1mb", "python", _generate_synthetic_python(1024 * 1024)),
        ("boundary_js_1mb", "javascript", _generate_synthetic_javascript(1024 * 1024)),
    ]

    benchmark_records = []

    for name, language, content in cases:
        adapter = py_adapter if language == "python" else js_adapter
        req = ParserRequest(
            artifact_id=uuid4(),
            path=f"synthetic/{name}",
            content=content,
            language=language,
        )

        # Wall-clock deadlines measure only the extractor in this process.
        # Memory is measured separately in a clean exec address space below so
        # launcher/test-order high-water marks cannot contaminate the result.
        start_time = time.perf_counter()
        res = adapter.parse(req)
        exec_time = time.perf_counter() - start_time

        assert res.success is True
        assert res.document is not None

        serialized_bytes = len(
            json.dumps(_serialize_json_value(res.document), sort_keys=True)
        )
        isolated = _measure_isolated_peak_rss(
            name, language, len(content), req.artifact_id
        )
        assert isolated["success"] is True
        assert isolated["fact_count"] == len(res.document.facts)
        assert isolated["serialized_bytes"] == serialized_bytes
        peak_mem_mb = int(isolated["peak_rss_bytes"]) / (1024 * 1024)

        record = {
            "name": name,
            "language": language,
            "size_bytes": len(content),
            "fact_count": len(res.document.facts),
            "serialized_bytes": serialized_bytes,
            "exec_time_seconds": round(exec_time, 4),
            "peak_mem_mb": round(peak_mem_mb, 2),
        }
        benchmark_records.append(record)

    print("\n--- M2 Synthetic & Boundary Benchmark Records ---")
    for rec in benchmark_records:
        print(
            f"Case: {rec['name']} | "
            f"Size: {rec['size_bytes'] / 1024:.1f} KB | "
            f"Facts: {rec['fact_count']} | "
            f"JSON Size: {rec['serialized_bytes'] / 1024:.1f} KB | "
            f"Time: {rec['exec_time_seconds']:.3f} s | "
            f"RAM: {rec['peak_mem_mb']} MB"
        )
    print("---------------------------------------------------\n")

    # Maxima recorded:
    max_facts_per_mb = max(
        r["fact_count"] / (r["size_bytes"] / (1024 * 1024)) for r in benchmark_records
    )
    print(f"Max fact density observed: ~{int(max_facts_per_mb)} facts/MB")

    # Assert bounded execution
    for rec in benchmark_records:
        assert rec["exec_time_seconds"] < 30.0  # within 30s deadline
        assert rec["peak_mem_mb"] < 512.0  # isolated workload boundary


def test_m2_benchmark_exact_five_mib_isolated_boundary() -> None:
    """Measure exact 5 MiB inputs through the production child sandbox."""
    if sys.platform != "linux":
        import pytest

        pytest.skip("The production parser sandbox currently targets Linux workers")

    boundary = 5 * 1024 * 1024
    cases = (
        ("python", b"#" + (b"x" * (boundary - 2)) + b"\n"),
        ("javascript", b"/*" + (b"x" * (boundary - 4)) + b"*/"),
    )
    executor = ParserExecutor()
    records = []

    for language, content in cases:
        assert len(content) == boundary
        parent_rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        child_rss_before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        started = time.perf_counter()
        result = executor.execute(
            ParserRequest(
                artifact_id=uuid4(),
                path=f"synthetic/boundary_5mib.{language}",
                content=content,
                language=language,
            )
        )
        elapsed = time.perf_counter() - started
        parent_rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        child_rss_after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss

        assert result.success is True, result.error_message
        assert result.document is not None
        assert elapsed < 30.0
        records.append(
            {
                "language": language,
                "size_bytes": len(content),
                "facts": len(result.document.facts),
                "elapsed_seconds": round(elapsed, 4),
                "parent_peak_rss_kib": max(parent_rss_before, parent_rss_after),
                "child_peak_rss_kib": max(child_rss_before, child_rss_after),
            }
        )

    print("\n--- M2 Exact 5 MiB Isolated Boundary Records ---")
    for record in records:
        print(
            f"Language: {record['language']} | Size: 5.0 MiB | "
            f"Facts: {record['facts']} | Time: {record['elapsed_seconds']:.3f}s | "
            f"Parent peak RSS: {record['parent_peak_rss_kib']} KiB | "
            f"Child peak RSS: {record['child_peak_rss_kib']} KiB"
        )
