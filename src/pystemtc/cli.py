"""Command-line entry point for pySTEMTC V1.

Frozen command surface (FINAL-A A4):

    pystemtc run    --config <defaults.txt> --output <dir>
    pystemtc batch  --config-dir <dir>  --output <dir>

Frozen exit codes (FINAL-A A4):

    0 = all analyses completed successfully
    1 = an analysis (config / input / write) failed
    2 = CLI usage error (bad args / config file unreadable / ...)

The CLI is a thin wrapper over :mod:`pystemtc.engine` and
:mod:`pystemtc.result`; it adds the headless equivalents of two STEM
GUI actions ("Run" and "Run All Configurations in Directory") and does
NOT extend the algorithm surface.

Relative path rule (FINAL-A A4): when a ``defaults.txt`` lists
``Data_File`` / ``Repeat_Data_Files`` as relative paths, the CLI
resolves them against the **directory containing the config file**,
not the current working directory.  This mirrors the Java STEM
behavior where the config-file directory is the natural base for any
files it references.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from .config import STEMConfig
from .engine import STEM
from .errors import STEMTCValueError


def _looks_like_config(path: Path) -> bool:
    """True iff ``path``'s first content line is ``Data_File<TAB>value``.

    Cheap structural probe; avoids a full STEMConfig.from_defaults_file
    parse just to decide whether to skip a non-config file.
    """
    try:
        with path.open("rt", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                key, sep, _ = line.partition("\t")
                return bool(sep) and key.strip().lower() == "data_file"
    except OSError:
        return False
    return False


def _resolve_config_paths(config: STEMConfig, config_dir: Path) -> STEMConfig:
    """Resolve Data_File / Repeat_Data_Files against ``config_dir``.

    Empty entries (Java STEM writes a blank value when the slot is
    unused) are dropped from ``repeat_files`` so the engine sees the
    same input as a GUI user with no repeat file picked.  Absolute
    paths and already-resolved entries are returned unchanged.

    The ``config_dir`` argument is the directory containing the
    ``defaults.txt``; callers that want CWD-relative resolution may
    pass ``Path.cwd()`` instead.
    """
    new_data_file = config.data_file
    if new_data_file:
        candidate = Path(new_data_file)
        if not candidate.is_absolute():
            candidate = (config_dir / candidate).resolve()
        new_data_file = str(candidate)

    new_repeat_files: list[str] = []
    for raw in config.repeat_files:
        token = raw.strip()
        if not token:
            continue
        candidate = Path(token)
        if not candidate.is_absolute():
            candidate = (config_dir / candidate).resolve()
        new_repeat_files.append(str(candidate))

    return replace(config, data_file=new_data_file, repeat_files=new_repeat_files)


def _run_one_config(
    config_path: Path,
    output_dir: Path,
    *,
    encoding: str | None,
    newline: str | None,
) -> list[str]:
    """Execute one config -> output_dir; returns the list of written paths.

    Raises on any analysis / config / I/O failure (caller decides how
    to log it).
    """
    config = STEMConfig.from_defaults_file(config_path)
    config = _resolve_config_paths(config, config_path.resolve().parent)

    if not config.data_file:
        raise STEMTCValueError(
            f"{config_path}: Data_File is empty -- nothing to analyze"
        )
    data_file = Path(config.data_file)
    if not data_file.is_file():
        raise STEMTCValueError(
            f"{config_path}: Data_File not found: {data_file}"
        )

    stem_engine = STEM(
        normalize=config.normalize,
        max_unit_change=config.max_unit_change,
        max_model_profiles=config.max_model_profiles,
        max_correlation=config.max_correlation,
        candidate_cap=config.candidate_cap,
        n_permutations=config.n_permutations,
        permute_t0=config.permute_t0,
        alpha=config.alpha,
        correction=config.correction,
        cluster_min_correlation=config.cluster_min_correlation,
        cluster_corr_percentile=config.cluster_corr_percentile,
        max_missing=config.max_missing,
        min_abs_expr=config.min_abs_expr,
        change_rule="max_minus_min" if config.maxmin else "diff_from_zero",
        repeat_min_correlation=config.repeat_min_correlation,
        repeat_mode=config.repeat_mode,
        spot_included=config.spot_included,
        clustering_method=config.clustering_method,
    )

    result = stem_engine.fit(
        data_file,
        replicates=list(config.repeat_files) or None,
    )
    prefix = config_path.stem
    return result.write_java_tables(
        output_dir, prefix=prefix, encoding=encoding, newline=newline,
    )


def cmd_run(args: argparse.Namespace) -> int:
    """``pystemtc run`` -> one config, exit 0 on success / 1 on failure."""
    config_path = Path(args.config)
    output_dir = Path(args.output)

    if not config_path.is_file():
        print(
            f"pystemtc run: config not found: {config_path}",
            file=sys.stderr,
        )
        return 2

    try:
        paths = _run_one_config(
            config_path,
            output_dir,
            encoding=args.encoding,
            newline=args.newline,
        )
    except STEMTCValueError as exc:
        print(
            f"pystemtc run: configuration / input error in {config_path}: {exc}",
            file=sys.stderr,
        )
        return 1
    except FileNotFoundError as exc:
        print(
            f"pystemtc run: file not found while processing {config_path}: {exc}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # pragma: no cover - defensive net
        print(
            f"pystemtc run: unexpected error in {config_path}: {exc}",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        return 1

    for p in paths:
        print(p)
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    """``pystemtc batch`` -> every config in --config-dir, continue on failure.

    Exit codes:
      0 = every config succeeded
      1 = at least one config failed (analysis / config / I/O)

    CLI usage errors (e.g. the directory does not exist) return 2.
    Per-config analysis / I/O failures are logged to stderr and the
    batch continues with the next config in deterministic order.

    Config detection: a file is treated as a config iff its first
    non-blank, non-``#``-comment line contains a tab-separated key/value
    pair whose key (case-insensitive) is ``Data_File``.  This keeps
    data files (e.g. ``g27_1.txt``) sitting next to the configs from
    being parsed as configs themselves.
    """
    config_dir = Path(args.config_dir)
    output_dir = Path(args.output)

    if not config_dir.is_dir():
        print(
            f"pystemtc batch: config-dir not found: {config_dir}",
            file=sys.stderr,
        )
        return 2

    candidates = sorted(p for p in config_dir.iterdir() if p.is_file())
    configs = [p for p in candidates if _looks_like_config(p)]
    if not configs:
        print(
            f"pystemtc batch: no config files in {config_dir}",
            file=sys.stderr,
        )
        return 0

    failures: list[tuple[Path, str]] = []
    for cfg in configs:
        try:
            paths = _run_one_config(
                cfg, output_dir,
                encoding=args.encoding, newline=args.newline,
            )
        except STEMTCValueError as exc:
            print(
                f"pystemtc batch: configuration / input error in {cfg}: {exc}",
                file=sys.stderr,
            )
            failures.append((cfg, str(exc)))
            continue
        except FileNotFoundError as exc:
            print(
                f"pystemtc batch: file not found while processing {cfg}: {exc}",
                file=sys.stderr,
            )
            failures.append((cfg, str(exc)))
            continue
        except Exception as exc:  # pragma: no cover - defensive net
            print(
                f"pystemtc batch: unexpected error in {cfg}: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc(file=sys.stderr)
            failures.append((cfg, str(exc)))
            continue
        for p in paths:
            print(p)

    if failures:
        print(
            f"pystemtc batch: {len(failures)}/{len(configs)} config(s) failed",
            file=sys.stderr,
        )
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pystemtc",
        description=(
            "pySTEMTC V1 -- headless STEM v1.3.14 clustering. "
            "Run a single config (run) or every config in a directory (batch). "
            "Both commands are thin wrappers over the module API -- for "
            "in-memory / notebook use, see the Python API section in README.md."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run one config file")
    p_run.add_argument("--config", required=True, help="path to defaults.txt")
    p_run.add_argument("--output", required=True, help="output directory")
    p_run.add_argument(
        "--encoding", default=None,
        help="output text encoding (default: platform default; pass 'gbk' for C2 byte-exact vs Java)",
    )
    p_run.add_argument(
        "--newline", default=None,
        help=(
            "output line terminator (default: platform default). "
            "C2 byte-exact output requires a literal CRLF; "
            "shell quoting for CRLF is shell-specific (Bash: $'\\r\\n')."
        ),
    )

    p_batch = sub.add_parser("batch", help="run every config in a directory")
    p_batch.add_argument("--config-dir", required=True, help="directory of defaults.txt files")
    p_batch.add_argument("--output", required=True, help="output directory")
    p_batch.add_argument(
        "--encoding", default=None,
        help="output text encoding (default: platform default; pass 'gbk' for C2 byte-exact vs Java)",
    )
    p_batch.add_argument(
        "--newline", default=None,
        help=(
            "output line terminator (default: platform default). "
            "C2 byte-exact output requires a literal CRLF; "
            "shell quoting for CRLF is shell-specific (Bash: $'\\r\\n')."
        ),
    )

    return parser


_SUBCOMMANDS = {"run": cmd_run, "batch": cmd_batch}


def main(argv: Sequence[str] | None = None) -> int:
    """Process entry point.  Returns a process exit code (0/1/2)."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse already printed usage; map any usage error to exit 2
        # (SystemExit.code is None when argparse calls sys.exit() with no
        # arg, which only happens for --help; treat that as 0)
        code = exc.code
        if code is None or code == 0:
            return 0
        return 2
    handler = _SUBCOMMANDS.get(args.command)
    if handler is None:
        parser.print_help(file=sys.stderr)
        return 2
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
