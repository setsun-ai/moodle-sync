"""
Step 2: upload DOWNLOAD_DIR to cloud storage with rclone.

rclone supports 70+ services: Google Drive, OneDrive (many universities give
students Microsoft 365 with 1 TB), Dropbox, Nextcloud, ... - the remote is
configured once with `rclone config`. Without RCLONE_REMOTE this step is
skipped, which is fine if DOWNLOAD_DIR already is a synced folder (e.g.
inside "Google Drive for desktop" or OneDrive on your PC).

We use `rclone copy`, NOT `rclone sync`:
  - copy only adds/updates files in the cloud and never deletes anything,
  - sync would mirror the local folder - clearing DOWNLOAD_DIR (e.g. to free
    space on a Raspberry Pi SD card) would wipe your materials in the cloud.
With KEEP_LOCAL=0 we use `rclone move`: a file disappears locally only after
a successful upload, and state.json remembers it was downloaded.

rclone compares size + modification time; the download step sets mtime to
the time the file was modified in Moodle, so only new or replaced files are
sent. --update also protects files you edited in the cloud (they're newer).
"""

import json
import os
import posixpath
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from . import config, state as state_mod
from .i18n import t

SKIPPED = 2

# Low memory use for a Raspberry Pi 3 (512 MB RAM): rclone buffers one chunk
# per parallel transfer, so 2 x 8 MB instead of the default 4 x 8 MB. With a
# few hundred files, Wi-Fi is the bottleneck anyway, not parallelism.
RCLONE_FLAGS = [
    "--transfers", "2",
    "--checkers", "4",
    "--drive-chunk-size", "8M",  # ignored by non-Google remotes
    "--fast-list",
    "--update",
    "--exclude", "*.part",
    "--exclude", "*.relocating",
    "--stats-one-line",
    "--stats", "30s",
    "--stats-log-level", "NOTICE",
]
# rclone exit codes: 3 = directory not found, 4 = file not found
RCLONE_NOT_FOUND = {3, 4}
MAX_MOVE_ATTEMPTS = 5
BACKUP_FILES = ["state.json", "courses.json", "przedmioty.json"]


def rclone(*args: str, quiet: bool = False) -> int:
    """
    Run rclone and pass its output through print(): only then does it reach the log,
    the error notification and /errors in the bot (a child process writing straight
    to the terminal would bypass them - errors used to show just the commands).
    """
    cmd = [config.rclone_bin(), *args]
    if not quiet:
        print("$", " ".join(cmd), flush=True)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace")
    for line in proc.stdout:
        if not quiet or "ERROR" in line:
            print("  " + line.rstrip(), flush=True)
    return proc.wait()


def remote_configured() -> bool:
    out = subprocess.run([config.rclone_bin(), "listremotes"], capture_output=True, text=True)
    return f"{config.rclone_remote()}:" in out.stdout.split()


def status() -> tuple[bool, str]:
    """(usable?, reason) - used by `doctor` and to decide whether to skip."""
    if not config.rclone_remote():
        return False, t("storage_disabled")
    if shutil.which(config.rclone_bin()) is None:
        return False, t("storage_no_rclone", bin=config.rclone_bin())
    if not remote_configured():
        return False, t("storage_no_remote", remote=config.rclone_remote())
    return True, f"{config.rclone_remote()}:{config.remote_dest()}"


def target(path: str = "") -> str:
    base = f"{config.rclone_remote()}:{config.remote_dest()}"
    return f"{base}/{path}" if path else base


