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

KIT_VERSION = "0.3.7"
KIT_MODE_SLUGS = {
    "agent-orchestrator", "agent-planner", "agent-branch-manager", "agent-executor",
    "agent-reviewer", "agent-integrator", "agent-curator", "agent-project-profiler",
    "agent-plan-drafter", "agent-branch-clerk", "agent-mechanical-reviewer",
    "agent-integration-clerk", "agent-curator-draft",
}


def log(msg: str) -> None:
    print(msg)


def fail(msg: str, code: int = 1) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def find_kit_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        required = [
            p / ".roomodes",
            p / ".roo/commands/agent-run.md",
            p / ".roo/rules-agent-executor",
            p / ".roo/skills-agent-executor/impact-analysis/SKILL.md",
            p / "launcher/vscode-zoo-agent-run-launcher",
            p / "scripts/install-global-zoo-agent-kit.py",
            p / "scripts/validate-zoo-agent-kit.py",
        ]
        if all(x.exists() for x in required):
            return p
    fail("Could not locate kit root.")
    raise AssertionError


def ensure_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        log(f"[dry-run] mkdir -p {path}")
    else:
        path.mkdir(parents=True, exist_ok=True)


def skip(path: Path) -> bool:
    name = path.name.lower()
    markers = [".env", "secret", "token", "credential", "private", ".pem", ".key"]
    return "__pycache__" in path.parts or path.suffix == ".pyc" or any(m in name for m in markers)


def backup(src: Path, dst: Path, dry_run: bool) -> None:
    if not src.exists():
        return
    if dry_run:
        log(f"[dry-run] backup {src} -> {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env*", "*secret*", "*token*", "*.pem", "*.key"))
    else:
        shutil.copy2(src, dst)


