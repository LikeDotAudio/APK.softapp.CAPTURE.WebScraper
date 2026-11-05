# Part of the APK.audio project — http://APK.audio — made by Anthony Kuzub
# MIT Licence. Free, for everyone, for ever. Full text in LICENSE at the root.
"""A common mistake at the command line, said as a plain problem with its way
back, never a traceback (ROAD-3522; doctrine "Every error carries its way back").

    from .cli_problems import guarded      # (apk_webscraper/cli.py)
    sys.exit(guarded(main))

`guarded(main)` runs `main` and turns the mistakes a person makes into the
bench's error catalogue text, with exit 1:

    a missing Python module (ImportError)   -> config_invalid, "pip install X"
    a missing/unreadable file (OSError)     -> file_unreadable
    a file that is not valid JSON           -> bad_json
    a file in the wrong shape (CSV, bytes)  -> bad_input
    no answer from a host in time           -> timeout
    a host or URL that cannot be reached    -> fetch_failed
    no desktop to open a window on          -> config_invalid
    anything else                           -> script_error (APK_DEBUG=1 re-raises it)

The text is `apkaudio_contracts.problems.problem_text(problem(code, detail=…))`
when that package is importable (installed, or the checkout's contracts/python,
found the way DATABASE.Groups/check.py finds it), else a short message, so the
tool still runs with nothing installed. Success is untouched: `guarded` returns
what `main` returns. Standard library only.
"""
import csv
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent

# A module's pip name where it differs from its import name (a wire fact about
# PyPI, not a list of devices). Anything else is installed under its own name.
PIP_NAMES = {"bs4": "beautifulsoup4", "yaml": "PyYAML", "PIL": "pillow", "fitz": "pymupdf",
             "paho": "paho-mqtt", "cv2": "opencv-python"}
# Modules that come with the operating system's Python, not from pip.
DISTRO_PACKAGES = {"tkinter": "python3-tk", "_tkinter": "python3-tk"}


def _catalogue():
    """(problem, problem_text) from apkaudio_contracts, or (None, None)."""
    try:
        from apkaudio_contracts.problems import problem, problem_text
        return problem, problem_text
    except ImportError:
        pass
    checkout = next((q / "contracts" / "python" for q in HERE.parents
                     if (q / "contracts" / "python" / "apkaudio_contracts").is_dir()), None)
    if checkout is None:
        return None, None
    sys.path.append(str(checkout))
    try:
        from apkaudio_contracts.problems import problem, problem_text
        return problem, problem_text
    except ImportError:
        return None, None


def _redact(text):
    """No password in a URL reaches the terminal."""
    return re.sub(r"(://)[^/@\s]+@", r"\1…@", text) if text else text


def say(code, detail=None, subject=None, fix=None):
    """The catalogue's plain text for `code`; a short message without it."""
    detail = _redact(detail)
    problem, problem_text = _catalogue()
    if problem is None:
        head = (detail or code) + (f" — {subject}" if subject else "") + f" [{code}]"
        return "\n".join([head] + [f"  Fix: {step}" for step in fix or []])
    return problem_text(problem(code, detail=detail, subject=subject, fix=list(fix or [])))


def fail(code, detail=None, subject=None, fix=None, status=1):
    """Print the problem on stderr and exit `status`."""
    print(say(code, detail, subject, fix), file=sys.stderr)
    raise SystemExit(status)


def _missing_module(err):
    name = (err.name or "").split(".")[0]
    if not name or any((d / name).is_dir() or (d / f"{name}.py").is_file() for d in (HERE, HERE.parent)):
        return None  # this tool's own module: a broken install, not a missing dependency
    if name in DISTRO_PACKAGES:
        step = f"Install the system package: sudo apt install {DISTRO_PACKAGES[name]} (pip cannot install {name})."
    else:
        step = (f"pip install {PIP_NAMES.get(name, name)} — or install everything this tool needs: "
                "pip install -r requirements.txt (or run its installation.py).")
    return say("config_invalid", detail=f"the Python module '{name}' is not installed",
               subject=name, fix=[step, "Then run the same command again."])


def explain(err):
    """The plain problem for a mistake a person makes, or None for a real bug."""
    if isinstance(err, ImportError):
        return _missing_module(err)
    if isinstance(err, json.JSONDecodeError):
        return say("bad_json", detail=f"line {err.lineno}, column {err.colno}: {err.msg}",
                   fix=["Open the file at that line and column (a missing or trailing comma, or an "
                        "unquoted key, is the usual cause), fix it, and run again."])
    if isinstance(err, (UnicodeDecodeError, csv.Error)):
        return say("bad_input", detail=f"{type(err).__name__}: {err}",
                   fix=["Check the file is the kind this tool reads (text, UTF-8, the expected columns)."])
    kind, module = type(err).__name__, type(err).__module__
    if isinstance(err, TimeoutError) or "Timeout" in kind:
        return say("timeout", detail=str(err))
    if isinstance(err, ConnectionError) or module.split(".")[0] in ("requests", "urllib3", "http") \
            or module == "urllib.error" or kind in ("gaierror", "herror"):
        return say("fetch_failed", detail=str(err),
                   fix=["Check the host or URL is right and answers from this machine (ping it, or open it in a browser)."])
    if isinstance(err, OSError) and getattr(err, "filename", None):
        return say("file_unreadable", detail=f"{err.filename}: {err.strerror or err}",
                   fix=[f"Check {err.filename} exists, is the right path and is readable/writable by you, then run again."])
    if kind == "TclError" and "display" in str(err).lower():
        return say("config_invalid", detail=str(err), subject="DISPLAY",
                   fix=["This is a desktop app: run it in a desktop session (or with DISPLAY set, e.g. ssh -X)."])
    return None


def guarded(main, *args, **kwargs):
    """Run main(*args, **kwargs); a mistake prints its problem and returns 1."""
    try:
        return main(*args, **kwargs)
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 130
    except Exception as err:  # noqa: BLE001 — the last resort; APK_DEBUG=1 keeps the traceback
        text = explain(err) or say("script_error", detail=f"{type(err).__name__}: {err}",
                                   fix=["Run again with APK_DEBUG=1 to see the traceback, and report it."])
        print(text, file=sys.stderr)
        if os.environ.get("APK_DEBUG") == "1":
            raise
        return 1
