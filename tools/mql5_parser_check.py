#!/usr/bin/env python3
"""Parse every MQL5 source in the repository with a real MQL5 grammar.

This is a *syntax* gate only. It proves the sources are well-formed MQL5 —
balanced declarations, statements, terminators — and it proves nothing about
types, MQL5 built-in signatures or `PrintFormat` specifiers. Only MetaEditor
checks those; see `METAEDITOR_PATH` in `tools/mql5_compile_smoke.py`.

The grammar is `mskelton/tree-sitter-mql5`, pinned below. It is cloned into a
cache directory and compiled on first use; nothing about it is committed to
this repository.

The run is only meaningful if the grammar can actually fail, so a negative
control is parsed first: if a deliberately broken snippet parses clean, the
gate reports itself broken instead of reporting the sources clean.

Usage:
    python tools/mql5_parser_check.py
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GRAMMAR_REPO = "https://github.com/mskelton/tree-sitter-mql5.git"
GRAMMAR_COMMIT = "3e4c4fdc5d42b1ec650bf5e6b5464017d05bcccf"
GRAMMAR_LANGUAGE = "tree_sitter_mql5"

# A snippet that must NOT parse. If it does, the gate is worthless and says so.
NEGATIVE_CONTROL = b"""void OnStart()
{
   double x = 1.0
   if (x > 1 {
      Print(x)
   }
}
"""

# A snippet that must parse: struct with fixed-size array members and a
# reference parameter, the pattern `Emtt_Supertrend.mqh` relies on.
POSITIVE_CONTROL = b"""struct SState { double centre[3]; int members[3]; };
double Sum(const double &v[])
{
   double t = 0;
   for (int i = 0; i < ArraySize(v); i++) t += v[i];
   return t;
}
"""


def die(message: str, code: int = 2):
    print(f"mql5 parser check: {message}", file=sys.stderr)
    raise SystemExit(code)


def cache_dir() -> Path:
    override = os.environ.get("EMTT_MQL5_GRAMMAR_DIR")
    if override:
        return Path(override)
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "emtt" / f"tree-sitter-mql5-{GRAMMAR_COMMIT[:12]}"


def fetch_grammar(target: Path) -> Path:
    """Clone the pinned grammar, or reuse it if already present."""
    src = target / "src"
    if (src / "parser.c").is_file():
        return target
    if not shutil.which("git"):
        die("git is required to fetch the MQL5 grammar")
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"cloning {GRAMMAR_REPO} @ {GRAMMAR_COMMIT[:12]}")
    subprocess.run(
        ["git", "clone", "--quiet", "--depth", "1", GRAMMAR_REPO, str(target)],
        check=True,
    )
    # Depth-1 clone of the default branch; pin exactly by fetching the commit.
    subprocess.run(
        ["git", "-C", str(target), "fetch", "--quiet", "--depth", "1", "origin", GRAMMAR_COMMIT],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(target), "checkout", "--quiet", GRAMMAR_COMMIT], check=True
    )
    return target


def build_library(grammar: Path) -> Path:
    """Compile parser.c + scanner.c(c) into a shared object."""
    library = grammar.parent / "mql5.so"
    if library.is_file():
        try:  # a cached library from a broken earlier link must not poison the run
            ctypes.CDLL(str(library))
            return library
        except OSError:
            print("cached library failed to load, rebuilding")
            library.unlink()
    cc = os.environ.get("CC", "cc")
    cxx = os.environ.get("CXX", "g++")
    src = grammar / "src"
    if not (src / "parser.c").is_file():
        die(f"no parser.c under {src}")
    scanner = src / "scanner.cc" if (src / "scanner.cc").is_file() else src / "scanner.c"
    with tempfile.TemporaryDirectory() as work:
        objects = []
        has_cpp = False
        for path in [src / "parser.c"] + ([scanner] if scanner.is_file() else []):
            out = Path(work) / f"{path.stem}.o"
            compiler = cxx if path.suffix in (".cc", ".cpp") else cc
            has_cpp = has_cpp or path.suffix in (".cc", ".cpp")
            print(f"compiling {path.name}")
            subprocess.run(
                [compiler, "-O0", "-fPIC", "-I", str(src), "-c", str(path), "-o", str(out)],
                check=True,
            )
            objects.append(str(out))
        # A C++ scanner needs libstdc++ at link time, so link with the C++ driver.
        linker = cxx if has_cpp else cc
        subprocess.run([linker, "-shared", "-o", str(library), *objects], check=True)
    return library


def load_parser(library: Path):
    try:
        from tree_sitter import Language, Parser
    except ImportError:
        die("py-tree-sitter is required (pip install tree-sitter)")
    handle = ctypes.CDLL(str(library))
    entry = getattr(handle, GRAMMAR_LANGUAGE, None)
    if entry is None:
        die(f"{library} does not export {GRAMMAR_LANGUAGE}")
    entry.restype = ctypes.c_void_p
    with warnings.catch_warnings():
        # py-tree-sitter deprecates the raw-integer Language() form; it is the
        # only form this pinned version accepts from a CDLL entry point.
        warnings.simplefilter("ignore", DeprecationWarning)
        return Parser(Language(entry()))


def parse(parser, source: bytes):
    """Return (root_node, [(line, kind, text), ...])."""
    lines = source.split(b"\n")
    tree = parser.parse(source)
    problems: list[tuple[int, str, str]] = []

    def walk(node) -> None:
        if node.type == "ERROR" or node.is_missing:
            row = node.start_point[0]
            text = lines[row][:72].decode("utf8", "replace").strip()
            problems.append((row + 1, node.type, text))
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return tree.root_node, problems


def controls(parser) -> None:
    """Fail loudly if the grammar cannot distinguish good MQL5 from broken."""
    _, bad = parse(parser, NEGATIVE_CONTROL)
    if not bad:
        die("negative control parsed clean — the grammar is not rejecting broken MQL5")
    good_root, good = parse(parser, POSITIVE_CONTROL)
    if good or good_root.has_error:
        die("positive control failed — the grammar is misparsing valid MQL5")
    print(f"controls: negative rejected ({len(bad)} error node), positive accepted")


def sources() -> list[Path]:
    found = []
    for path in sorted(ROOT.rglob("*.mq*")):
        if path.suffix in (".mq5", ".mqh", ".mq4") and ".git" not in path.parts:
            found.append(path)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep-grammar-dir", action="store_true", help="print the cache path and exit")
    args = ap.parse_args()
    if args.keep_grammar_dir:
        print(cache_dir())
        return 0

    target = cache_dir()
    try:
        grammar = fetch_grammar(target)
        library = build_library(grammar)
    except subprocess.CalledProcessError as exc:
        die(f"could not build the grammar: {exc}")
    parser = load_parser(library)
    controls(parser)
    print()

    files = sources()
    if not files:
        die("no MQL sources found")
    width = max(len(p.relative_to(ROOT).as_posix()) for p in files)
    total_errors = 0
    for path in files:
        source = path.read_bytes()
        root, problems = parse(parser, source)
        digest = hashlib.sha256(source).hexdigest()[:12]
        rel = path.relative_to(ROOT).as_posix()
        print(
            f"{rel:<{width}}  sha256={digest}  nodes={root.descendant_count:<6}"
            f"  has_error={str(root.has_error):<5}  errors={len(problems)}"
        )
        for line, kind, text in problems[:10]:
            print(f"      line {line:>5} [{kind}] {text}")
        total_errors += len(problems)

    print(f"\n{len(files)} MQL source(s) parsed, {total_errors} syntax error(s)")
    return 1 if total_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