def remote_files() -> set[str] | None:
    """All file paths under the target folder (one rclone call), or None if listing failed."""
    out = subprocess.run(
        [config.rclone_bin(), "lsf", "-R", "--files-only", "--fast-list", target()],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if out.returncode in RCLONE_NOT_FOUND:
        return set()
    if out.returncode != 0:
        return None
    return {line for line in out.stdout.splitlines() if line}


def net_moves(queue: list[dict], existing: set[str]) -> list[dict]:
    """
    Replay the queued moves on the list of files that REALLY exist in the cloud
    and return only what's left to do: [{"from": where it is now, "to": final place}].
    - a move whose source isn't there (already done, or never uploaded) disappears,
    - chains collapse (A->B, B->C = A->C), round trips vanish (A->B, B->A = nothing).
    This matters after an interrupted re-organisation: hundreds of queued moves
    may come down to a handful - each rclone call costs seconds on a Raspberry Pi.
    """
    origin_of = {path: path for path in existing}  # current location -> where it is now in the cloud
    for move in queue:
        if move["from"] in origin_of:
            origin_of[move["to"]] = origin_of.pop(move["from"])
    return [{"from": origin, "to": final} for final, origin in origin_of.items() if origin != final]


def _move_one(move: dict) -> bool:
    return rclone("moveto", target(move["from"]), target(move["to"])) == 0


def apply_remote_moves(dry_run: bool) -> int:
    """Files moved locally by re-categorisation -> `rclone moveto` (no re-upload)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    state = state_mod.load()
    queue = state.get("remote_moves", [])
    if not queue:
        return 0

    existing = remote_files()
    if existing is None:
        print(t("storage_list_failed"))
        return 1  # keep the queue, try again next run
    moves = net_moves(queue, existing)
    print(t("storage_moving", n=len(moves), queued=len(queue)))
    if dry_run:
        for move in moves:
            print(f"    {move['from']} -> {move['to']}")
        return 0

    # Google Drive allows several folders with the same name. Three parallel moves into a
    # folder that doesn't exist yet would each create it - three "Language I" folders. So
    # the target folders are created first, one by one, parents before children.
    for folder in sorted({posixpath.dirname(m["to"]) for m in moves if posixpath.dirname(m["to"])},
                         key=lambda d: (d.count("/"), d)):
        rclone("mkdir", target(folder), quiet=True)

    attempts = {m["from"]: m.get("attempts", 0) for m in queue}
    failed, pending, done = 0, list(moves), 0
    # A few moves in parallel: each is a separate rclone process that spends
    # most of its time waiting for Google, not using the CPU.
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_move_one, m): m for m in moves}
        for future in as_completed(futures):
            move = futures[future]
            pending.remove(move)
            if not future.result():
                tries = attempts.get(move["from"], 0) + 1
                if tries >= MAX_MOVE_ATTEMPTS:
                    # Worst case of giving up: the old copy stays next to the new one.
                    print("    " + t("storage_move_gave_up", n=MAX_MOVE_ATTEMPTS, path=move["from"]))
                else:
                    failed += 1
                    pending.append({**move, "attempts": tries})  # e.g. no network - retry next time
            done += 1
            if done % 20 == 0:  # save progress: an interrupted run won't redo finished moves
                state["remote_moves"] = list(pending)
                state_mod.save(state)

    state["remote_moves"] = list(pending)
    state_mod.save(state)
    rclone("rmdirs", target(), "--leave-root")  # empty folders left after moves
    return failed


# --- stale copies (python -m moodle_sync upload --cleanup, bot: /cleanup) -------------------------

def tracked_paths(state: dict) -> set[str]:
    """Where moodle-sync keeps its files now (downloads + subject cards), casefolded."""
    paths = {e["path"] for e in state.get("downloaded", {}).values() if e.get("path")}
    paths |= {e["path"] for e in state.get("syllabi", {}).values() if e.get("path")}
    return {p.casefold() for p in paths}


def stale_copies(listing: list[tuple[str, int]], tracked: set[str]) -> list[str]:
    """
    Files that are an old copy of a tracked file: not at a tracked path, but with
    the same name and size as a tracked file elsewhere (e.g. left behind when a
    move to the new folders failed). Your own files with other names are never
    touched. Pure - see tests.
    """
    signatures = {(Path(p).name.casefold(), size) for p, size in listing if p.casefold() in tracked}
    return sorted(p for p, size in listing
                  if p.casefold() not in tracked and (Path(p).name.casefold(), size) in signatures)


def local_listing() -> list[tuple[str, int]]:
    root = config.download_dir()
    if not root.is_dir():
        return []
    return [(f.relative_to(root).as_posix(), f.stat().st_size) for f in root.rglob("*")
            if f.is_file() and not f.name.endswith((".part", ".relocating"))]


def remote_items() -> list[dict] | None:
    if not status()[0]:
        return None
    out = subprocess.run([config.rclone_bin(), "lsjson", "-R", "--no-mimetype", "--no-modtime", target()],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        return None
    return json.loads(out.stdout or "[]")


def remote_listing(items: list[dict] | None = None) -> list[tuple[str, int]] | None:
    items = remote_items() if items is None else items
    if items is None:
        return None
    return [(item["Path"], item.get("Size", -1)) for item in items if not item.get("IsDir")]


def duplicate_paths(items: list[dict]) -> list[str]:
    """Paths that exist more than once - Google Drive allows two folders (or files) with the same name."""
    counts = Counter((item["Path"], bool(item.get("IsDir"))) for item in items)
    return sorted(path for (path, _), n in counts.items() if n > 1)


def misplaced(listing: list[tuple[str, int]], state: dict, local: set[str]) -> tuple[list[dict], list[str]]:
    """
    Files moodle-sync believes are at path X while the cloud has them elsewhere - left
    behind when a move in the cloud failed after the state had already been updated.
    Returns (moves [{"from": where it really is, "to": X}], paths found nowhere). A file
    is recognised by its name and the folder right above it ("Cwiczenia/list3.pdf"),
    and only when exactly one untracked file fits. Pure - see tests.
    """
    remote = {p.casefold() for p, _ in listing}
    tracked = {e["path"] for e in state.get("downloaded", {}).values() if e.get("path")}
    tracked |= {e["path"] for e in state.get("syllabi", {}).values() if e.get("path")}
    tracked_cf = {p.casefold() for p in tracked}

    def tail(path: str) -> str:
        return "/".join(path.split("/")[-2:]).casefold()

    candidates: dict = {}
    for path, _ in listing:
        if path.casefold() not in tracked_cf:
            candidates.setdefault(tail(path), []).append(path)
    moves, missing = [], []
    for path in sorted(tracked):
        if path.casefold() in remote or path.casefold() in local:
            continue  # in place, or the next upload sends the local copy
        found = candidates.get(tail(path), [])
        if len(found) == 1:
            moves.append({"from": found.pop(), "to": path})
        else:
            missing.append(path)
    return moves, missing


def find_stale() -> dict:
    """
    {"local": [paths], "remote": [paths] or None when there's no cloud, "duplicates": [paths],
    "misplaced": [moves], "missing": [paths]}.
    """
    state = state_mod.load()
    tracked = tracked_paths(state)
    items = remote_items()
    local = local_listing()
    found = {"local": stale_copies(local, tracked),
             "remote": stale_copies(remote_listing(items), tracked) if items is not None else None,
             "duplicates": duplicate_paths(items) if items is not None else [], "misplaced": [], "missing": []}
    if items is not None:
        found["misplaced"], found["missing"] = misplaced(remote_listing(items), state, {p.casefold() for p, _ in local})
    return found


def remove_stale(found: dict) -> int:
    if found.get("duplicates"):
        # merge folders with the same name (their content ends up in one), and of two files
        # with the same name in the same folder keep the newest
        rclone("dedupe", "--dedupe-mode", "newest", target())
    moves = found.get("misplaced") or []
    for folder in sorted({posixpath.dirname(m["to"]) for m in moves if posixpath.dirname(m["to"])},
                         key=lambda d: (d.count("/"), d)):
        rclone("mkdir", target(folder), quiet=True)
    for move in moves:  # one by one: they're few, and parallel moves made duplicate folders before
        _move_one(move)
    if found.get("missing"):
        state = state_mod.load()
        missing = {p.casefold() for p in found["missing"]}
        for entry in state.get("downloaded", {}).values():
            if entry.get("path") and entry["path"].casefold() in missing:
                entry["skipped"], entry["path"] = "redownload", None  # fetched again, quietly, on the next sync
        for entry in state.get("syllabi", {}).values():
            if entry.get("path", "").casefold() in missing:
                entry["checked"], entry["sha"] = 0, ""
        state_mod.save(state)
    root = config.download_dir()
    for path in found["local"]:
        (root / path).unlink(missing_ok=True)
    if found["local"] and root.exists():
        from .files import _remove_empty_dirs
        _remove_empty_dirs(root)
    if found["remote"]:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as fh:
            fh.write("\n".join(found["remote"]) + "\n")
        try:
            rclone("delete", target(), "--files-from-raw", fh.name)
            rclone("rmdirs", target(), "--leave-root")
        finally:
            os.unlink(fh.name)
    return (len(found["local"]) + len(found["remote"] or []) + len(found.get("duplicates", []))
            + len(found.get("misplaced", [])) + len(found.get("missing", [])))


def cleanup(apply: bool = False) -> int:
    found = find_stale()
    for where, label in (("local", t("cleanup_local")), ("remote", t("cleanup_remote"))):
        items = found[where] or []
        print(t("cleanup_found", where=label, n=len(items)))
        for path in items[:30]:
            print(f"    {path}")
    if found["duplicates"]:
        print(t("cleanup_duplicates", n=len(found["duplicates"])))
        for path in found["duplicates"][:30]:
            print(f"    {path}")
    if found["misplaced"] or found["missing"]:
        print(t("cleanup_misplaced", moved=len(found["misplaced"]), missing=len(found["missing"])))
        for move in found["misplaced"][:30]:
            print(f"    {move['from']}\n -> {move['to']}")
    if not apply:
        if found["local"] or found["remote"] or found["duplicates"] or found["misplaced"] or found["missing"]:
            print("\n" + t("cleanup_hint"))
        return 0
    print(t("cleanup_done", n=remove_stale(found)))
    return 0


def backup_state() -> None:
    """Copy state.json (+ courses config) to the cloud - no secrets (.env, tokens)."""
    for name in BACKUP_FILES:
        path = config.DATA_DIR / name
        if path.exists():
            dest = f"{config.rclone_remote()}:{config.state_backup_dest()}/{name}"
            if rclone("copyto", str(path), dest, "-q", quiet=True) != 0:
                print(t("storage_backup_failed", name=name))


def check() -> int:
    ok, reason = status()
    if not ok:
        print(reason)
        return SKIPPED
    return rclone("lsd", f"{config.rclone_remote()}:")


def run(dry_run: bool = False) -> int:
    ok, reason = status()
    if not ok:
        print(reason)
        return SKIPPED

    failed_moves = apply_remote_moves(dry_run)
    local = config.download_dir()
    code = 0
    if local.is_dir():
        verb = "copy" if config.keep_local() else "move"
        extra = ["--dry-run"] if dry_run else []
        if not config.keep_local():
            extra.append("--delete-empty-src-dirs")
        code = rclone(verb, str(local), target(), *RCLONE_FLAGS, "-v", *extra)
    else:
        print(t("storage_nothing", dir=local))
    if not dry_run:
        backup_state()
    return code or (1 if failed_moves else 0)
