import sys, pathlib, unittest, tempfile, json
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import updater as u


class Tests(unittest.TestCase):
    def test_recent_poll_cache_changes_and_rate_limit(self):
        import urllib.error, io, copy

        class Response:
            def __init__(self, data):
                self.data = io.BytesIO(json.dumps(data).encode())
                self.headers = {"ETag": "test-etag"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self, *args):
                return self.data.read(*args)

        item = {
            "number": 42,
            "updated_at": "first",
            "body": "issue",
            "comments": 1,
            "html_url": "https://github.com/stascorp/rdpwrap/issues/42",
            "state": "closed",
            "labels": [{"name": "solved"}],
            "locked": True,
        }
        calls = []
        current = copy.deepcopy(item)
        mode = ["normal"]

        def request(req, **kwargs):
            calls.append(req.full_url)
            if mode[0] == "rate":
                raise urllib.error.HTTPError(req.full_url, 403, "rate limit", {}, None)
            if "search/issues" in req.full_url:
                if mode[0] == "unchanged":
                    raise urllib.error.HTTPError(
                        req.full_url, 304, "unchanged", {}, None
                    )
                return Response({"items": [current], "incomplete_results": False})
            return Response(
                [{"body": "comment", "html_url": "https://github.com/comment/42"}]
            )

        with (
            tempfile.TemporaryDirectory() as d,
            patch.object(u.urllib.request, "urlopen", side_effect=request),
        ):
            p = pathlib.Path(d) / "cache.json"
            self.assertEqual(len(u.recent_documents(p)), 2)
            self.assertEqual(len(calls), 2)
            mode[0] = "unchanged"
            calls.clear()
            self.assertEqual(len(u.recent_documents(p)), 2)
            self.assertEqual(len(calls), 1)
            mode[0] = "normal"
            current["updated_at"] = "second"
            calls.clear()
            u.recent_documents(p)
            self.assertEqual(len(calls), 2)
            saved = json.loads(p.read_text())
            self.assertEqual(len(saved["history"]), 2)
            self.assertEqual(saved["history"][-1]["tags"], ["solved"])
            before = p.read_bytes()
            mode[0] = "rate"
            with self.assertRaises(u.Refused):
                u.recent_documents(p)
            self.assertEqual(before, p.read_bytes())

    def test_silent_auto_and_error_logging(self):
        import io, contextlib

        with tempfile.TemporaryDirectory() as d:
            log = pathlib.Path(d) / "runs.jsonl"
            result = {"changed": True, "ini": "temporary.ini", "version": "test"}
            args = [
                "updater",
                "--auto",
                "--silent",
                "--ini",
                "temporary.ini",
                "--log",
                str(log),
            ]
            with (
                patch.object(sys, "argv", args),
                patch.object(u, "check", return_value=(result, b"old", b"new")),
                patch.object(u, "apply", return_value="backup") as apply,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(u.main(), 0)
                apply.assert_called_once()
                self.assertEqual(output.getvalue(), "")
            self.assertEqual(
                json.loads(log.read_text().splitlines()[0])["status"], "updated"
            )
            with (
                patch.object(sys, "argv", args),
                patch.object(u, "check", side_effect=u.Refused("conflicting offsets")),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(u.main(), 2)
                self.assertEqual(output.getvalue(), "")
            self.assertEqual(
                json.loads(log.read_text().splitlines()[-1])["status"], "error"
            )

    def setUp(self):
        # Fictional fixtures exercise parsing; these are NOT real Windows offsets.
        self.codes = {
            "mov_eax_1_nop_2": "B8010000009090",
            "policy": "EB",
            "jmpshort": "EB",
        }
        main = {
            k + ".x64": (
                "1"
                if k.endswith(("Patch", "Hook"))
                else "mov_eax_1_nop_2"
                if k == "SingleUserCode"
                else "policy"
                if k == "DefPolicyCode"
                else "jmpshort"
                if k == "LocalOnlyCode"
                else "New_CSLQuery_Initialize"
                if k.endswith("Func")
                else "1100"
            )
            for k in u.MAIN
        }
        sl = {k + ".x64": "2100" for k in u.SL}
        self.version = "10.0.0.1"
        self.profile = (main, sl)
        self.text = (
            "[PatchCodes]\n"
            + "\n".join(k + "=" + v for k, v in self.codes.items())
            + "\n"
        )
        for n in range(1, 761):
            name = "10.0.0." + str(n)
            self.text += (
                "\n".join(
                    "[" + s + "]\n" + "\n".join(k + "=" + v for k, v in d.items())
                    for s, d in zip([name, name + "-SLInit"], self.profile)
                )
                + "\n"
            )
        self.fixture = "\n".join(
            "[" + n + "]\n" + "\n".join(k + "=" + v for k, v in d.items())
            for n, d in zip([self.version, self.version + "-SLInit"], self.profile)
        )

    def test_all_complete_profiles_and_mutations(self):
        cases = 0
        valid = 0
        sections = u.parse(self.text)
        for name, parts in sections.items():
            if not __import__("re").fullmatch(r"\d+\.\d+\.\d+\.\d+", name):
                continue
            try:
                profile = u.validate(
                    u.unique(parts, name),
                    u.unique(sections.get(name + "-SLInit", []), name + "-SLInit"),
                    self.codes,
                )
            except u.Refused:
                continue
            fixture = "\n".join(
                "[" + n + "]\n" + "\n".join(k + "=" + v for k, v in d.items())
                for n, d in zip([name, name + "-SLInit"], profile)
            )
            for s in [
                fixture,
                fixture.replace("\n", "\r\n"),
                "```ini\n" + fixture + "\n```",
                "\n".join("> " + x for x in fixture.splitlines()),
                "<pre>" + fixture + "</pre>",
            ]:
                self.assertEqual(u.extract(s, name, self.codes, True), profile)
                valid += 1
            for key in profile[0]:
                for bad in ["GG", "-1", "0", "123456789", "true"]:
                    if bad == "0" and key.split(".")[0].endswith(("Patch", "Hook")):
                        continue
                    s = fixture.replace(key + "=" + profile[0][key], key + "=" + bad)
                    with self.assertRaises(u.Refused):
                        u.extract(s, name, self.codes)
                    cases += 1
            for s in [
                fixture + "\nUnknown.x64=1",
                fixture.replace("bServerSku.x64", "bServerSku.х64"),
                fixture + "\n[" + name + "]\nSingleUserOffset.x64=1",
                fixture.replace(
                    "SLInitFunc.x64=New_CSLQuery_Initialize", "SLInitFunc.x64=Other"
                ),
            ]:
                with self.assertRaises(u.Refused):
                    u.extract(s, name, self.codes)
                cases += 1
        self.assertGreater(valid, 3500)
        print(
            "Production parser:",
            valid,
            "valid formats;",
            cases,
            "invalid mutations rejected",
        )

    def test_merge_preserves_other_sections(self):
        base = "; hello\r\n[PatchCodes]\r\na=EB\r\n[Other]\r\nx=1\r\n"
        merged = u.render_update(base, self.version, self.profile)
        self.assertTrue(merged.startswith(base))
        self.assertEqual(u.extract(merged, self.version, self.codes), self.profile)

    def test_backup_atomic_and_race(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "rdpwrap.ini"
            dll = pathlib.Path(d) / "termsrv.dll"
            dll.write_bytes(b"dll")
            path.write_bytes(b"original")
            r = {
                "ini": str(path),
                "changed": True,
                "ini_sha256": u.digest(b"original"),
                "dll_sha256": u.digest(b"dll"),
            }
            with patch.object(u, "dll_path", return_value=dll):
                backup = u.apply(r, b"original", b"updated")
                self.assertEqual(path.read_bytes(), b"updated")
                self.assertEqual(pathlib.Path(backup).read_bytes(), b"original")
                with self.assertRaises(u.Refused):
                    u.apply(r, b"original", b"other")

    def test_failed_replace_keeps_original(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "file"
            p.write_bytes(b"original")
            with patch.object(u.os, "replace", side_effect=PermissionError):
                with self.assertRaises(PermissionError):
                    u.atomic_write(p, b"new")
            self.assertEqual(p.read_bytes(), b"original")
            self.assertEqual(len(list(pathlib.Path(d).iterdir())), 1)

    def test_binary_rejects_out_of_range(self):
        import struct

        data = bytearray(512)
        data[:2] = b"MZ"
        struct.pack_into("<I", data, 60, 64)
        data[64:68] = b"PE\0\0"
        struct.pack_into("<H", data, 68, 0x8664)
        struct.pack_into("<H", data, 70, 2)
        struct.pack_into("<H", data, 84, 0)
        for at, rva, flags in [(88, 0x1000, 0x20000000), (128, 0x2000, 0x80000000)]:
            struct.pack_into("<III", data, at + 8, 0x1000, rva, 0x1000)
            struct.pack_into("<I", data, at + 36, flags)
        u.binary_guard(data, *self.profile, self.codes)
        main = dict(self.profile[0])
        main["SingleUserOffset.x64"] = "FFFFFFFF"
        with self.assertRaises(u.Refused):
            u.binary_guard(data, main, self.profile[1], self.codes)

    def test_conflicting_posted_bytes(self):
        with self.assertRaises(u.Refused):
            u.extract(self.fixture + "\nmov_eax_1_nop_2=EB", self.version, self.codes)


if __name__ == "__main__":
    unittest.main()
