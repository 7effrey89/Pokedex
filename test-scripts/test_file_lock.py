import errno
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from src.utils.file_lock import exclusive_file_lock


class FileLockTests(unittest.TestCase):
    def test_windows_blocking_lock_waits_through_contention_without_ten_second_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "index.lock"
            locking = mock.Mock(side_effect=[
                *[PermissionError(errno.EACCES, "busy") for _ in range(210)],
                OSError(errno.EDEADLK, "busy"), None, None,
            ])
            windows = SimpleNamespace(locking=locking, LK_NBLCK=2, LK_UNLCK=0)
            with mock.patch("src.utils.file_lock.os.name", "nt"), \
                 mock.patch.dict("sys.modules", {"msvcrt": windows}), \
                 mock.patch("src.utils.file_lock.time.sleep") as sleep:
                with exclusive_file_lock(path):
                    pass
            self.assertGreater(sum(call.args[0] for call in sleep.call_args_list), 10)
            self.assertEqual([2] * 212 + [0], [call.args[1] for call in locking.call_args_list])

    def test_nonblocking_contention_and_unexpected_errors_are_not_swallowed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "index.lock"
            for blocking, error in (
                (False, PermissionError(errno.EACCES, "busy")),
                (True, OSError(errno.EIO, "disk failure")),
            ):
                windows = SimpleNamespace(locking=mock.Mock(side_effect=error), LK_NBLCK=2, LK_UNLCK=0)
                with mock.patch("src.utils.file_lock.os.name", "nt"), \
                     mock.patch.dict("sys.modules", {"msvcrt": windows}), \
                     mock.patch("src.utils.file_lock.time.sleep") as sleep:
                    with self.assertRaises(OSError):
                        with exclusive_file_lock(path, blocking=blocking):
                            self.fail("Lock must not be acquired")
                    sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
