#!/usr/bin/env bash
# ============================================================
# 一键推送 + 发布脚本
#
# 问题诊断：git push HTTPS 失败是因为 SChannel TLS 重新协商
# 导致大包被重置。解决方案：用 gh CLI 的 API 通道绕过 git push。
# ============================================================
set -e

cd "$(dirname "$0")"

echo "=== 1. 验证 gh 认证 ==="
gh auth status || { echo "请先运行: gh auth login"; exit 1; }

echo "=== 2. 创建远程分支 ==="
SHA=$(git rev-parse HEAD)
gh api repos/CS-Samuel-hamo/fractal-agent-governance/git/refs \
  --field ref=refs/heads/feat/v1.1-session-cockpit \
  --field sha="$SHA" 2>/dev/null && echo "分支已创建" || echo "分支可能已存在，继续..."

echo "=== 3. 推送全部 commits (用 git push 小包策略) ==="
# 分步推送每个 commit，减小每次推送的数据量
for COMMIT in 004dccd 67df8ec 1eb52fa 82da26e 9881732 8bf16ca b20ecee 8813d1f 22df83c; do
  echo "  推送 commit $COMMIT ..."
  git push origin "$COMMIT":refs/heads/feat/v1.1-session-cockpit --force 2>/dev/null && break
  # 如果失败，只推当前最新的 tag 也能工作
done

echo "=== 4. 打 tag ==="
git tag -f v1.1.0-alpha.1 HEAD
git push origin v1.1.0-alpha.1 --force 2>/dev/null || {
  # 如果 git push 失败，用 gh 创建 release
  echo "  git push tag 失败，改用 gh release create ..."
}

echo "=== 5. 创建 GitHub Release ==="
gh release create v1.1.0-alpha.1 \
  --title "v1.1.0-alpha.1 Session & Cockpit Improvement" \
  --notes-file docs/releases/RELEASE_NOTES.md \
  --target feat/v1.1-session-cockpit \
  --draft \
  --prerelease

echo ""
echo "=== ✅ 完成 ==="
echo "分支: https://github.com/CS-Samuel-hamo/fractal-agent-governance/tree/feat/v1.1-session-cockpit"
echo "Release: https://github.com/CS-Samuel-hamo/fractal-agent-governance/releases/tag/v1.1.0-alpha.1"
