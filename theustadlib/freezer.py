"""Protected-input snapshots, tamper checks, and restoration."""

import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Iterable


DEFAULT_PATTERNS = (
    "tests/**",
    "pytest.ini",
    "conftest.py",
    "**/conftest.py",
    "pyproject.toml",
    "setup.cfg",
    "tox.ini",
    "pytest.py",
    "pytest/**",
    "sitecustomize.py",
    "usercustomize.py",
)


@dataclass(frozen=True)
class ManifestEntry:
    path: str
    file_type: str
    sha256: str | None
    mode: int
    snapshot_path: Path | None


@dataclass(frozen=True)
class Manifest:
    repo: Path
    state_dir: Path
    snapshot_dir: Path
    patterns: tuple[str, ...]
    entries: dict[str, ManifestEntry]


@dataclass
class Tampering:
    modified: list[str]
    deleted: list[str]
    added: list[str]

    @property
    def newly_added(self) -> list[str]:
        return self.added

    @property
    def clean(self) -> bool:
        return not (self.modified or self.deleted or self.added)

    def __bool__(self) -> bool:
        return not self.clean


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _normalize_patterns(patterns: Iterable[str]) -> tuple[str, ...]:
    return tuple(pattern.replace("\\", "/").removeprefix("./") for pattern in patterns)


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        if fnmatchcase(path, pattern):
            return True
        if pattern.endswith("/**") and path == pattern[:-3].rstrip("/"):
            return True
    return False


def _iter_entries(repo: Path):
    stack = [repo]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                relative = path.relative_to(repo).as_posix()
                if entry.is_symlink():
                    yield relative, path, "symlink", entry.stat(follow_symlinks=False)
                elif entry.is_dir(follow_symlinks=False):
                    yield relative, path, "directory", entry.stat(follow_symlinks=False)
                    stack.append(path)
                elif entry.is_file(follow_symlinks=False):
                    yield relative, path, "file", entry.stat(follow_symlinks=False)
                else:
                    yield relative, path, "other", entry.stat(follow_symlinks=False)


def _open_regular(path: Path):
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    file_stat = os.fstat(descriptor)
    if not stat.S_ISREG(file_stat.st_mode):
        os.close(descriptor)
        raise ValueError(f"protected path is not a regular file: {path}")
    return os.fdopen(descriptor, "rb"), file_stat


