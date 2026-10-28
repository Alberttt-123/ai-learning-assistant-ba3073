"""Build a source-only archive, excluding assignment-prohibited runtime files.

Run: python scripts/package-source.py
Reports and runtime evidence are submitted separately, not inside this archive.
"""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "submission" / "source-code.zip"
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "data", "workspace",
    "submission", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".vite",
    "htmlcov", "dist", "build", ".idea", ".vscode", ".aws", ".codex", ".agents",
}
EXCLUDED_NAMES = {
    "Qwen_API", "local-ui-check.txt", "ecs-docker-check.txt",
    "ecs-web-service-test.txt", "https-access-check.txt", ".coverage",
    ".DS_Store", "Thumbs.db",
}
PRIVATE_SUFFIXES = {".pyc", ".pyo", ".pem", ".key", ".p12", ".pfx", ".netrc"}


def source_files():
    # Prune traversal before entering large runtime dependency directories.
    import os

    for current, dirs, files in os.walk(ROOT, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS
                         and not (Path(current) / d).is_symlink())
        for name in sorted(files):
            path = Path(current) / name
            if path.is_symlink() or name.startswith(".env"):
                continue
            if name in EXCLUDED_NAMES or path.suffix.lower() in PRIVATE_SUFFIXES:
                continue
            if name in {"model-secrets.env", "model-key-encryption.key"}:
                continue
            yield path


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    paths = list(source_files())
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(ROOT).as_posix())
    with ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None
    print(f"Source archive: {OUTPUT}")
    print(f"Files: {len(paths)}; bytes: {OUTPUT.stat().st_size}")
