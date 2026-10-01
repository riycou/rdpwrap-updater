"""AI-generated RDP Wrapper updater. Copyright (c) 2026 riycou. MIT License."""

import argparse, ctypes, hashlib, html, json, os, pathlib, re, struct, sys, difflib
import tempfile, time, urllib.request, urllib.parse, urllib.error, subprocess, threading, queue

ROOT = pathlib.Path(
    getattr(sys, "_MEIPASS", pathlib.Path(__file__).resolve().parents[1])
)
MAIN = [
    "SingleUserPatch",
    "SingleUserOffset",
    "SingleUserCode",
    "DefPolicyPatch",
    "DefPolicyOffset",
    "DefPolicyCode",
    "LocalOnlyPatch",
    "LocalOnlyOffset",
    "LocalOnlyCode",
    "SLInitHook",
    "SLInitOffset",
    "SLInitFunc",
]
SL = [
    "bServerSku",
    "bRemoteConnAllowed",
    "bFUSEnabled",
    "bAppServerAllowed",
    "bMultimonAllowed",
    "lMaxUserSessions",
    "ulMaxDebugSessions",
    "bInitialized",
]


class Refused(ValueError):
    pass


def digest(b):
    return hashlib.sha256(b).hexdigest()


def parse(text, markdown=False):
    if markdown:
        text = html.unescape(text)
        text = re.sub(
            r"</?(?:pre|code|div|p|br|li|tr|td)\b[^>]*>", "\n", text, flags=re.I
        )
        text = re.sub(r"<[^>]*>", "", text)
    sections = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if markdown:
            line = (
                re.sub(r"^>\s*", "", line)
                .replace("**", "")
                .replace("`", "")
                .replace("\\[", "[")
                .replace("\\]", "]")
            )
            if line.startswith("~~~"):
                current = None
                continue
        if not line or line.startswith((";", "#")):
            continue
        m = re.fullmatch(r"\[([^\]]+)\]", line)
        if m:
            current = {}
            sections.setdefault(m[1], []).append(current)
            continue
        if current is not None and "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            v = re.split(r"[;#]", v)[0].strip()
            if k in current and current[k] != v:
                current["!error"] = "duplicate key"
            current[k] = v
    return sections


def unique(parts, name):
    if not parts:
        raise Refused("Missing " + name)
    combined = {}
    for p in parts:
        for k, v in p.items():
            if k in combined and combined[k] != v:
                raise Refused("Conflicting " + name + " " + k)
            combined[k] = v
    return combined


def patch_codes(text):
    p = parse(text)
    return unique(p.get("PatchCodes", []), "PatchCodes")


def validate(main, sl, codes):
    for values, allowed in [(main, MAIN), (sl, SL)]:
        for key, value in values.items():
            if key not in {k + "." + a for k in allowed for a in ["x64", "x86"]}:
                raise Refused("Unexpected/misplaced key " + key)
            if key.split(".")[0].endswith(("Patch", "Hook")):
                if value not in ["0", "1"]:
                    raise Refused("Invalid flag " + key)
            elif key.split(".")[0].endswith("Code"):
                if value not in codes or not re.fullmatch(
                    r"(?:[0-9A-Fa-f]{2})+", codes[value]
                ):
                    raise Refused("Unknown patch code " + value)
            elif key.split(".")[0].endswith("Func"):
                if value != "New_CSLQuery_Initialize":
                    raise Refused("Unknown hook function")
            elif not re.fullmatch(r"[0-9A-Fa-f]{1,8}", value) or int(value, 16) == 0:
                raise Refused("Invalid offset " + key)
    if any(k + ".x64" not in main for k in MAIN) or any(
        k + ".x64" not in sl for k in SL
    ):
        raise Refused("Incomplete x64 profile")
    for a in ["x64", "x86"]:
        for group in ["SingleUser", "DefPolicy", "LocalOnly"]:
            fields = [group + x + "." + a for x in ["Patch", "Offset", "Code"]]
            if any(k in main for k in fields) and (
                fields[0] not in main
                or main[fields[0]] == "1"
                and any(k not in main for k in fields)
            ):
                raise Refused("Incomplete " + group + " " + a)
        if main.get("SLInitHook." + a) == "1" and (
            any(k + "." + a not in main for k in ["SLInitOffset", "SLInitFunc"])
            or any(k + "." + a not in sl for k in SL)
        ):
            raise Refused("Incomplete SLInit " + a)
    return main, sl


def extract(text, version, codes, markdown=False):
    p = parse(text, markdown)
    main = unique(p.get(version, []), version)
    sl = unique(p.get(version + "-SLInit", []), version + "-SLInit")
    for key in [
        v for k, v in main.items() if k.endswith("Code.x64") or k.endswith("Code.x86")
    ]:
        for posted in re.findall(
            r"(?m)^\s*" + re.escape(key) + r"\s*=\s*([0-9A-Fa-f]+)\s*(?:;[^\r\n]*)?$",
            html.unescape(text),
        ):
            if key in codes and posted.upper() != codes[key].upper():
                raise Refused("Posted patch bytes conflict with existing definition")
    return validate(main, sl, codes)


def dll_path():
    return (
        pathlib.Path(os.environ.get("WINDIR", "C:\\Windows"))
        / "System32"
        / "termsrv.dll"
    )


def fixed_version(path):
    lib = ctypes.WinDLL("version", use_last_error=True)
    ignored = ctypes.c_ulong()
    lib.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p]
    lib.GetFileVersionInfoW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
    ]
    lib.VerQueryValueW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    size = lib.GetFileVersionInfoSizeW(str(path), ctypes.byref(ignored))
    if not size:
        raise Refused("Cannot read termsrv fixed version")
    buf = ctypes.create_string_buffer(size)
    if not lib.GetFileVersionInfoW(str(path), 0, size, buf):
        raise Refused("Cannot read DLL version")
    ptr = ctypes.c_void_p()
    length = ctypes.c_uint()
    if not lib.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(length)):
        raise Refused("Missing fixed version")
    words = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint32))
    return ".".join(
        map(str, [words[2] >> 16, words[2] & 65535, words[3] >> 16, words[3] & 65535])
    )


