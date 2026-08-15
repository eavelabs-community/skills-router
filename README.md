<div align="center">

# Skills Router

*cross-platform AI skills router*

[![Release](https://img.shields.io/github/v/release/eavelabs-community/skills-router?style=flat-square&label=Release)](https://github.com/eavelabs-community/skills-router/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/eavelabs-community/skills-router/release.yml?style=flat-square&label=CI)](https://github.com/eavelabs-community/skills-router/actions)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[![Copilot](https://img.shields.io/badge/Copilot-supported-brightgreen?style=flat-square)]()
[![CodeBuddy](https://img.shields.io/badge/CodeBuddy-supported-brightgreen?style=flat-square)]()
[![Claude](https://img.shields.io/badge/Claude-supported-brightgreen?style=flat-square)]()
[![Codex](https://img.shields.io/badge/Codex-supported-brightgreen?style=flat-square)]()

</div>

Skills Router 是一套**跨平台技能发现/安装层**。它以 `.skills-router/` 为唯一手写维护的核心，
通过初始化脚本把薄薄的平台入口（`SKILL.md`）分发到各个 AI 平台自己的技能目录，
让 **Copilot、CodeBuddy、Claude、Codex** 等编辑器都能使用同一套技能路由能力。

- **发现**：从配置的技能源仓库（如 JetBrains、Anthropic 官方 skills 仓库）拉取并建立本地技能索引。
- **搜索**：支持单查询与多查询检索，对名称、描述做加权打分，并支持中英文查询词扩展。
- **安装**：将兼容的技能直接安装到目标平台的技能目录；不兼容时提供适配流程指导。
- **分发**：`init.py` 按工作区中已存在的平台标记，自动生成各平台的薄入口文件。

## 目录结构

```
skills-router/
├── .skills-router/                 # 共享核心（唯一手写维护处）
│   ├── init.py                    #   初始化脚本：检测平台 → 生成平台入口
│   ├── scripts/
│   │   └── skills_router.py        #   共享核心：refresh / search / install / detect-platform
│   ├── templates/                 #   初始化模板（共享模板 + 平台特有覆盖）
│   ├── sources.json               #   技能源配置（JetBrains / Anthropic 仓库）
│   ├── platforms.json             #   平台定义（copilot / claude / codex / codebuddy）
│   ├── registry.json              #   生成产物：refresh 后生成的技能索引（勿手改）
│   ├── tests/                     #   离线工作流测试 + 50 场景双语检索评估
│   └── README.md                  #   共享核心的详细说明
└── README.md                      # 本文件
```

> 详细设计原则（单一来源、模板分层、覆盖式精细化等）见 [`.skills-router/README.md`](.skills-router/README.md)。

## 下载安装

发布包以 GitHub Releases 的形式分发（打 `v*` tag 自动构建，见 [发布新版本](#发布新版本)）。
每次发布在 Release 页面提供 `skills-router.tar.gz`（核心包）与带版本号的副本。

**方式一：直接下载发布包（推荐）**

Release 页面下载 `skills-router.tar.gz` 后：

```bash
tar -xzf skills-router.tar.gz
python .skills-router/init.py        # 自动探测平台并生成入口
```

**方式二：命令行快速安装（Linux / macOS / WSL）**

`install.sh` 随源码仓库管理，可从 GitHub 原始文件下载后执行（默认已指向 `eavelabs-community/skills-router`，如需其他仓库可设置 `SKILLS_ROUTER_REPO` 环境变量）：

```bash
curl -fsSL -o install.sh https://raw.githubusercontent.com/eavelabs-community/skills-router/main/install.sh
chmod +x install.sh

# 安装最新版到当前目录
./install.sh

# 安装指定版本 / 指定目录 / 指定仓库
VERSION=v1.2.3 ./install.sh
DEST=/path/to/project ./install.sh
SKILLS_ROUTER_REPO=eavelabs-community/skills-router ./install.sh
```

**方式三：命令行快速安装（Windows PowerShell）**

```powershell
curl.exe -fsSL -o install.ps1 https://raw.githubusercontent.com/eavelabs-community/skills-router/main/install.ps1

# 在目标项目目录中执行（需 PowerShell 7 或 Windows 10 1803+）
.\install.ps1

# 安装指定版本 / 指定目录 / 指定仓库
.\install.ps1 -Version v1.2.3
.\install.ps1 -Destination D:\MyProject
$env:SKILLS_ROUTER_REPO = "eavelabs-community/skills-router"; .\install.ps1
```

安装脚本会自动：从 GitHub Releases 下载发布包 → 备份已存在的 `.skills-router`（`.skills-router.bak`）→ 把 `.skills-router/` 安装到**执行脚本时所在的目录** → 运行 `init.py` 探测工作区中的平台并生成入口。安装完成后使用：

```powershell
python .skills-router/scripts/skills_router.py refresh
python .skills-router/scripts/skills_router.py search "markdown"
```

## 快速开始

```powershell
# 1. 生成平台入口（自动探测工作区中已存在的平台）
python .skills-router/init.py

# 2. 刷新技能注册表（拉取 sources.json 中配置的仓库，生成 registry.json）
python .skills-router/scripts/skills_router.py refresh

# 3. 搜索技能
python .skills-router/scripts/skills_router.py search "markdown"
python .skills-router/scripts/skills_router.py search-many "幻灯片" "word" --limit 5

# 4. 安装技能到目标平台
python .skills-router/scripts/skills_router.py install <candidate-id> --platform codebuddy

# 5. 查看/准备不兼容技能的适配
python .skills-router/scripts/skills_router.py status <candidate-id> --platform codebuddy
python .skills-router/scripts/skills_router.py prepare-adaptation <candidate-id> --platform codebuddy
```

## 命令行参考

### 入口分发 `init.py`

| 参数 | 说明 |
|------|------|
| （无参数） | 自动探测工作区中已存在的平台并生成入口 |
| `--platform <name>` | 显式指定平台（可多次指定） |
| `--all` | 为所有配置的平台生成 |
| `--dry-run` | 仅预览将要写入的文件，不实际写入 |
| `--workspace <path>` | 指定项目根目录（默认：仓库根目录） |

### 核心脚本 `skills_router.py`

| 命令 | 说明 |
|------|------|
| `refresh` | 拉取技能源仓库，刷新 `registry.json` |
| `detect-platform` | 探测工作区中存在的平台及当前激活平台 |
| `search <query>` | 单查询搜索技能（`--limit` 控制返回条数） |
| `search-many <q1> <q2> ...` | 多查询合并检索，按综合得分排序 |
| `status <candidate-id>` | 查看某候选技能在目标平台的兼容性与安装状态 |
| `install <candidate-id>` | 安装技能到目标平台（仅限原生兼容，`--force` 可覆盖已安装） |
| `prepare-adaptation <candidate-id>` | 输出不兼容技能的适配要求清单，供当前 AI 完成适配 |
| `plan-install <candidate-id>` | 预览该技能在各检测到平台上的安装计划 |

通用参数：`--sources` / `--registry` / `--cache` / `--platforms` / `--workspace`。
平台可通过 `--platform <name>` 显式指定，或 `--platform auto`（默认）自动解析：
`SKILLS_ROUTER_PLATFORM` 环境变量 > 工作区唯一平台标记。

## 平台标记与安装根

| 平台      | 标记文件                       | 技能安装根             |
|-----------|--------------------------------|------------------------|
| copilot   | `.github/copilot-instructions.md` | `.github/skills`    |
| claude    | `.claude`                      | `.claude/skills`       |
| codex     | `.agents`                      | `.agents/skills`       |
| codebuddy | `.codebuddy`                   | `.codebuddy/skills`    |

## 添加技能源

编辑 `.skills-router/sources.json`，追加一个包含 `id`、`repo`、`ref`、`skills_path`、
`priority`、`trusted` 的对象，然后重新运行 `refresh` 即可。

## 测试

```powershell
python .skills-router/tests/test_skills_router.py -v   # 离线工作流测试
python .skills-router/tests/evaluate_router.py        # 50 场景双语检索评估
```

## 设计原则

- **单一来源**：`.skills-router/` 是唯一手写维护处；各平台目录下的入口文件均为生成产物，重跑 `init.py` 再生成。
- **薄入口**：平台入口只含路由工作流说明与脚本调用，具体逻辑全部指向共享核心，避免多份漂移。
- **覆盖式精细化**：`init.py` 渲染时优先取 `templates/overrides/<平台>/<同名文件>`，没有则回退共享模板。
- **绝对路径**：生成时把脚本路径替换为指向共享核心的绝对路径，入口放在哪个平台目录都能正确调用。

## 发布新版本

`.github/workflows/release.yml` 会在以下时机自动运行：

1. 推送 `v*` 格式的 tag（如 `v1.0.0`）—— 推荐方式；
2. 或手动触发 workflow（`workflow_dispatch`）。

流程：先跑 `tests/` 下的全部测试 → 通过后打包 `.skills-router/`（排除 `.cache`、`registry.json`、`__pycache__`）与 `README.md` 为 `skills-router.tar.gz`（另附带版本号的副本）→ 创建 GitHub Release 并上传附件。

```bash
# 本地打 tag 并推送，即自动触发发布
git tag v1.0.0
git push origin v1.0.0
```

> `install.sh` / `install.ps1` 默认已指向 `eavelabs-community/skills-router`，使用者可通过 `SKILLS_ROUTER_REPO` 环境变量或脚本参数覆盖。
