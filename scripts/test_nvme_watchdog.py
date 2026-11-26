#!/usr/bin/env python3
"""Synthetic sysfs unit tests for continuous fail-closed NVMe watchdog (zero SSD load)."""
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nvme_watchdog import NvmeWatchdog, NvmeWatchdogError, probe_nvme, wait_safe_before


def make_fake_nvme(root: Path, state: str = "live", temp_mc: int = 38000, model: str = "KIOXIA-EXCERIA PRO SSD"):
    dev = root / "nvme2"
    hw = dev / "hwmon3"
    hw.mkdir(parents=True, exist_ok=True)
    (dev / "model").write_text(model + "\n", encoding="utf-8")
    (dev / "state").write_text(state + "\n", encoding="utf-8")
    (hw / "temp1_input").write_text(f"{temp_mc}\n", encoding="utf-8")
    return dev, hw / "temp1_input"


class TestNvmeWatchdog(unittest.TestCase):
    def test_live_and_normal_temp_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_fake_nvme(root, state="live", temp_mc=38500)
            sample = wait_safe_before("unit-normal", sysfs_root=root, poll_s=0.05)
            self.assertEqual(sample.state, "live")
            self.assertAlmostEqual(sample.temp_c, 38.5)
            with NvmeWatchdog(poll_s=0.05, sysfs_root=root) as wd:
                time.sleep(0.18)
                wd.raise_if_tripped()
            self.assertFalse(wd.stats.tripped)
            self.assertGreaterEqual(wd.stats.samples, 2)
            self.assertAlmostEqual(wd.stats.max_temp_c, 38.5)

    def test_mid_run_overtemp_kills_process_group(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _, temp_f = make_fake_nvme(root, state="live", temp_mc=40000)
            proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
            try:
                with NvmeWatchdog(target_pid=proc.pid, abort_c=65.0, poll_s=0.05, kill_grace_s=1.0, sysfs_root=root) as wd:
                    time.sleep(0.12)
                    self.assertIsNone(proc.poll())
                    # Inject sudden overheating during active execution
                    temp_f.write_text("66500\n", encoding="utf-8")
                    rc = proc.wait(timeout=3.0)
                    self.assertNotEqual(rc, 0)
                self.assertTrue(wd.stats.tripped)
                self.assertIn("over_temp", wd.stats.trip_reason)
                with self.assertRaises(NvmeWatchdogError):
                    wd.raise_if_tripped()
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=3.0)

    def test_mid_run_controller_drop_kills_process_group(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dev, _ = make_fake_nvme(root, state="live", temp_mc=39000)
            proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
            try:
                with NvmeWatchdog(target_pid=proc.pid, abort_c=65.0, poll_s=0.05, kill_grace_s=1.0, sysfs_root=root) as wd:
                    time.sleep(0.12)
                    (dev / "state").write_text("dead\n", encoding="utf-8")
                    rc = proc.wait(timeout=3.0)
                    self.assertNotEqual(rc, 0)
                self.assertTrue(wd.stats.tripped)
                self.assertIn("controller_state_not_live", wd.stats.trip_reason)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=3.0)

    def test_mid_run_missing_sensor_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _, temp_f = make_fake_nvme(root, state="live", temp_mc=39000)
            proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
            try:
                with NvmeWatchdog(
                    target_pid=proc.pid, abort_c=65.0, poll_s=0.05, max_read_failures=2, kill_grace_s=1.0, sysfs_root=root
                ) as wd:
                    time.sleep(0.10)
                    temp_f.unlink()
                    rc = proc.wait(timeout=3.0)
                    self.assertNotEqual(rc, 0)
                self.assertTrue(wd.stats.tripped)
                self.assertIn("sensor_unreadable", wd.stats.trip_reason)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=3.0)

    def test_cooldown_timeout_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_fake_nvme(root, state="live", temp_mc=58000)
            with self.assertRaises(NvmeWatchdogError) as ctx:
                wait_safe_before("unit-hot", cool_c=55.0, abort_c=65.0, max_wait_s=0.15, poll_s=0.05, sysfs_root=root)
            self.assertIn("fail-closed", str(ctx.exception))

    def test_missing_controller_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(NvmeWatchdogError):
                probe_nvme("KIOXIA", sysfs_root=Path(td))

    def test_real_host_readonly_probe(self):
        # Single read-only sysfs read on live host (zero disk I/O)
        s = probe_nvme("KIOXIA")
        self.assertEqual(s.state, "live")
        self.assertGreater(s.temp_c, 10.0)
        self.assertLess(s.temp_c, 65.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