def binary_guard(data, main, sl, codes):
    if data[:2] != b"MZ":
        raise Refused("Invalid DLL")
    pe = struct.unpack_from("<I", data, 60)[0]
    if (
        data[pe : pe + 4] != b"PE\0\0"
        or struct.unpack_from("<H", data, pe + 4)[0] != 0x8664
    ):
        raise Refused("Only x64 Windows supported")
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    start = pe + 24 + opt
    ranges = []
    for n in range(count):
        at = start + 40 * n
        vs, rva, raw = struct.unpack_from("<III", data, at + 8)
        flags = struct.unpack_from("<I", data, at + 36)[0]
        ranges.append((rva, rva + max(vs, raw), flags))
    for values, flag in [(main, 0x20000000), (sl, 0x80000000)]:
        for key, value in values.items():
            if not key.endswith(".x64") or key.split(".")[0].endswith(
                ("Patch", "Hook", "Code", "Func")
            ):
                continue
            size = 4 if values is sl else 1
            if values is main and key.endswith("Offset.x64"):
                code = main.get(key.replace("Offset.", "Code."))
                size = len(codes[code]) // 2 if code else 1
            offset = int(value, 16)
            if not any(
                lo <= offset and offset + size <= hi and flags & flag
                for lo, hi, flags in ranges
            ):
                raise Refused("Offset outside appropriate DLL section: " + key)


