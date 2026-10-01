"""Regression checks for hidden action buttons and an idle startup window."""

import pathlib
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import updater


class GuiTests(unittest.TestCase):
    def exercise(self, select_with_browse, denied=False):
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest("Tkinter unavailable")
        with tempfile.TemporaryDirectory() as directory:
            ini = pathlib.Path(directory) / "rdpwrap.ini"
            ini.write_text("; temporary GUI fixture")
            result = {"changed": denied, "version": "test", "ini": str(ini)}
            expected = "Ready to apply." if denied else "Your profile already matches."

            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)

            def inspect(window):
                try:
                    window.update_idletasks()
                    window.update()
                    controls = {
                        w.cget("text"): w
                        for w in descendants(window)
                        if w.winfo_class() == "TButton"
                    }
                    for geometry in ["780x500", "560x320"]:
                        window.geometry(geometry)
                        window.update_idletasks()
                        window.update()
                        for name in ["Check for update", "Apply validated profile"]:
                            button = controls[name]
                            self.assertTrue(button.winfo_ismapped(), name)
                            bottom = (
                                button.winfo_rooty()
                                - window.winfo_rooty()
                                + button.winfo_height()
                            )
                            self.assertLessEqual(bottom, window.winfo_height(), name)
                    if select_with_browse:
                        controls["Browse"].invoke()
                    deadline = time.monotonic() + 3
                    output = next(
                        w for w in descendants(window) if w.winfo_class() == "Text"
                    )
                    while time.monotonic() < deadline:
                        window.update()
                        if expected in output.get("1.0", "end"):
                            break
                        time.sleep(0.01)
                    self.assertIn(expected, output.get("1.0", "end"))
                    checked.assert_called_once_with(str(ini))
                    applied.assert_not_called()
                    if denied:
                        applied.side_effect = PermissionError("access denied")
                        controls["Apply validated profile"].invoke()
                        applied.assert_called_once()
                        error_dialog.assert_called_once()
                        elevation_dialog.assert_not_called()
                    self.assertEqual(
                        str(controls["Check for update"].cget("state")), "normal"
                    )
                finally:
                    for callback in window.tk.call("after", "info"):
                        window.after_cancel(callback)
                    window.destroy()

            initial = (
                str(ini)
                if not select_with_browse
                else str(pathlib.Path(directory) / "missing.ini")
            )
            with (
                patch.object(tk.Tk, "mainloop", inspect),
                patch.object(
                    updater, "check", return_value=(result, b"", b"")
                ) as checked,
                patch.object(updater, "apply") as applied,
                patch("tkinter.filedialog.askopenfilename", return_value=str(ini)),
                patch("tkinter.messagebox.showerror") as error_dialog,
                patch("tkinter.messagebox.askyesno") as elevation_dialog,
            ):
                updater.gui(initial)

    def test_buttons_visible_and_existing_ini_checked_on_startup(self):
        self.exercise(False)

    def test_browse_starts_read_only_check(self):
        self.exercise(True)

    def test_write_denied_reports_once_without_elevation_retry(self):
        self.exercise(False, denied=True)


if __name__ == "__main__":
    unittest.main()
