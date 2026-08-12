# .skills-router — 多平台技能路由器（单一来源）

Skills Router 是一套**跨平台技能发现/安装层**。它以 `.skills-router/` 为唯一手写维护的核心，
通过初始化脚本把薄薄的平台入口（`SKILL.md`）分发到各个 AI 平台自己的技能目录，
从而让 **Copilot、CodeBuddy、Claude、Codex** 等编辑器都能使用同一套技能路由能力。

## 目录结构

```
.skills-router/
├── templates/                      # 初始化模板（唯一手写维护）
│   ├── SKILL.md.template           #   共享入口模板：所有平台共用（SKILL.md 格式）
│   └── overrides/                  #   平台特有模板（含对共享模板的差异覆盖）
│       └── copilot/
│           └── copilot-instructions.md.template  # Copilot 自动触发入口
├── init.py                # 初始化脚本：检测平台 → 渲染共享模板 + 平台特有 init 文件
├── skills_router.py        # 共享核心：refresh / search / install / detect-platform
├── sources.json           # 共享：技能源配置（JetBrains / Anthropic 仓库）
├── platforms.json         # 共享：平台定义（copilot / claude / codex / codebuddy）+ init_files
├── registry.json          # 生成产物：refresh 后生成的技能索引（勿手改）
└── tests/                 # 共享：离线工作流测试 + 50 场景评估
```

## 设计原则

- **单一来源**：`.skills-router/` 是唯一手写维护处；各平台目录下的入口文件（`skills-router/SKILL.md`、
  以及 `platforms.json` 中 `init_files` 声明的文件，如 `.github/copilot-instructions.md`）均为
  **生成产物**，请勿手改，重跑 `init.py` 即可再生成。
- **模板分层**：`templates/` 根目录只放**全平台共享**的模板（当前只有 `SKILL.md.template`，
  4 个平台都是 SKILL.md 格式，仅路径占位符不同）；**平台特有**的模板统一放
  `templates/overrides/<平台>/`（如 copilot 的 `copilot-instructions.md.template`），并在
  `platforms.json` 的 `init_files` 里声明「模板 → 输出路径」。新增平台 = 加模板 + 加配置，不改脚本。
- **覆盖式精细化**：`init.py` 渲染时对任意模板**优先取 `templates/overrides/<平台>/<同名文件>`，
  没有就回退共享模板**。所以平台特有内容与「差异覆盖」共用同一套机制、同一个目录——差异是
  「增量覆盖」而非「整份复制」，无差异平台零成本，天然防漂移。
- **薄入口**：平台入口只含路由工作流说明与脚本调用，具体逻辑全部指向共享核心，避免多份漂移。
- **脚本路径用绝对路径**：生成时把 `{{ROUTER_SCRIPT}}` 替换为指向共享核心的绝对路径，
  因此无论入口放在哪个平台目录都能正确调用同一份核心；`{{ROUTER_SKILL}}` 则替换为相对项目根
  的入口路径（如 `.github/skills/skills-router/SKILL.md`）。

## 使用

```powershell
# 1. 生成平台入口（自动探测工作区中已存在的平台）
#    每个平台：写 install_root/skills-router/SKILL.md（共享模板）
#    copilot 额外写 .github/copilot-instructions.md（overrides/copilot 模板）
python .skills-router/init.py

# 2. 显式指定平台 / 全平台 / 预览
python .skills-router/init.py --platform codebuddy --platform copilot
python .skills-router/init.py --all
python .skills-router/init.py --dry-run

# 3. 刷新技能注册表（拉取 sources.json 中的仓库）
python .skills-router/scripts/skills_router.py refresh

# 4. 多查询搜索 / 安装 / 适配
python .skills-router/scripts/skills_router.py search-many "<q1>" "<q2>" --limit 5
python .skills-router/scripts/skills_router.py install <candidate-id> --platform codebuddy
python .skills-router/scripts/skills_router.py prepare-adaptation <candidate-id> --platform codebuddy
```

## 平台标记与安装根

| 平台      | 标记文件                 | 技能安装根             |
|-----------|--------------------------|------------------------|
| copilot   | `.github/copilot-instructions.md` | `.github/skills` |
| claude    | `.claude`                | `.claude/skills`       |
| codex     | `.agents`                | `.agents/skills`       |
| codebuddy | `.codebuddy`             | `.codebuddy/skills`    |

> 平台标记决定 `detect-platform` 探测与 `init.py` 自动分发；安装根决定业务技能装到哪个平台目录。
> `init_files` 决定该平台除了 `skills-router/SKILL.md` 之外，`init.py` 还会把哪些模板渲染到哪些位置
> （当前仅 copilot 声明了 `.github/copilot-instructions.md`——它既是标记文件也是自动触发入口）。

## 测试

```powershell
python .skills-router/tests/test_skills_router.py -v   # 离线工作流测试
python .skills-router/tests/evaluate_router.py        # 50 场景双语检索评估
```

## 与旧版 `.github/skills/skills-router` 的关系

迁移后，`.github/skills/skills-router/SKILL.md` 由 `init.py` 重新生成，成为指向共享核心的薄入口；
核心逻辑（`skills_router.py`、`sources.json`、`platforms.json`、`tests/`）统一收纳到 `.skills-router/`。
如需新增技能源，只需编辑 `.skills-router/sources.json`。