def _snapshot_file(source: Path, destination: Path) -> tuple[str, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    source_file, source_stat = _open_regular(source)
    with source_file, destination.open("xb") as snapshot_file:
        while chunk := source_file.read(1024 * 1024):
            digest.update(chunk)
            snapshot_file.write(chunk)
    mode = stat.S_IMODE(source_stat.st_mode)
    os.chmod(destination, mode)
    return digest.hexdigest(), mode


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    source_file, _ = _open_regular(path)
    with source_file:
        while chunk := source_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _scan(repo: Path, patterns: tuple[str, ...]) -> dict[str, ManifestEntry]:
    entries: dict[str, ManifestEntry] = {}
    for relative, path, file_type, path_stat in _iter_entries(repo):
        if not _matches(relative, patterns):
            continue

        mode = stat.S_IMODE(path_stat.st_mode)
        sha256 = None
        if file_type == "file":
            try:
                sha256 = _hash_file(path)
            except (OSError, ValueError):
                file_type = "unreadable"

        entries[relative] = ManifestEntry(
            path=relative,
            file_type=file_type,
            sha256=sha256,
            mode=mode,
            snapshot_path=None,
        )
    return entries


def _resolve_manifest_repo(
    repo: str | os.PathLike[str], manifest: Manifest
) -> Path:
    repository = Path(repo).resolve(strict=True)
    if repository != manifest.repo:
        raise ValueError("repository does not match manifest")
    return repository


def freeze(
    repo: str | os.PathLike[str],
    patterns: Iterable[str],
    state_dir: str | os.PathLike[str],
) -> Manifest:
    """Snapshot protected repository inputs into external TheUstad-owned state."""
    repository = Path(repo).resolve(strict=True)
    if not repository.is_dir():
        raise ValueError(f"repository is not a directory: {repository}")

    state = Path(state_dir).resolve(strict=False)
    if _is_within(state, repository):
        raise ValueError("state_dir must be outside the repository")
    state.mkdir(parents=True, exist_ok=True)
    state = state.resolve(strict=True)
    if _is_within(state, repository):
        raise ValueError("state_dir must be outside the repository")

    normalized_patterns = _normalize_patterns(patterns)
    snapshot_dir = Path(tempfile.mkdtemp(prefix="snapshot-", dir=state))
    entries: dict[str, ManifestEntry] = {}

    try:
        for relative, path, file_type, path_stat in _iter_entries(repository):
            if not _matches(relative, normalized_patterns):
                continue
            if file_type == "symlink":
                raise ValueError(f"protected path is a symlink: {relative}")
            if file_type == "other":
                raise ValueError(f"unsupported protected path type: {relative}")

            mode = stat.S_IMODE(path_stat.st_mode)
            sha256 = None
            snapshot_path = None
            if file_type == "file":
                snapshot_path = snapshot_dir / "files" / Path(relative)
                sha256, mode = _snapshot_file(path, snapshot_path)

            entries[relative] = ManifestEntry(
                path=relative,
                file_type=file_type,
                sha256=sha256,
                mode=mode,
                snapshot_path=snapshot_path,
            )
    except Exception:
        shutil.rmtree(snapshot_dir, ignore_errors=True)
        raise

    return Manifest(
        repo=repository,
        state_dir=state,
        snapshot_dir=snapshot_dir,
        patterns=normalized_patterns,
        entries=entries,
    )


_GIT_FILE_MODES = {"100644": 0o644, "100755": 0o755}


def git_output(
    repo: str | os.PathLike[str], *args: str, stdin: bytes | None = None
) -> bytes:
    """Run one git command in ``repo`` and return its raw stdout."""
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is not installed or not on PATH")
    result = subprocess.run(
        [git, *args],
        cwd=Path(repo),
        input=stdin,
        capture_output=True,
        shell=False,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {args[0]} failed: {detail or result.returncode}")
    return result.stdout


def _tree_entries(repo: Path, commit: str) -> list[tuple[str, str, str, str]]:
    """Return ``(mode, type, object id, path)`` for every entry a commit records."""
    output = git_output(repo, "ls-tree", "-r", "-z", "--full-tree", commit)
    entries = []
    for record in output.split(b"\0"):
        if not record:
            continue
        header, _, raw_path = record.partition(b"\t")
        mode, object_type, object_id = header.decode("ascii").split(" ")
        entries.append((mode, object_type, object_id, os.fsdecode(raw_path)))
    return entries


def _read_blobs(repo: Path, object_ids: list[str]) -> dict[str, bytes]:
    """Read blobs in one ``git cat-file --batch`` call."""
    if not object_ids:
        return {}
    unique = list(dict.fromkeys(object_ids))
    output = git_output(
        repo, "cat-file", "--batch", stdin="".join(f"{oid}\n" for oid in unique).encode()
    )
    blobs: dict[str, bytes] = {}
    position = 0
    for object_id in unique:
        newline = output.index(b"\n", position)
        header = output[position:newline].decode("ascii").split(" ")
        if len(header) != 3 or header[0] != object_id or header[1] != "blob":
            raise RuntimeError(f"git did not return blob {object_id}: {header}")
        size = int(header[2])
        start = newline + 1
        blobs[object_id] = output[start : start + size]
        position = start + size + 1
    return blobs


def freeze_commit(
    repo: str | os.PathLike[str],
    commit: str,
    patterns: Iterable[str],
    state_dir: str | os.PathLike[str],
) -> Manifest:
    """Snapshot protected inputs as ``commit`` records them, not as the disk holds them.

    The working tree a CI job checks out belongs to the change under review,
    and so do any files its build steps wrote. A baseline read from that disk
    would already contain whatever the change did to its own tests. Git
    objects of the commit the change started from cannot be edited by it.

    The manifest is the same shape :func:`freeze` produces, so :func:`check`
    and :func:`restore` judge and repair the working tree against it unchanged.
    """
    repository = Path(repo).resolve(strict=True)
    state = Path(state_dir).resolve(strict=False)
    if _is_within(state, repository):
        raise ValueError("state_dir must be outside the repository")
    state.mkdir(parents=True, exist_ok=True)
    state = state.resolve(strict=True)
    if _is_within(state, repository):
        raise ValueError("state_dir must be outside the repository")

    normalized_patterns = _normalize_patterns(patterns)
    protected = []
    directories: set[str] = set()
    for mode, object_type, object_id, relative in _tree_entries(repository, commit):
        parts = relative.split("/")
        for depth in range(1, len(parts)):
            parent = "/".join(parts[:depth])
            if _matches(parent, normalized_patterns):
                directories.add(parent)
        if not _matches(relative, normalized_patterns):
            continue
        if mode == "120000":
            raise ValueError(f"protected path is a symlink at {commit}: {relative}")
        if object_type != "blob" or mode not in _GIT_FILE_MODES:
            raise ValueError(
                f"unsupported protected path type at {commit}: {relative} ({mode})"
            )
        protected.append((relative, object_id, _GIT_FILE_MODES[mode]))

    blobs = _read_blobs(repository, [object_id for _, object_id, _ in protected])
    snapshot_dir = Path(tempfile.mkdtemp(prefix="snapshot-", dir=state))
    entries: dict[str, ManifestEntry] = {}
    try:
        for relative in sorted(directories):
            entries[relative] = ManifestEntry(
                path=relative,
                file_type="directory",
                sha256=None,
                mode=0o755,
                snapshot_path=None,
            )
        for relative, object_id, mode in protected:
            content = blobs[object_id]
            snapshot_path = snapshot_dir / "files" / Path(relative)
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            with snapshot_path.open("xb") as snapshot_file:
                snapshot_file.write(content)
            os.chmod(snapshot_path, mode)
            entries[relative] = ManifestEntry(
                path=relative,
                file_type="file",
                sha256=hashlib.sha256(content).hexdigest(),
                mode=mode,
                snapshot_path=snapshot_path,
            )
    except Exception:
        shutil.rmtree(snapshot_dir, ignore_errors=True)
        raise

    return Manifest(
        repo=repository,
        state_dir=state,
        snapshot_dir=snapshot_dir,
        patterns=normalized_patterns,
        entries=entries,
    )


def check(repo: str | os.PathLike[str], manifest: Manifest) -> Tampering:
    """Compare current protected paths with a frozen manifest."""
    repository = _resolve_manifest_repo(repo, manifest)
    current = _scan(repository, manifest.patterns)
    baseline_paths = set(manifest.entries)
    current_paths = set(current)

    deleted = sorted(baseline_paths - current_paths)
    added = sorted(current_paths - baseline_paths)
    modified: list[str] = []

    for relative in sorted(baseline_paths & current_paths):
        expected = manifest.entries[relative]
        observed = current[relative]
        if expected.file_type != observed.file_type:
            modified.append(relative)
        elif expected.file_type == "file" and expected.sha256 != observed.sha256:
            modified.append(relative)

    return Tampering(modified=modified, deleted=deleted, added=added)


def _remove_existing(path: Path) -> None:
    try:
        path_stat = path.lstat()
    except FileNotFoundError:
        return

    if stat.S_ISDIR(path_stat.st_mode) and not stat.S_ISLNK(path_stat.st_mode):
        shutil.rmtree(path)
    else:
        path.unlink()


def _ensure_parent_directories(repo: Path, parent: Path) -> None:
    current = repo
    for part in parent.relative_to(repo).parts:
        current /= part
        try:
            current_stat = current.lstat()
        except FileNotFoundError:
            current.mkdir()
            continue
        if stat.S_ISLNK(current_stat.st_mode):
            raise RuntimeError(f"refusing to restore through symlink: {current}")
        if not stat.S_ISDIR(current_stat.st_mode):
            raise RuntimeError(f"restore parent is not a directory: {current}")


def _restore_file(snapshot: Path, destination: Path, mode: int) -> None:
    source_file, _ = _open_regular(snapshot)
    with source_file, destination.open("xb") as destination_file:
        shutil.copyfileobj(source_file, destination_file, length=1024 * 1024)
    os.chmod(destination, mode)


def restore(repo: str | os.PathLike[str], manifest: Manifest) -> None:
    """Restore the protected baseline and remove newly protected paths."""
    repository = _resolve_manifest_repo(repo, manifest)

    for entry in manifest.entries.values():
        if entry.file_type != "file":
            continue
        if entry.snapshot_path is None or entry.sha256 is None:
            raise RuntimeError(f"missing snapshot metadata: {entry.path}")
        try:
            snapshot_hash = _hash_file(entry.snapshot_path)
        except (OSError, ValueError) as error:
            raise RuntimeError(f"unreadable snapshot: {entry.path}") from error
        if snapshot_hash != entry.sha256:
            raise RuntimeError(f"snapshot hash mismatch: {entry.path}")

    tampering = check(repository, manifest)
    for relative in sorted(
        tampering.added, key=lambda path: (path.count("/"), path), reverse=True
    ):
        _remove_existing(repository / Path(relative))

    directories = sorted(
        (entry for entry in manifest.entries.values() if entry.file_type == "directory"),
        key=lambda entry: (entry.path.count("/"), entry.path),
    )
    for entry in directories:
        destination = repository / Path(entry.path)
        _ensure_parent_directories(repository, destination.parent)
        try:
            destination_stat = destination.lstat()
        except FileNotFoundError:
            destination.mkdir()
        else:
            if stat.S_ISLNK(destination_stat.st_mode) or not stat.S_ISDIR(
                destination_stat.st_mode
            ):
                _remove_existing(destination)
                destination.mkdir()
        os.chmod(destination, entry.mode)

    files = sorted(
        (entry for entry in manifest.entries.values() if entry.file_type == "file"),
        key=lambda entry: entry.path,
    )
    for entry in files:
        destination = repository / Path(entry.path)
        _ensure_parent_directories(repository, destination.parent)
        _remove_existing(destination)
        snapshot_path = entry.snapshot_path
        if snapshot_path is None:
            raise RuntimeError(f"missing snapshot path: {entry.path}")
        _restore_file(snapshot_path, destination, entry.mode)

    remaining = check(repository, manifest)
    if remaining:
        raise RuntimeError(
            "protected inputs remain tampered after restore: "
            f"modified={remaining.modified}, deleted={remaining.deleted}, "
            f"added={remaining.added}"
        )