def api(route):
    req = urllib.request.Request(
        "https://api.github.com/" + route,
        headers={
            "User-Agent": "RDPWrapUpdater/1.0",
            "Accept": "application/vnd.github+json",
        },
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def live_documents(version):
    query = 'repo:stascorp/rdpwrap is:issue "' + version + '"'
    result = api(
        "search/issues?" + urllib.parse.urlencode({"q": query, "per_page": 100})
    )
    if result.get("incomplete_results") or result["total_count"] > 100:
        raise Refused("Search incomplete; inspect sources manually")
    if not result["items"]:
        query = 'repo:stascorp/rdpwrap is:issue "' + version.split(".")[-1] + '"'
        result = api(
            "search/issues?" + urllib.parse.urlencode({"q": query, "per_page": 100})
        )
        if result.get("incomplete_results") or result["total_count"] > 100:
            raise Refused("Search incomplete")
    docs = []
    for item in result["items"]:
        docs.append((item.get("body") or "", item["html_url"]))
        page = 1
        while True:
            comments = api(
                "repos/stascorp/rdpwrap/issues/"
                + str(item["number"])
                + "/comments?per_page=100&page="
                + str(page)
            )
            docs.extend((c.get("body") or "", c["html_url"]) for c in comments)
            if len(comments) < 100:
                break
            page += 1
    return docs


def recent_documents(cache_path, limit=25, seconds=40):
    """Bounded poll; reuse unchanged threads, commit cache only after complete fetch."""
    cache_path = pathlib.Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + seconds
    requests = 0
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        cache = {}

    def get(route, etag=None):
        nonlocal requests
        remaining = deadline - time.monotonic()
        if remaining <= 0 or requests >= 30:
            raise Refused("Poll time/request budget exhausted; retry next shutdown")
        requests += 1
        headers = {
            "User-Agent": "RDPWrapUpdater/1.2",
            "Accept": "application/vnd.github+json",
        }
        if etag:
            headers["If-None-Match"] = etag
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request("https://api.github.com/" + route, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=min(8, remaining)) as response:
                return json.load(response), response.headers.get("ETag")
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return None, etag
            if e.code in (403, 429):
                raise Refused(
                    "GitHub rate limit/access refusal; no update applied"
                ) from e
            raise

    # Search excludes pull requests and includes closed issues.
    route = "search/issues?" + urllib.parse.urlencode(
        {
            "q": "repo:stascorp/rdpwrap is:issue",
            "sort": "updated",
            "order": "desc",
            "per_page": limit,
        }
    )
    result, etag = get(route, cache.get("etag"))
    if result is None:
        items = cache.get("items", [])
        if not items:
            raise Refused("Conditional response without cache")
    else:
        if result.get("incomplete_results"):
            raise Refused("Incomplete recent-issue search")
        items = result["items"]
    threads = {}
    events = cache.get("history", [])
    changed = []
    for item in items:
        key = str(item["number"])
        old = cache.get("threads", {}).get(key)
        stamp = digest(
            json.dumps(
                {
                    k: item.get(k)
                    for k in [
                        "updated_at",
                        "body",
                        "comments",
                        "state",
                        "labels",
                        "locked",
                    ]
                },
                sort_keys=True,
            ).encode()
        )
        if old and old.get("stamp") == stamp:
            threads[key] = old
            continue
        comments = []
        page = 1
        if item.get("comments", 0):
            while True:
                batch, _ = get(
                    "repos/stascorp/rdpwrap/issues/"
                    + key
                    + "/comments?per_page=100&page="
                    + str(page)
                )
                comments.extend((c.get("body") or "", c["html_url"]) for c in batch)
                if len(batch) < 100:
                    break
                page += 1
        threads[key] = {
            "stamp": stamp,
            "documents": [(item.get("body") or "", item["html_url"])] + comments,
        }
        changed.append(item["number"])
        events.append(
            {
                "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "number": item["number"],
                "url": item["html_url"],
                "updated_at": item["updated_at"],
                "state": item["state"],
                "locked": item.get("locked", False),
                "tags": [x["name"] for x in item.get("labels", [])],
                "change": "changed" if old else "new",
            }
        )
        # Keep completed fetches even if a later thread exhausts the budget.
        cache.setdefault("threads", {})[key] = threads[key]
        cache["history"] = events[-250:]
        atomic_write(cache_path, json.dumps(cache, indent=2).encode())
    saved = {
        "etag": etag,
        "items": items,
        "threads": threads,
        "history": events[-250:],
        "last_poll": {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "requests": requests,
            "changed_issues": changed,
            "tracked_issues": len(items),
        },
    }
    atomic_write(cache_path, json.dumps(saved, indent=2).encode())
    return [tuple(doc) for thread in threads.values() for doc in thread["documents"]]


def render_update(text, version, profile):
    newline = "\r\n" if "\r\n" in text else "\n"
    names = [version, version + "-SLInit"]
    blocks = []
    for name, values in zip(names, profile):
        blocks.append(
            "["
            + name
            + "]"
            + newline
            + newline.join(k + "=" + v for k, v in values.items())
            + newline
        )
    for name in names:
        pattern = r"(?m)^\[" + re.escape(name) + r"\][^\r\n]*(?:\r?\n|$).*?(?=^\[|\Z)"
        text = re.sub(pattern, "", text, flags=re.S)
    return text.rstrip("\r\n") + newline + newline + newline.join(blocks)


def check(path, offline=False, documents=None, offline_file=None):
    path = pathlib.Path(path).resolve()
    original = path.read_bytes()
    if original.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise Refused("UTF-16 INI requires manual review")
    text = original.decode("utf-8-sig")
    codes = patch_codes(text)
    dll = dll_path()
    binary = dll.read_bytes()
    version = fixed_version(dll)
    if documents is not None:
        docs = documents
    elif offline:
        if not offline_file:
            raise Refused(
                "Offline mode requires --offline-file PATH to your own reference INI"
            )
        docs = [
            (
                pathlib.Path(offline_file).read_text(encoding="utf-8-sig"),
                str(pathlib.Path(offline_file).resolve()),
            )
        ]
    else:
        docs = live_documents(version)
    candidates = {}
    observed = {}
    refusals = []
    for body, url in docs:
        parts = parse(body, not offline)
        if version not in parts and version + "-SLInit" not in parts:
            continue
        # Partial posts participate in conflict detection.
        for name in [version, version + "-SLInit"]:
            for section in parts.get(name, []):
                for k, v in section.items():
                    observed.setdefault((name, k), set()).add(v)
        try:
            p = extract(body, version, codes, not offline)
        except Refused as e:
            refusals.append(url + ": " + str(e))
            continue
        if not offline and re.search(
            r"\b(?:not working|doesn.t work|failed|incorrect|wrong offsets)\b",
            body,
            re.I,
        ):
            refusals.append(url + ": failure report requires manual review")
            continue
        signature = json.dumps(p, sort_keys=True)
        candidates.setdefault(signature, {"profile": p, "sources": []})[
            "sources"
        ].append(url)
    if any(len(v) > 1 for v in observed.values()):
        raise Refused(
            "Conflicting posted values for this build; automatic update refused"
        )
    if len(candidates) != 1:
        raise Refused("No unique complete profile. " + "; ".join(refusals[:3]))
    chosen = next(iter(candidates.values()))
    profile = chosen["profile"]
    binary_guard(binary, *profile, codes)
    try:
        same = extract(text, version, codes) == profile
    except Refused:
        same = False
    updated = (
        original
        if same
        else (b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b"")
        + render_update(text, version, profile).encode("utf-8")
    )
    return (
        {
            "ini": str(path),
            "version": version,
            "changed": not same,
            "sources": chosen["sources"],
            "offline": offline,
            "ini_sha256": digest(original),
            "dll_sha256": digest(binary),
            "warnings": refusals,
        },
        original,
        updated,
    )


def atomic_write(path, data):
    fd, temp = tempfile.mkstemp(prefix=".rdpwrap-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def apply(result, original, updated):
    path = pathlib.Path(result["ini"])
    if not result["changed"]:
        return None
    if (
        digest(path.read_bytes()) != result["ini_sha256"]
        or digest(dll_path().read_bytes()) != result["dll_sha256"]
    ):
        raise Refused("INI or DLL changed since check; check again")
    backup = path.with_name(
        path.name
        + ".backup-"
        + time.strftime("%Y%m%d-%H%M%S")
        + "-"
        + str(time.time_ns())
    )
    with backup.open("xb") as f:
        f.write(original)
        f.flush()
        os.fsync(f.fileno())
    atomic_write(path, updated)
    if path.read_bytes() != updated:
        atomic_write(path, original)
        raise Refused("Verification failed; restored backup")
    return str(backup)


def gui(initial):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    window = tk.Tk()
    window.title("RDP Wrapper Updater")
    window.geometry("780x500")
    path = tk.StringVar(value=initial)
    offline = tk.BooleanVar(value=False)
    state = {}
    events = queue.Queue()
    ttk.Label(window, text="Existing rdpwrap.ini").pack(anchor="w", padx=12, pady=8)
    row = ttk.Frame(window)
    row.pack(fill="x", padx=12)
    ttk.Entry(row, textvariable=path).pack(side="left", fill="x", expand=True)
    ttk.Button(
        row,
        text="Browse",
        command=lambda: path.set(
            filedialog.askopenfilename(filetypes=[("INI", "*.ini")]) or path.get()
        ),
    ).pack(side="right")
    ttk.Label(
        window,
        text="Checks issue bodies and comments in stascorp/rdpwrap. Service restart is manual.",
    ).pack(anchor="w", padx=12, pady=8)
    output = tk.Text(window, wrap="word")
    output.pack(fill="both", expand=True, padx=12, pady=8)

    def show(value):
        output.delete("1.0", "end")
        output.insert("end", value)

    def worker():
        try:
            events.put(("ok", check(path.get(), offline.get())))
        except Exception as e:
            events.put(("error", str(e)))

    def run():
        state.clear()
        apply_button.config(state="disabled")
        show("Checking exact DLL build and posted schema…")
        threading.Thread(target=worker, daemon=True).start()

    def commit():
        try:
            r, a, b = state["checked"]
            backup = apply(r, a, b)
            show(
                "Updated. Backup: "
                + str(backup)
                + "\nRestart Remote Desktop Services when your RDP sessions are finished."
            )
            apply_button.config(state="disabled")
        except PermissionError:
            if messagebox.askyesno(
                "Administrator access",
                "Writing this INI requires administrator access. Reopen the updater as administrator? You will need to check and apply again.",
            ):
                args = (
                    [str(pathlib.Path(__file__).resolve())]
                    if not getattr(sys, "frozen", False)
                    else []
                ) + ["--ini", path.get()]
                rc = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    sys.executable,
                    subprocess.list2cmdline(args),
                    None,
                    1,
                )
                if rc <= 32:
                    messagebox.showerror(
                        "Elevation failed",
                        "Administrator launch was cancelled or failed.",
                    )
        except Exception as e:
            messagebox.showerror("Update refused", str(e))

    buttons = ttk.Frame(window)
    buttons.pack(fill="x", padx=12, pady=10)
    ttk.Button(buttons, text="Check for update", command=run).pack(side="left")
    apply_button = ttk.Button(
        buttons, text="Apply validated profile", command=commit, state="disabled"
    )
    apply_button.pack(side="right")

    def poll():
        try:
            status, value = events.get_nowait()
            if status == "error":
                show(value)
            else:
                state["checked"] = value
                r, a, b = value
                diff = "".join(
                    difflib.unified_diff(
                        a.decode("utf-8-sig").splitlines(True),
                        b.decode("utf-8-sig").splitlines(True),
                        fromfile="Existing INI",
                        tofile="Proposed INI",
                    )
                )
                show(
                    json.dumps(r, indent=2)
                    + "\n\n"
                    + (
                        "Ready to apply. A backup will be saved beside your INI.\n\n"
                        + diff
                        if r["changed"]
                        else "Your profile already matches."
                    )
                )
                if r["changed"]:
                    apply_button.config(state="normal")
        except queue.Empty:
            pass
        window.after(100, poll)

    window.after(100, poll)
    window.mainloop()


def main():
    p = argparse.ArgumentParser(
        description="Exact-build RDP Wrapper updater. Default opens a file picker GUI. Service restart is manual."
    )
    p.add_argument("path", nargs="?")
    p.add_argument("--ini")
    p.add_argument("--check", "--dry-run", action="store_true")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument(
        "--auto", action="store_true", help="Check and apply without GUI or prompts"
    )
    p.add_argument(
        "--silent",
        action="store_true",
        help="Suppress terminal output; implies --auto unless --check is supplied",
    )
    p.add_argument("--log", help="Append JSON run records to this file")
    p.add_argument(
        "--recent",
        type=int,
        choices=[25],
        help="Poll only 25 recently updated issues, using a rolling cache",
    )
    p.add_argument("--cache", help="Recent-issue cache JSON path")
    p.add_argument("--offline-file", help="Your own reference INI; requires --offline")
    a = p.parse_args()
    path = (
        a.ini
        or a.path
        or str(
            pathlib.Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
            / "RDP Wrapper"
            / "rdpwrap.ini"
        )
    )
    if a.check and (a.apply or a.auto):
        p.error("--check cannot be combined with --apply or --auto")
    automatic = a.auto or (a.silent and not a.check)
    if not (a.check or a.apply or automatic):
        gui(path)
        return 0
    log = None
    try:
        if a.log or automatic or a.silent:
            logpath = (
                pathlib.Path(a.log)
                if a.log
                else pathlib.Path(
                    os.environ.get("LOCALAPPDATA", str(pathlib.Path.home()))
                )
                / "RDPWrapUpdater"
                / "runs.jsonl"
            )
            logpath.parent.mkdir(parents=True, exist_ok=True)
            log = logpath.open("a", encoding="utf-8")
        if a.recent and a.offline:
            raise Refused("--recent and --offline cannot be combined")
        if a.recent:
            cachepath = a.cache or str(
                pathlib.Path(os.environ.get("LOCALAPPDATA", str(pathlib.Path.home())))
                / "RDPWrapUpdater"
                / "recent-issues.json"
            )
            docs = recent_documents(cachepath, a.recent)
            r, original, updated = check(path, documents=docs)
            r["recent_issue_cache"] = cachepath
        elif a.offline:
            r, original, updated = check(path, True, offline_file=a.offline_file)
        else:
            r, original, updated = check(path)
        if a.apply or automatic:
            r["backup"] = apply(r, original, updated)
        r["status"] = (
            "updated"
            if r.get("backup")
            else "update_available"
            if r["changed"]
            else "already_current"
        )
        if log:
            log.write(
                json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **r}) + "\n"
            )
            log.flush()
        if not a.silent and sys.stdout is not None:
            print(json.dumps(r, indent=2))
        return 0
    except Exception as e:
        failure = {"status": "error", "ini": str(path), "error": str(e)}
        if log:
            try:
                log.write(
                    json.dumps(
                        {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **failure}
                    )
                    + "\n"
                )
                log.flush()
            except OSError:
                pass
        if not a.silent and sys.stdout is not None:
            print(json.dumps(failure))
        return 2
    finally:
        if log:
            log.close()


if __name__ == "__main__":
    sys.exit(main())
