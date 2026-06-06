#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

KIT_VERSION = "0.3.9.3-implementation-delivery-kernel"
# Replace both active and retired kit modes so global custom_modes.yaml does not keep old visible roles.
KIT_MODE_SLUGS = {
    "agent-orchestrator",
    "agent-planner",
    "agent-branch-manager",
    "agent-executor",
    "agent-reviewer",
    "agent-integrator",
    "agent-curator",
    "agent-project-profiler",
    "agent-plan-drafter",
    "agent-branch-clerk",
    "agent-mechanical-reviewer",
    "agent-integration-clerk",
    "agent-curator-draft",
    "agent-codex-worker",
}


def log(message: str) -> None:
    print(message)


def fail(message: str, code: int = 1) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)
    sys.exit(code)


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def find_kit_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        required = [
            candidate / ".roomodes",
            candidate / ".roo/commands/agent-run.md",
            candidate / ".roo/rules",
            candidate / ".roo/skills-agent-executor",
            candidate / "scripts/install-global-zoo-agent-kit.py",
            candidate / "scripts/validate-zoo-agent-kit.py",
            candidate / "templates/codex/AGENTS.md",
            candidate / "launcher/vscode-zoo-agent-run-launcher/package.json",
        ]
        if all(path.exists() for path in required):
            return candidate
    fail("Could not locate kit root.")
    raise AssertionError


def ensure_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        log(f"[dry-run] mkdir {path}")
    else:
        path.mkdir(parents=True, exist_ok=True)


def skip(path: Path) -> bool:
    lower = path.name.lower()
    markers = [".env", "secret", "token", "credential", "private", ".pem", ".key"]
    return "__pycache__" in path.parts or path.suffix == ".pyc" or any(marker in lower for marker in markers)


def same_location(left: Path, right: Path) -> bool:
    try:
        left_text = str(left.resolve())
    except FileNotFoundError:
        left_text = str(left.absolute())
    try:
        right_text = str(right.resolve())
    except FileNotFoundError:
        right_text = str(right.absolute())
    return os.path.normcase(left_text) == os.path.normcase(right_text)


