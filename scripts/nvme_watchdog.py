#!/usr/bin/env python3
"""Continuous, fail-closed NVMe controller health & thermal watchdog (read-only sysfs).

Design goals (addressing Phase 2 independent audit findings):
  1. Continuous background monitoring WHILE a workload/server is running (not only pre-run).
  2. Fail-closed on missing controller, non-'live' controller state, or unreadable/missing
     temperature sensor (never silently returns None or 0C).
  3. Pre-run cooldown fails closed if temperature remains >= cool_c after max_wait_s.
  4. Immediately terminates the tracked process group (SIGTERM -> SIGKILL fallback) on trip.
  5. Zero disk I/O: reads only sysfs attributes (/sys/class/nvme/...).
"""
from __future__ import annotations

import os
import signal
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


class NvmeWatchdogError(RuntimeError):
    """Raised when NVMe health/temperature check or continuous watchdog trips."""


@dataclass(frozen=True)
class NvmeSample:
    device: str
    model: str
    state: str
    temp_c: float
    timestamp: float


def probe_nvme(model_substr: str = "KIOXIA", sysfs_root: Path = Path("/sys/class/nvme")) -> NvmeSample:
    """Read controller state and composite temperature (fail-closed on any missing/corrupt field)."""
    if not sysfs_root.exists():
        raise NvmeWatchdogError(f"NVMe sysfs root not found: {sysfs_root}")
    matched_dir: Optional[Path] = None
    matched_model = ""
    want = model_substr.upper()
    for d in sorted(sysfs_root.glob("nvme*")):
        model_p = d / "model"
        if not model_p.is_file():
            continue
        try:
            model = model_p.read_text(encoding="utf-8", errors="replace").strip()
        except OSError as exc:
            raise NvmeWatchdogError(f"Cannot read {model_p}: {exc}") from exc
        if want in model.upper():
            matched_dir = d
            matched_model = model
            break
    if matched_dir is None:
        raise NvmeWatchdogError(f"No NVMe controller matching '{model_substr}' found under {sysfs_root}")

    state_p = matched_dir / "state"
    try:
        state = state_p.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        raise NvmeWatchdogError(f"Cannot read controller state {state_p}: {exc}") from exc

    temp_files = sorted(matched_dir.glob("hwmon*/temp1_input"))
    if not temp_files:
        raise NvmeWatchdogError(f"Temperature sensor missing for {matched_dir.name} ({matched_model})")
    try:
        raw_mc = int(temp_files[0].read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        raise NvmeWatchdogError(f"Unreadable temperature sensor {temp_files[0]}: {exc}") from exc
    if raw_mc <= -50000 or raw_mc >= 200000:
        raise NvmeWatchdogError(f"Implausible NVMe sensor reading {raw_mc} mC on {matched_dir.name}")

    return NvmeSample(
        device=matched_dir.name,
        model=matched_model,
        state=state,
        temp_c=raw_mc / 1000.0,
        timestamp=time.monotonic(),
    )


def wait_safe_before(
    tag: str,
    model_substr: str = "KIOXIA",
    cool_c: float = 55.0,
    abort_c: float = 65.0,
    max_wait_s: float = 60.0,
    poll_s: float = 5.0,
    sysfs_root: Path = Path("/sys/class/nvme"),
) -> NvmeSample:
    """Pre-run fail-closed check with bounded cooldown. Raises NvmeWatchdogError if unsafe."""
    deadline = time.monotonic() + max_wait_s
    while True:
        sample = probe_nvme(model_substr=model_substr, sysfs_root=sysfs_root)
        if sample.state != "live":
            raise NvmeWatchdogError(
                f"ABORT before {tag}: {sample.device} ({sample.model}) state='{sample.state}' != 'live'"
            )
        if sample.temp_c >= abort_c:
            raise NvmeWatchdogError(
                f"ABORT before {tag}: {sample.device} temperature {sample.temp_c:.1f}C >= {abort_c:.1f}C"
            )
        if sample.temp_c < cool_c:
            return sample
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise NvmeWatchdogError(
                f"ABORT before {tag}: {sample.device} remained at {sample.temp_c:.1f}C >= {cool_c:.1f}C "
                f"after {max_wait_s:.0f}s cooldown (fail-closed)"
            )
        sleep_for = min(poll_s, remaining)
        print(
            f"  [nvme-guard] {sample.device} {sample.temp_c:.1f}C >= {cool_c:.1f}C before {tag}; "
            f"cooling {sleep_for:.1f}s...",
            flush=True,
        )
        time.sleep(sleep_for)


@dataclass
class WatchdogStats:
    samples: int = 0
    min_temp_c: Optional[float] = None
    max_temp_c: Optional[float] = None
    last_state: Optional[str] = None
    tripped: bool = False
    trip_reason: Optional[str] = None
    errors: list[str] = field(default_factory=list)


class NvmeWatchdog:
    """Continuous background monitor that kills the target process group immediately on fault."""

    def __init__(
        self,
        target_pid: Optional[int] = None,
        model_substr: str = "KIOXIA",
        abort_c: float = 65.0,
        poll_s: float = 1.0,
        max_read_failures: int = 2,
        kill_grace_s: float = 3.0,
        sysfs_root: Path = Path("/sys/class/nvme"),
        on_trip: Optional[Callable[[str], None]] = None,
    ):
        self.target_pid = target_pid
        self.model_substr = model_substr
        self.abort_c = abort_c
        self.poll_s = poll_s
        self.max_read_failures = max(1, max_read_failures)
        self.kill_grace_s = kill_grace_s
        self.sysfs_root = sysfs_root
        self.on_trip = on_trip
        self.stats = WatchdogStats()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    def set_target_pid(self, pid: Optional[int]) -> None:
        with self._lock:
            self.target_pid = pid

    def _terminate_target(self) -> None:
        with self._lock:
            pid = self.target_pid
        if pid is None or pid <= 1:
            return
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except OSError:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                return
        end = time.monotonic() + self.kill_grace_s
        while time.monotonic() < end:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.05)
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except OSError:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def _trip(self, reason: str) -> None:
        with self._lock:
            if self.stats.tripped:
                return
            self.stats.tripped = True
            self.stats.trip_reason = reason
            self.stats.errors.append(reason)
        print(f"  [nvme-watchdog] TRIP: {reason} — terminating target process group!", flush=True)
        self._terminate_target()
        if self.on_trip is not None:
            try:
                self.on_trip(reason)
            except Exception:
                pass
        self._stop.set()

    def _loop(self) -> None:
        consec_failures = 0
        while not self._stop.is_set():
            try:
                sample = probe_nvme(model_substr=self.model_substr, sysfs_root=self.sysfs_root)
                consec_failures = 0
                with self._lock:
                    self.stats.samples += 1
                    self.stats.last_state = sample.state
                    if self.stats.min_temp_c is None or sample.temp_c < self.stats.min_temp_c:
                        self.stats.min_temp_c = sample.temp_c
                    if self.stats.max_temp_c is None or sample.temp_c > self.stats.max_temp_c:
                        self.stats.max_temp_c = sample.temp_c
                if sample.state != "live":
                    self._trip(f"controller_state_not_live: {sample.device} state='{sample.state}'")
                    return
                if sample.temp_c >= self.abort_c:
                    self._trip(f"over_temp: {sample.device} {sample.temp_c:.1f}C >= {self.abort_c:.1f}C")
                    return
            except NvmeWatchdogError as exc:
                consec_failures += 1
                with self._lock:
                    self.stats.errors.append(str(exc))
                if consec_failures >= self.max_read_failures:
                    self._trip(f"sensor_unreadable ({consec_failures}x): {exc}")
                    return
            self._stop.wait(self.poll_s)

    def start(self) -> "NvmeWatchdog":
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="nvme-watchdog", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> WatchdogStats:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        return self.stats

    def raise_if_tripped(self) -> None:
        with self._lock:
            if self.stats.tripped:
                raise NvmeWatchdogError(f"Continuous NVMe watchdog tripped: {self.stats.trip_reason}")

    def __enter__(self) -> "NvmeWatchdog":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