def copy_file(src: Path, dst: Path, backup_root: Path, dry_run: bool) -> None:
    if not src.exists() or skip(src):
        return
    if dst.exists():
        backup(dst, backup_root / "overwritten-files" / dst.name, dry_run)
    if dry_run:
        log(f"[dry-run] copy {src} -> {dst}")
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path, backup_root: Path, dry_run: bool) -> None:
    if not src.exists():
        return
    ensure_dir(dst, dry_run)
    for item in src.rglob("*"):
        if skip(item):
            continue
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            ensure_dir(target, dry_run)
            continue
        if target.exists():
            backup(target, backup_root / "overwritten-files" / dst.name / rel, dry_run)
        if dry_run:
            log(f"[dry-run] copy {item} -> {target}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


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
            for p in root.glob("**/settings/custom_modes.yaml"):
                s = str(p).lower()
                if "zoo" in s or "roo" in s:
                    paths.append(p)
    out: List[Path] = []
    seen = set()
    for p in paths:
        key = str(p.resolve() if p.exists() else p.absolute())
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def choose_modes_path(explicit: Optional[str]) -> Path:
    if explicit:
        p = Path(explicit).expanduser()
        if p.exists():
            return p
        fail(f"Explicit custom modes path does not exist: {p}")
    for p in candidate_modes(explicit):
        if p.exists():
            return p
    scanned = ", ".join(str(p) for p in global_storage_dirs() if p.exists()) or "(none)"
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
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        slug = m.group(1)
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
    merged_order = existing_order + [s for s in kit_order if s in kit_blocks]
    lines = [prefix.rstrip(), ""]
    for slug in merged_order:
        block = kit_blocks.get(slug) or existing_blocks.get(slug)
        if block:
            lines.append(block.rstrip())
    return "\n".join(lines).rstrip() + "\n"


def editor_extension_dirs() -> List[Path]:
    home = Path.home()
    dirs = [home / ".vscode/extensions", home / ".vscode-insiders/extensions", home / ".cursor/extensions", home / ".vscode-oss/extensions", home / ".vscodium/extensions"]
    existing = [d for d in dirs if d.exists()]
    return existing or [home / ".vscode/extensions"]


def full_backup(modes_path: Optional[Path], dry_run: bool) -> Path:
    root = Path.home() / "zoo-global-agent-kit/backups" / f"global-before-v3.7-install-{stamp()}"
    ensure_dir(root, dry_run)
    roo = Path.home() / ".roo"
    entries = [(roo / "commands", root / "roo-commands"), (roo / "rules", root / "roo-rules"), (roo / "skills", root / "roo-skills"), (roo / "agent-governance-kit", root / "roo-agent-governance-kit")]
    if roo.exists():
        for child in roo.iterdir():
            if child.is_dir() and (child.name.startswith("rules-agent-") or child.name.startswith("skills-agent-")):
                entries.append((child, root / f"roo-{child.name}"))
    if modes_path:
        entries.append((modes_path, root / "global-custom_modes.yaml"))
    for ext in editor_extension_dirs():
        if ext.exists():
            for child in ext.glob("local.zoo-agent-run-launcher-*"):
                if child.is_dir():
                    entries.append((child, root / f"launcher-{ext.parent.name}-{child.name}"))
    for src, dst in entries:
        backup(src, dst, dry_run)
    manifest = root / "BACKUP_MANIFEST.md"
    if dry_run:
        log(f"[dry-run] write backup manifest -> {manifest}")
    else:
        lines = ["# Backup Manifest", "", f"- created_at: {datetime.now().isoformat()}", f"- backup_root: {root}", "- excluded: secrets, .env, API keys, tokens, credentials, private keys", "", "## Entries"]
        for src, dst in entries:
            if src.exists():
                lines.append(f"- `{src}` -> `{dst}`")
        manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def install_assets(root: Path, dry_run: bool) -> Path:
    roo = Path.home() / ".roo"
    backup_root = roo / "backups" / f"zoo-agent-kit-v3.7-global-{stamp()}"
    ensure_dir(roo, dry_run)
    ensure_dir(backup_root, dry_run)
    copy_tree(root / ".roo/rules", roo / "rules", backup_root, dry_run)
    for d in (root / ".roo").glob("rules-*"):
        if d.is_dir():
            copy_tree(d, roo / d.name, backup_root, dry_run)
    for d in (root / ".roo").glob("skills*"):
        if d.is_dir():
            copy_tree(d, roo / d.name, backup_root, dry_run)
    copy_tree(root / ".roo/commands", roo / "commands", backup_root, dry_run)
    resource = roo / "agent-governance-kit"
    copy_file(root / ".roomodes", resource / ".roomodes", backup_root, dry_run)
    copy_tree(root / ".roo", resource / ".roo", backup_root, dry_run)
    copy_tree(root / "docs", resource / "docs", backup_root, dry_run)
    copy_tree(root / "scripts", resource / "scripts", backup_root, dry_run)
    copy_tree(root / "evals", resource / "evals", backup_root, dry_run)
    copy_tree(root / "launcher", resource / "launcher", backup_root, dry_run)
    for name in ["AGENTS.md", "README.md", "CODEX_GLOBAL_INSTALL_PROMPT.md", "GLOBAL_INSTALL_README.md", ".rooignore", ".worktreeinclude", ".gitignore.additions"]:
        copy_file(root / name, resource / name, backup_root, dry_run)
    bootstrap = roo / "rules/05-agent-governance-global-bootstrap.md"
    text = f"""# Agent Governance Global Bootstrap

Zoo Code Agent Governance Kit v3.7 Fractal + Zoo Native Runtime is installed globally.

- Apply global modes/rules/skills/commands to existing and future workspaces.
- Do not copy the full kit into business repositories.
- First-run intake is read-only by default.
- Use templates from `{resource}` when project-local templates are absent.
- Do not read or print secrets, API keys, tokens, .env, private keys, credentials, or provider profiles.
"""
    if dry_run:
        log(f"[dry-run] write {bootstrap}")
    else:
        bootstrap.parent.mkdir(parents=True, exist_ok=True)
        bootstrap.write_text(text, encoding="utf-8")
    log(f"[OK] Installed global rules/skills/commands/resources under {roo}")
    log(f"[OK] Per-file backup root: {backup_root}")
    return backup_root


def install_modes(root: Path, modes_path: Path, backup_root: Path, dry_run: bool) -> None:
    backup(modes_path, backup_root / "global-modes/custom_modes.yaml", dry_run)
    merged = merge_modes(modes_path.read_text(encoding="utf-8"), (root / ".roomodes").read_text(encoding="utf-8"))
    if dry_run:
        log(f"[dry-run] write merged global modes -> {modes_path}")
    else:
        modes_path.write_text(merged, encoding="utf-8")


def install_launcher(root: Path, backup_root: Path, dry_run: bool) -> None:
    src = root / "launcher/vscode-zoo-agent-run-launcher"
    for ext in editor_extension_dirs():
        dst = ext / f"local.zoo-agent-run-launcher-{KIT_VERSION}"
        if ext.exists():
            for old in ext.glob("local.zoo-agent-run-launcher-*"):
                if old.is_dir() and old.name != dst.name:
                    backup(old, backup_root / "old-launchers" / ext.parent.name / old.name, dry_run)
                    log(f"[INFO] Preserved old launcher after backup: {old}")
        backup(dst, backup_root / "overwritten-launchers" / ext.parent.name / dst.name, dry_run)
        if dry_run:
            log(f"[dry-run] install VS Code launcher extension {src} -> {dst}")
        else:
            ext.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            log(f"[OK] Installed launcher extension -> {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install Zoo Code Agent Governance Kit v3.7 globally.")
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
        log("[OK] Global modes merged.")
    log("[NEXT] Reload VS Code/Cursor. Configure GPT/DeepSeek provider profiles in Zoo Code UI if needed. API keys are not installed or read.")


if __name__ == "__main__":
    main()