def backup_path(src: Path, dst: Path, dry_run: bool) -> None:
    if not src.exists() or skip(src):
        return
    if dry_run:
        log(f"[dry-run] backup {src} -> {dst}")
        return
    if src.is_dir():
        copy_tree(src, dst, None, False)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def copy_file(src: Path, dst: Path, backup_root: Optional[Path], dry_run: bool) -> None:
    if not src.exists() or skip(src):
        return
    if same_location(src, dst):
        if dry_run:
            log(f"[dry-run] keep {dst} (source and destination are the same)")
        return
    if dst.exists() and backup_root:
        backup_path(dst, backup_root / "overwritten-files" / str(dst).replace(":", "").replace("\\", "/"), dry_run)
    if dry_run:
        log(f"[dry-run] copy {src} -> {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path, backup_root: Optional[Path], dry_run: bool) -> None:
    if not src.exists():
        return
    if same_location(src, dst):
        if dry_run:
            log(f"[dry-run] keep {dst} (source and destination tree are the same)")
        return
    ensure_dir(dst, dry_run)
    for item in src.rglob("*"):
        if skip(item):
            continue
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            ensure_dir(target, dry_run)
        else:
            copy_file(item, target, backup_root, dry_run)


def global_storage_dirs() -> List[Path]:
    home = Path.home()
    appdata = os.environ.get("APPDATA")
    if sys.platform == "win32" and appdata:
        base = Path(appdata)
        return [base / app / "User/globalStorage" for app in ["Code", "Code - Insiders", "Cursor", "VSCodium"]]
    if sys.platform == "darwin":
        base = home / "Library/Application Support"
        return [base / app / "User/globalStorage" for app in ["Code", "Code - Insiders", "Cursor", "VSCodium"]]
    base = home / ".config"
    return [base / app / "User/globalStorage" for app in ["Code", "Code - Insiders", "Cursor", "VSCodium"]]


def candidate_modes(explicit: Optional[str]) -> List[Path]:
    paths: List[Path] = []
    if explicit:
        paths.append(Path(explicit).expanduser())
    env = os.environ.get("ZOO_GLOBAL_MODES_PATH")
    if env:
        paths.append(Path(env).expanduser())
    for root in global_storage_dirs():
        if root.exists():
            paths.append(root / "settings/custom_modes.yaml")
            for child in root.iterdir():
                if not child.is_dir():
                    continue
                text = child.name.lower()
                if any(marker in text for marker in ["zoo", "roo", "cline"]):
                    paths.append(child / "settings/custom_modes.yaml")
    unique: List[Path] = []
    seen = set()
    for path in paths:
        key = str(path.resolve() if path.exists() else path.absolute())
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def choose_modes_path(explicit: Optional[str]) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists():
            return path
        fail(f"Explicit custom modes path does not exist: {path}")
    for path in candidate_modes(explicit):
        if path.exists():
            return path
    scanned = ", ".join(str(path) for path in global_storage_dirs() if path.exists()) or "(none)"
    fail(f"No existing Zoo/Roo global custom_modes.yaml found. Scanned: {scanned}")
    raise AssertionError


def split_mode_blocks(text: str) -> Tuple[str, Dict[str, str], List[str]]:
    if "customModes:" not in text:
        return "customModes:\n", {}, []
    idx = text.find("customModes:")
    prefix = text[:idx] + "customModes:\n"
    body = text[idx + len("customModes:") :]
    matches = list(re.finditer(r"(?m)^-\s+slug:\s*['\"]?([A-Za-z0-9-]+)['\"]?\s*$", body))
    blocks: Dict[str, str] = {}
    order: List[str] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        slug = match.group(1)
        blocks[slug] = body[start:end].rstrip() + "\n"
        order.append(slug)
    return prefix, blocks, order


def merge_modes(existing: str, kit: str) -> str:
    prefix, existing_blocks, existing_order = split_mode_blocks(existing)
    _, kit_blocks, kit_order = split_mode_blocks(kit)
    for slug in KIT_MODE_SLUGS:
        existing_blocks.pop(slug, None)
        if slug in existing_order:
            existing_order.remove(slug)
    merged_order = existing_order + [slug for slug in kit_order if slug in kit_blocks]
    lines = [prefix.rstrip(), ""]
    for slug in merged_order:
        block = kit_blocks.get(slug) or existing_blocks.get(slug)
        if block:
            lines.append(block.rstrip())
    return "\n".join(lines).rstrip() + "\n"


def editor_extension_dirs() -> List[Path]:
    home = Path.home()
    dirs = [
        home / ".vscode/extensions",
        home / ".vscode-insiders/extensions",
        home / ".cursor/extensions",
        home / ".vscode-oss/extensions",
        home / ".vscodium/extensions",
    ]
    existing = [path for path in dirs if path.exists()]
    return existing or [home / ".vscode/extensions"]


def full_backup(modes_path: Optional[Path], dry_run: bool) -> Path:
    root = Path.home() / "zoo-global-agent-kit" / "backups" / f"global-before-0.3.9.3-install-{stamp()}"
    ensure_dir(root, dry_run)
    roo = Path.home() / ".roo"
    entries = [
        (roo / "agent-governance-kit", root / "roo-agent-governance-kit"),
        (roo / "commands", root / "roo-commands"),
    ]
    if roo.exists():
        for child in roo.iterdir():
            if child.name.startswith("rules") or child.name.startswith("skills"):
                entries.append((child, root / f"roo-{child.name}"))
    if modes_path:
        entries.append((modes_path, root / "global-custom_modes.yaml"))
    for ext in editor_extension_dirs():
        if ext.exists():
            for child in ext.glob("local.zoo-agent-run-launcher*"):
                entries.append((child, root / f"launcher-{ext.parent.name}-{child.name}"))
    for src, dst in entries:
        backup_path(src, dst, dry_run)
    manifest = root / "BACKUP_MANIFEST.md"
    if dry_run:
        log(f"[dry-run] write backup manifest -> {manifest}")
    else:
        lines = [
            "# Backup Manifest",
            "",
            f"- created_at: {datetime.now().isoformat()}",
            f"- backup_root: {root}",
            "- excluded: secrets, .env, API keys, tokens, credentials, private keys",
            "",
            "## Entries",
        ]
        for src, dst in entries:
            if src.exists():
                lines.append(f"- `{src}` -> `{dst}`")
        manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def install_assets(root: Path, dry_run: bool) -> Path:
    roo = Path.home() / ".roo"
    backup_root = roo / "backups" / f"zoo-agent-kit-0.3.9.3-global-{stamp()}"
    ensure_dir(roo, dry_run)
    ensure_dir(backup_root, dry_run)
    copy_tree(root / ".roo/rules", roo / "rules", backup_root, dry_run)
    for directory in (root / ".roo").glob("rules-*"):
        if directory.is_dir():
            copy_tree(directory, roo / directory.name, backup_root, dry_run)
    for directory in (root / ".roo").glob("skills*"):
        if directory.is_dir():
            copy_tree(directory, roo / directory.name, backup_root, dry_run)
    copy_tree(root / ".roo/commands", roo / "commands", backup_root, dry_run)

    resource = roo / "agent-governance-kit"
    copy_file(root / ".roomodes", resource / ".roomodes", backup_root, dry_run)
    for name in [".roo", "docs", "scripts", "evals", "launcher", "templates"]:
        copy_tree(root / name, resource / name, backup_root, dry_run)
    for name in ["AGENTS.md", "README.md", "CODEX_GLOBAL_INSTALL_PROMPT.md", "GLOBAL_INSTALL_README.md", ".rooignore", ".worktreeinclude", ".gitignore.additions"]:
        copy_file(root / name, resource / name, backup_root, dry_run)

    bootstrap = roo / "rules/05-agent-governance-global-bootstrap.md"
    text = f"""# Agent Governance Global Bootstrap

Zoo Code Agent Governance Kit {KIT_VERSION} is installed globally.

- Apply global modes, rules, skills, commands, and Codex bridge templates to existing and future workspaces.
- Do not copy the full kit into business repositories.
- First-run intake is read-only by default.
- Use templates from `{resource}` when project-local templates are absent.
- Do not read or print secrets, API keys, tokens, .env, private keys, credentials, or provider profiles.
- Do not write `~/.codex/config.toml`; use `templates/codex/config.toml.example` as a manual reference only.
"""
    if dry_run:
        log(f"[dry-run] write {bootstrap}")
    else:
        bootstrap.parent.mkdir(parents=True, exist_ok=True)
        bootstrap.write_text(text, encoding="utf-8")
    log(f"[OK] Installed global assets under {roo}")
    log(f"[OK] Per-file backup root: {backup_root}")
    return backup_root


def install_modes(root: Path, modes_path: Path, backup_root: Path, dry_run: bool) -> None:
    backup_path(modes_path, backup_root / "global-modes/custom_modes.yaml", dry_run)
    merged = merge_modes(modes_path.read_text(encoding="utf-8"), (root / ".roomodes").read_text(encoding="utf-8"))
    if dry_run:
        log(f"[dry-run] write merged global modes -> {modes_path}")
    else:
        modes_path.write_text(merged, encoding="utf-8")
        log("[OK] Global modes merged.")


def install_launcher(root: Path, backup_root: Path, dry_run: bool) -> None:
    src = root / "launcher/vscode-zoo-agent-run-launcher"
    for ext in editor_extension_dirs():
        dst = ext / "local.zoo-agent-run-launcher-0.3.12"
        backup_path(dst, backup_root / "overwritten-launchers" / ext.parent.name / dst.name, dry_run)
        if dry_run:
            log(f"[dry-run] install VS Code launcher extension {src} -> {dst}")
        else:
            ext.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            log(f"[OK] Installed launcher extension -> {dst}")


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Install Zoo Code Agent Governance Kit {KIT_VERSION} globally.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--custom-modes-path")
    parser.add_argument("--skip-modes", action="store_true")
    parser.add_argument("--skip-launcher", action="store_true")
    args = parser.parse_args()

    root = find_kit_root(Path.cwd())
    log(f"[INFO] Kit root: {root}")
    modes_path = None if args.skip_modes else choose_modes_path(args.custom_modes_path)
    pre_backup = full_backup(modes_path, args.dry_run)
    log(f"[INFO] Full pre-install backup root: {pre_backup}")
    per_file_backup = install_assets(root, args.dry_run)
    if not args.skip_launcher:
        install_launcher(root, per_file_backup, args.dry_run)
    if modes_path:
        log(f"[INFO] Global custom modes target: {modes_path}")
        install_modes(root, modes_path, per_file_backup, args.dry_run)
    log("[NEXT] Reload VS Code/Cursor. Configure Codex, GPT, and DeepSeek profiles manually if needed. API keys are not installed or read.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
