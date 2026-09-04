import mimetypes
import os
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError

TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".html", ".htm", ".css", ".js", ".mjs", ".cjs", ".json", ".py",
    ".toml", ".yaml", ".yml", ".xml", ".csv", ".ini", ".cfg", ".tsx", ".ts",
    ".jsx", ".vue", ".svelte", ".java", ".go", ".rs", ".php", ".rb", ".sh", ".sql",
}

SENSITIVE_FILENAMES = {
    "credentials.json", "secrets.json", "service-account.json", "id_rsa", "id_dsa", "id_ed25519",
}
SENSITIVE_SUFFIXES = {".db", ".key", ".p12", ".pfx", ".pem", ".sqlite", ".sqlite3"}


def _is_within(path: Path, root: Path) -> bool:
    try:
        normalized_path = os.path.normcase(os.path.realpath(os.fspath(path)))
        normalized_root = os.path.normcase(os.path.realpath(os.fspath(root)))
        return os.path.commonpath([normalized_path, normalized_root]) == normalized_root
    except (ValueError, OSError):
        return False


def _is_protected_relative(relative: Path) -> bool:
    parts = relative.parts
    if any(part.startswith(".") for part in parts):
        return True
    name = relative.name.lower()
    return name in SENSITIVE_FILENAMES or relative.suffix.lower() in SENSITIVE_SUFFIXES


def project_root(project, settings_obj):
    if not project.local_path:
        raise ValidationError("This project has no local folder path yet.")
    root = Path(project.local_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValidationError("The configured project folder does not exist on the Django server computer.")
    boundary = settings_obj.normalized_workspace_root()
    if boundary and not _is_within(root, boundary):
        raise PermissionDenied("This project folder is outside your configured workspace root.")
    return root


def resolve_project_path(project, settings_obj, relative=""):
    root = project_root(project, settings_obj)
    rel = str(relative or "").replace("\\", "/").lstrip("/")
    relative_path = Path(rel)
    if rel and _is_protected_relative(relative_path):
        raise PermissionDenied("Hidden, credential, key, and database files are not available in project preview.")
    target = (root / rel).resolve()
    if not _is_within(target, root):
        raise PermissionDenied("Path traversal outside the project folder is not allowed.")
    return root, target


def list_directory(project, settings_obj, relative="", limit=500):
    root, target = resolve_project_path(project, settings_obj, relative)
    if not target.exists() or not target.is_dir():
        raise ValidationError("Requested path is not a directory.")
    entries = []
    try:
        children = list(target.iterdir())
    except OSError as exc:
        raise ValidationError(f"Could not read directory: {exc}") from exc
    children.sort(key=lambda p: (not p.is_dir(), p.name.lower()))
    visible_children = []
    for p in children:
        try:
            relative_path = p.relative_to(root)
            if _is_protected_relative(relative_path) or not _is_within(p.resolve(), root):
                continue
            visible_children.append(p)
        except (OSError, ValueError):
            continue
    truncated = len(visible_children) > limit
    for p in visible_children[:limit]:
        try:
            stat = p.stat()
            is_dir = p.is_dir()
            rel = p.relative_to(root).as_posix()
            entries.append({
                "name": p.name,
                "kind": "directory" if is_dir else "file",
                "path": rel,
                "size": None if is_dir else stat.st_size,
                "modified": int(stat.st_mtime),
                "extension": "" if is_dir else p.suffix.lower(),
            })
        except OSError:
            continue
    return {
        "rootName": root.name,
        "path": "" if target == root else target.relative_to(root).as_posix(),
        "entries": entries,
        "truncated": truncated,
    }


def read_text_file(project, settings_obj, relative, max_bytes=2_000_000):
    root, target = resolve_project_path(project, settings_obj, relative)
    if not target.exists() or not target.is_file():
        raise ValidationError("Requested path is not a file.")
    if target.stat().st_size > max_bytes:
        raise ValidationError("This file is too large for the built-in preview.")
    suffix = target.suffix.lower()
    if suffix not in TEXT_SUFFIXES and target.name not in {"Dockerfile", "Makefile", "LICENSE", "README"}:
        raise ValidationError("This file type is not supported by the text preview.")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ValidationError("This file could not be read by the Django server.") from exc
    return {
        "name": target.name,
        "path": target.relative_to(root).as_posix(),
        "content": content,
        "mime": mimetypes.guess_type(target.name)[0] or "text/plain",
    }
