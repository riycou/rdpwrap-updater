# Third-party material

This project reads public issue discussions from [stascorp/rdpwrap](https://github.com/stascorp/rdpwrap). That project's code has its own [Apache-2.0 license](https://github.com/stascorp/rdpwrap/blob/master/LICENSE). Profile authors and community contributors deserve credit for the offsets they publish.

The MIT license here covers this updater's original code, tests, and documentation. It does not relicense community profiles, Windows binaries, GitHub issue text, Python, Tcl/Tk, or PyInstaller. No collected INI corpus or Microsoft DLL is included in the public repository or release. Local cache data remains on the machine running the updater.

`assets/base.ini` derives its global Main, SLPolicy and PatchCodes sections from upstream commit `326551985f1ecf8cc1e43bd4b4505a7871534b0f`. Build-specific sections were removed, modification notices were added, and modern patch definitions were added from the explicitly cited issue comment. Attribution and source URLs are retained in the INI and `assets/base-provenance.json`. The upstream-derived configuration is distributed with `licenses/RDPWrap-Apache-2.0.txt`; the updater's MIT license does not replace those terms. The base contains no build offsets.

Portable executables bundle the Python runtime, Tcl/Tk, and the PyInstaller bootloader. Copies of their distribution licenses are included in the release's `licenses` directory. PyInstaller's bootloader distribution exception permits packaging an application under its own license. See the bundled notices for the exact terms.
