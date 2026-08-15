#!/usr/bin/env bash
#
# skills-router 安装脚本（Linux / macOS / WSL）
#
# 从 GitHub Releases 下载 skills-router 发布包，安装到执行指令的目录（默认当前目录）。
#
# 用法:
#   ./install.sh                          # 安装最新版到当前目录
#   VERSION=v1.2.3 ./install.sh           # 安装指定版本
#   DEST=/path/to/project ./install.sh    # 安装到指定目录（需已存在）
#   SKILLS_ROUTER_REPO=owner/repo ./install.sh   # 指定 GitHub 仓库（默认 eavelabs-community/skills-router）
#
# 首次使用请将仓库地址写入脚本（见下方 REPO）或通过 SKILLS_ROUTER_REPO 环境变量传入。

set -euo pipefail

# 仓库地址：默认 eavelabs-community/skills-router，可通过 SKILLS_ROUTER_REPO 环境变量覆盖
REPO="${SKILLS_ROUTER_REPO:-eavelabs-community/skills-router}"
# 版本：latest（默认）或 v1.2.3 等具体 tag
VERSION="${SKILLS_ROUTER_VERSION:-latest}"
# 安装目标目录：默认是执行脚本时所在的目录
DEST="${SKILLS_ROUTER_DEST:-$(pwd)}"
ASSET="skills-router.tar.gz"

if [ ! -d "$DEST" ]; then
  echo "error: destination directory does not exist: $DEST" >&2
  exit 1
fi

if [[ "$VERSION" =~ ^v[0-9] ]]; then
  URL="https://github.com/$REPO/releases/download/$VERSION/$ASSET"
else
  URL="https://github.com/$REPO/releases/latest/download/$ASSET"
fi

echo "==> Downloading skills-router ($VERSION)"
echo "    $URL"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$URL" -o "$TMP/$ASSET"
elif command -v wget >/dev/null 2>&1; then
  wget -q "$URL" -O "$TMP/$ASSET"
else
  echo "error: neither curl nor wget is available" >&2
  exit 1
fi

echo "==> Extracting..."
tar -xzf "$TMP/$ASSET" -C "$TMP"

if [ ! -d "$TMP/.skills-router" ]; then
  echo "error: archive does not contain .skills-router" >&2
  exit 1
fi

echo "==> Installing to $DEST"
if [ -d "$DEST/.skills-router" ]; then
  echo "    backing up existing .skills-router -> .skills-router.bak"
  rm -rf "$DEST/.skills-router.bak"
  mv "$DEST/.skills-router" "$DEST/.skills-router.bak"
fi
cp -R "$TMP/.skills-router" "$DEST/.skills-router"
if [ -f "$TMP/README.md" ]; then
  cp "$TMP/README.md" "$DEST/README.skills-router.md"
fi

echo "==> Generating platform entries (init.py)"
if command -v python3 >/dev/null 2>&1; then
  (cd "$DEST" && python3 .skills-router/init.py) || true
elif command -v python >/dev/null 2>&1; then
  (cd "$DEST" && python .skills-router/init.py) || true
fi

echo "==> Done."
echo "    skills-router installed at: $DEST/.skills-router"
echo "    Next steps:"
echo "      python .skills-router/scripts/skills_router.py refresh"
echo "      python .skills-router/scripts/skills_router.py search \"markdown\""
