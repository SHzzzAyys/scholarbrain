# obsidian-second-brain fork · Harden Plan

> Fork: `eugeniughelbur/obsidian-second-brain` (1337 ⭐, MIT, 上游 2026-05 仍活跃)
> 本地: `D:\projects\obsidian-second-brain`
> 包管理: `uv`（**不是** pip）
> 立项日期: 2026-05-25

---

## 0. 项目目标

**一句话目标**: 把"创作者/营销人的二号大脑"改造成"中文科研人的二号大脑"——在 Obsidian vault 之上叠加 PubMed/arXiv/Semantic Scholar 学术检索 + DeepSeek 国内可用 LLM + 中文命令触发 + 六模块论文抽取 + PushGate 推送的端到端科研工作流。

**差异化定位（vs 上游）**:

| 维度 | 上游 (eugeniughelbur) | 本 fork |
|---|---|---|
| LLM 后端 | OpenAI / Perplexity | **DeepSeek**（国内直连，零墙）+ 可选 Perplexity |
| 研究信息源 | Perplexity 网搜 | **PubMed + arXiv + Semantic Scholar** + 可选网搜 |
| 命令触发 | 纯英文 | **中英双语并列**（不替换） |
| 论文入库 | 手动粘贴 | **MinerU / Docling 批量解析**，paper_extractor 六模块抽取 |
| 通知 | 无 | **PushGate** webhook (Bark / 钉钉 / 飞书 / 邮件) |
| 期刊元信息 | 无 | **journal_query** 自动写 IF / 分区到 frontmatter |
| 目标用户 | indie hacker / marketer | 中文圈科研人（医学 + CS） |

**v1.0 KPI（明确数字，2026-08-31 前达成）**:

1. PubMed / arXiv / Semantic Scholar 三个 backend 端到端跑通，单 topic 检索 → vault 落档 < 90 秒
2. `/research` 等 10+ 命令支持中文 trigger（"深度调研" / "做综述" 等）
3. DeepSeek backend 替换 OpenAI 后，5 个 phase 的 research_deep.py 零行为退化
4. README 中英双语 + 1 个 5 分钟 demo 视频
5. GitHub fork 独立 ⭐ ≥ 50（v0.5 发布后 30 天内）
6. 给上游提至少 **3 个**可合并 PR

---

## 1. v0.1 任务清单（≈9 小时 / 1.5 天）

每条 = 文件路径 / 改动类型 / 工时 / 完成判定。

### 1.1 新建 `scripts/research/lib/deepseek.py` — 30 分钟 ✅ 已完成
- **状态**: 已落盘（requests 直连，max_tokens=8000，四键返回 {text/citations/model/raw}）
- **完成判定**:
  ```bash
  uv run python -c "from scripts.research.lib import deepseek; r = deepseek.call('一句话介绍光合作用'); assert 'text' in r and 'citations' in r and 'model' in r and 'raw' in r; print(r['text'][:200])"
  ```

### 1.2 新建 `scripts/research/lib/pubmed.py` — 30 分钟 ✅ 已完成
- **状态**: 已落盘（esearch→esummary→efetch，PMID 去重，rate limit，User-Agent，email/tool query param 齐全）
- **完成判定**:
  ```bash
  uv run python -c "from scripts.research.lib import pubmed; r = pubmed.call('Toxoplasma gondii RNA-seq', max_results=5); assert len(r['citations']) >= 3; print([c['pmid'] for c in r['citations']])"
  ```

### 1.3 新建 `scripts/research/lib/arxiv.py` — 1 小时 ✅ 已完成
- **状态**: 已落盘（stdlib xml.etree 解析，3 秒礼貌间隔，Atom namespace 正确）
- **完成判定**:
  ```bash
  uv run python -c "from scripts.research.lib import arxiv; r = arxiv.call('graph neural network drug discovery', max_results=5); assert len(r['citations']) >= 3; print([c['title'][:60] for c in r['citations']])"
  ```

### 1.4 新建 `scripts/research/lib/semantic_scholar.py` — 1 小时
- **改动类型**: 新增
- **内容**: Semantic Scholar Graph API `/graph/v1/paper/search`；支持可选 API key（env `SEMANTIC_SCHOLAR_API_KEY`，无 key 走 100 req/5min 公共限额）；同四键返回
- **完成判定**:
  ```bash
  uv run python -c "from scripts.research.lib import semantic_scholar as ss; r = ss.call('large language model scientific writing', limit=5); assert len(r['citations']) >= 3"
  ```

### 1.5 改 `scripts/research/lib/config.py` 加 DeepSeek / NCBI 配置 — 5 分钟 ⚠️ 必做
- **改动类型**: 修改
- **关键**：当前 deepseek.py / pubmed.py 已 import 这些名字，但 config.py 还没加，**跑测试会报 ImportError**
- **内容**: 加 `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL`（默认 `"deepseek-chat"`） / `DEEPSEEK_REASONER_MODEL`（默认 `"deepseek-reasoner"`） / `NCBI_EMAIL`（required lambda） / `PUBMED_API_KEY`（optional lambda） / `SEMANTIC_SCHOLAR_API_KEY` 字段；对齐已有 `PERPLEXITY_API_KEY` 的 lambda 风格
- **完成判定**: `grep DEEPSEEK_API_KEY scripts/research/lib/config.py` 命中 + `~/.config/obsidian-second-brain/.env` 含全部新字段

### 1.6 改 `scripts/research/research_deep.py` — 2 小时
- **改动类型**: 修改
- **内容**:
  - Phase 2 (gap_LLM) 与 Phase 4 (synthesis_LLM) 默认调用 `lib.deepseek` 替换 `lib.perplexity`
  - Phase 3 (targeted_research) 加 `--backend {perplexity, pubmed, arxiv, semantic_scholar, all}` 分支；`all` = 并发四路合流去重
  - 调用 DeepSeek 时 `max_tokens >= 8000`（paper_extractor 已知坑，已硬编码进 deepseek.py 默认值）
- **完成判定**:
  ```bash
  uv run -m scripts.research.research_deep "Toxoplasma RNA-seq differential expression" --backend pubmed
  # 产出 vault note 包含 ≥5 个 PMID 引用
  ```

### 1.7 改 `scripts/research/research.py` 加 `--backend` — 1 小时
- **改动类型**: 修改
- **内容**: 透传 `--backend` 到 `research_deep.py`；CLI `--help` 显示可选值
- **完成判定**: `uv run -m scripts.research.research --help` 输出含 `--backend`

### 1.8 改 `GAP_PROMPT` — 30 分钟
- **改动类型**: 修改（位于 `research_deep.py`）
- **内容**: 在原 prompt 中加入学术 source 选项说明（pubmed / arxiv / semantic_scholar），并加 "如用户语言为中文，请用中文输出 gap 列表，每条不超 40 字"；保持英文行为不变
- **完成判定**: 中文 topic 输入时 gap 列表为中文，英文输入时英文输出

### 1.9 `commands/research.md` 加中文 trigger — 30 分钟
- **改动类型**: 修改
- **内容**: frontmatter 加 `triggers_zh: ["调研", "研究一下", "查一下", "文献调研"]`；命令体兼容中文 args
- **完成判定**: `grep -E "调研|做综述" commands/research.md commands/research-deep.md` 命中

### 1.10 端到端真测 — 2 小时
- **改动类型**: 测试（生成 cassette fixture）
- **内容**:
  - 医学 topic: "Toxoplasma gondii Chinese1 strain transcriptome"
  - CS topic: "Mixture-of-Experts inference latency"
  - 各跑一遍 `--backend all` 全链路；记录 vault 落档 .md + 截图入 `tests/fixtures/`
- **完成判定**: 两个 topic 各 1 个 vault note 生成成功；note 中引用数 ≥ 5；DeepSeek 摘要段落 ≥ 200 字

**v0.1 合计 9 小时**。完成后立刻 tag `v0.1.0` 并发一条 X / 即刻预告。

---

## 2. v0.2 - v1.0 路线图（≈8.5 天，4 周里程碑）

| 里程碑 | 任务 | 工时 | 截止 |
|---|---|---|---|
| **v0.2** | researcher preset 重做接 paper_extractor 六模块（基本信息/方法/结论/数据/局限/创新点 + 证据卡） | **3 天** | W1 末 |
| **v0.3** | PushGate webhook 整合（research_deep 完成后推 Bark / 飞书） | **0.5 天** | W2 头 |
| **v0.4** | MinerU + Docling PDF batch 入 vault（`/obsidian-ingest --pdf-dir`） | **1.5 天** | W2 末 |
| **v0.5** | journal_query 接入（自动写 IF / 分区 / JCR 区到 frontmatter） | **1 天** | W3 头 |
| **v0.6** | 中文命令全套（10+ 个 obsidian-\* + research\* 加中文 trigger） | **1.5 天** | W3 末 |
| **v1.0** | README 中英双语 + 5 分钟 demo 视频 + V2EX / 即刻 / X / 小红书推广 | **1 天** | W4 末 |

**总计 v0.2-v1.0: 8.5 天**（与上游同步 buffer 已含在每周末半天）。

---

## 3. 硬约束（hive AGENTS.md 风格 · 不可违反）

1. **接口契约不动**: 所有新 `scripts/research/lib/*.py` 必须返回 `{text: str, citations: list[dict], model: str, raw: dict}` 四键，键名/类型与 `perplexity.py` 完全一致。citations 元素至少含 `title, url`；可选 `pmid / doi / year / authors`。
2. **依赖白名单**: 不许引入 `requests + xml.etree + stdlib` 之外的新 Python 依赖；DeepSeek 走 `requests` 直连 OpenAI 兼容端点，不许装 `openai` SDK，不许换 `httpx`。
3. **`SKILL.md` 只读**: 1166 行的单一事实来源不许 fork 内直改；要改先给上游开 PR，上游 merge 后 rebase 拉回。
4. **中文 trigger 并列不替换**: 任何 `commands/*.md` 加中文 alias 时，原英文 trigger 必须保留；不许删上游任何一条 alias。
5. **真集成测试**: 每个新 `lib/*.py` 必须有打真 API 的集成测试，VCR/cassette fixture 进 git (`tests/fixtures/cassettes/<lib>.yaml`)；CI 默认放回放模式，本地 `PYTEST_RECORD=1` 才打真网。
6. **DeepSeek `max_tokens >= 8000`**: 所有 `deepseek.call` 默认 `max_tokens=8000`；低于此值的调用必须显式注释为什么（paper_extractor 实测：低于 8000 容易被截断）。
7. **PubMed / arXiv rate limit + UA**:
   - PubMed: 无 key 时 ≤ 3 req/s（每次 sleep 0.34s），有 key 时 ≤ 10 req/s（每次 sleep 0.11s）；`User-Agent` = `obsidian-second-brain-research/<ver> (mailto:<NCBI_EMAIL>)`；esearch/esummary/efetch URL 都加 `email + tool` query param
   - arXiv: ≥ 3 秒/请求（官方要求）；UA 同上
   - 违反 = 直接抛 RuntimeError，不许静默重试
8. **API key 仅来自 `.env`**: 任何 `lib/*.py` 不许出现硬编码 key / sk- 字样；CI 检查 `grep -rE 'sk-[a-zA-Z0-9]{20,}' scripts/` 必须为空。
9. **向下兼容上游 vault schema**: 任何写入 vault 的 frontmatter 字段必须是新增；不许改上游已用字段的语义（如 `tags / status / created / type / topic`）。新增字段建议前缀 `research_` 或 `paper_`。

---

## 4. 与上游同步策略

**rebase 频率**: 每周一上午 `git fetch upstream && git rebase upstream/main`；冲突 < 30 分钟搞定，超时立刻停手发 issue。

**永远跟上游的目录/文件**（出冲突 = 接受上游版）:
- `commands/` 下绝大部分（除明确加了中文 trigger 的，见下）
- `SKILL.md`（单一事实来源）
- `adapters/`（claude-code / codex-cli / gemini-cli / opencode）
- `hooks/`
- `install.sh`
- `architecture.md`
- `examples/`

**fork 独占文件**（冲突 = 保留 fork 版）:
- `scripts/research/lib/deepseek.py`
- `scripts/research/lib/pubmed.py`
- `scripts/research/lib/arxiv.py`
- `scripts/research/lib/semantic_scholar.py`
- `HARDEN_PLAN.md`（本文）
- `tests/fixtures/cassettes/*`
- `README.zh-CN.md`

**冲突时 fork 优先**（手动 merge，保留 fork 改动 + 上游新增）:
- `scripts/research/research_deep.py`（Phase 2/3/4 已改）
- `scripts/research/research.py`（`--backend` 已加）
- `scripts/research/lib/config.py`（DeepSeek / NCBI 字段已加）
- `GAP_PROMPT` 所在位置（在 research_deep.py 内）
- 加了中文 trigger 的 `commands/research.md` / `commands/research-deep.md` / `commands/obsidian-ingest.md` 等

**rebase SOP**: 冲突时先 `git diff upstream/main -- <file>` 看上游意图，再决定保留哪一侧；3 个冲突文件以内手 merge，超过 3 个就拆 PR 反推上游。

---

## 5. 给上游的 PR 计划（≥ 3 个可拆 PR）

| # | 标题 | 修什么 | merge 概率 |
|---|---|---|---|
| PR1 | `feat(lib): add pluggable backend interface for research_deep Phase 3` | 把 Phase 3 的 perplexity 硬调用抽象为 `BackendProtocol`，仍默认 perplexity；不引入新依赖 | **高（80%）**——纯重构，对上游无害，反而让上游更易扩展 |
| PR2 | `feat(i18n): add zh-CN aliases for top 5 commands` | `commands/research.md / obsidian-capture.md / obsidian-daily.md / obsidian-find.md / obsidian-recap.md` 各加 1 行中文 alias；不删原文 | **中（50%）**——上游可能不想维护 i18n，但 alias 列表本来就在；可做成可选 |
| PR3 | `fix(prompts): make GAP_PROMPT language-aware` | GAP_PROMPT 检测输入语言后输出对应语言；英文行为字节级不变 | **中高（65%）** |
| PR4（备） | `docs(lib): document Backend return contract (text/citations/model/raw)` | 把四键契约写进 `architecture.md` 或新建 `lib/README.md` | **高（85%）**——纯文档 |

PR 顺序: PR1 → PR4 → PR2 → PR3。PR1 合了再发 PR2/PR3，避免被一次性打回。

---

## 6. 营销 / 发布策略

### v0.1（W1 末，2026-06-01 前）
- **渠道**: 只发即刻 + X 个人号；标题"给中文圈科研人的二号大脑（v0.1）—— PubMed + DeepSeek 二合一"
- **目标**: 找 5 个种子用户内测；不求 ⭐
- **附**: 30 秒 GIF 跑通"输入中文 topic → 落 vault note → 含 5 个 PMID"

### v0.5（W3 末，2026-06-15 前）
- **渠道**: V2EX 分享发现 / 小红书图文（带"科研工具"#） / 即刻 / X / Bilibili 5 分钟 demo
- **目标**: ⭐ 30+，真实试用 ≥ 20 人
- **附**: README.zh-CN + 一键安装脚本（`curl ... | bash` 带 DeepSeek key 引导）

### v1.0（W4 末，2026-06-22 前）
- **渠道**: Hacker News Show HN（英文版） / Reddit r/ObsidianMD + r/PhD / 知乎"有哪些科研工具值得安利" / 微信"丁香园 / 募格" 投稿
- **目标**: ⭐ 50+（fork 独立计），1-2 个非作者 contributor
- **附**: 演示视频 + 与上游差异对照表

---

## 7. 立刻动手的第一个 90 分钟

**目标**: 90 分钟后，本地能跑通 PubMed 真链路 + DeepSeek 真链路。

> ⚠️ 三个 lib 文件已落盘（1.1 / 1.2 / 1.3），所以这 90 分钟主要做 **config 接入 + 烟囱测试 + 第一次端到端跑通**。

### 0-30 min · 改 config.py + 建 .env

```powershell
cd D:\projects\obsidian-second-brain
git remote add upstream https://github.com/eugeniughelbur/obsidian-second-brain.git
git fetch upstream
git checkout -b feat/deepseek-pubmed-arxiv

# 0-15 min: 编辑 scripts\research\lib\config.py
# 在已有 PERPLEXITY_API_KEY 那段下面追加（对齐 lambda 风格）：
#   DEEPSEEK_API_KEY = lambda: get_required("DEEPSEEK_API_KEY")
#   DEEPSEEK_MODEL = get_optional("DEEPSEEK_MODEL", "deepseek-chat")
#   DEEPSEEK_REASONER_MODEL = get_optional("DEEPSEEK_REASONER_MODEL", "deepseek-reasoner")
#   NCBI_EMAIL = lambda: get_required("NCBI_EMAIL")
#   PUBMED_API_KEY = lambda: get_optional("PUBMED_API_KEY", "")
#   SEMANTIC_SCHOLAR_API_KEY = lambda: get_optional("SEMANTIC_SCHOLAR_API_KEY", "")

# 15-25 min: 同步 .env（项目实际位置 ~/.config/obsidian-second-brain/.env）
mkdir -Force $HOME\.config\obsidian-second-brain
notepad $HOME\.config\obsidian-second-brain\.env
# 填入:
#   DEEPSEEK_API_KEY=sk-...
#   DEEPSEEK_MODEL=deepseek-chat
#   DEEPSEEK_REASONER_MODEL=deepseek-reasoner
#   NCBI_EMAIL=phancaotho416@gmail.com
#   PUBMED_API_KEY=
#   SEMANTIC_SCHOLAR_API_KEY=
#   OBSIDIAN_VAULT_PATH=D:\obsidian-vault     # 改成你真实 vault 路径

# 25-30 min: 烟囱测 deepseek
uv run python -c "from scripts.research.lib import deepseek; r = deepseek.call('用一句话介绍光合作用'); print(r['text'][:200]); assert all(k in r for k in ('text','citations','model','raw'))"
```

### 30-60 min · 跑通 PubMed + arXiv

```powershell
# 30-45 min: PubMed 真链路
uv run python -c "from scripts.research.lib import pubmed; r = pubmed.call('Toxoplasma gondii RNA-seq', max_results=3); print(len(r['citations']), '条结果'); [print(c['pmid'], c['title'][:60]) for c in r['citations']]"

# 45-60 min: arXiv 真链路
uv run python -c "from scripts.research.lib import arxiv; r = arxiv.call('mixture of experts inference', max_results=3); print(len(r['citations'])); [print(c['arxiv_id'], c['title'][:60]) for c in r['citations']]"
```

### 60-90 min · 改 research.py + 落第一笔 commit

```powershell
# 60-80 min: 改 scripts\research\research.py 加 --backend
notepad scripts\research\research.py
# 关键改动:
#   import argparse, 加 --backend 参数
#   根据 backend 路由到 perplexity.call / pubmed.call / arxiv.call
#   保持四键返回契约,后续 save_note() 不用改

# 80-85 min: 真跑端到端
uv run -m scripts.research.research "Toxoplasma RNA-seq methods" --backend pubmed

# 85-90 min: 第一个 commit
git add scripts/research/lib/deepseek.py scripts/research/lib/pubmed.py scripts/research/lib/arxiv.py scripts/research/lib/config.py scripts/research/research.py HARDEN_PLAN.md
git status   # 确认没误提交 .env
git commit -m "feat(lib): add deepseek + pubmed + arxiv backends, wire --backend flag

- New lib/deepseek.py: OpenAI-compatible DeepSeek client (max_tokens=8000, citations=[])
- New lib/pubmed.py: NCBI E-utilities esearch+esummary+efetch with rate limit + UA
- New lib/arxiv.py: arXiv Atom API via stdlib xml.etree, 3s polite interval
- config.py: add DEEPSEEK_API_KEY / DEEPSEEK_MODEL / NCBI_EMAIL / PUBMED_API_KEY
- research.py: add --backend {perplexity,pubmed,arxiv} routing
- All new libs follow perplexity.py contract: {text, citations, model, raw}

Refs: HARDEN_PLAN.md tasks 1.1-1.5, 1.7"
```

**90 分钟末尾交付物**:
1. `feat/deepseek-pubmed-arxiv` 分支已创建并落第一笔 commit
2. `lib/deepseek.py` + `lib/pubmed.py` + `lib/arxiv.py` 已可调用（已落盘）
3. `config.py` 加新字段 + `.env` 三件套对齐
4. PubMed + arXiv + DeepSeek 各跑一次真 API 验证
5. `--backend` flag 在 research.py 里跑通三个选项

---

## 风险（不美化）

- **DeepSeek 限流 / 偶发 502**: 国内 LLM 高峰期波动大，研究阶段不做重试爆破；遇 502 直接打断、记 log，留待 v0.3 加 retry/circuit breaker。
- **NCBI 邮箱被封**: 不按 ToS 填 `NCBI_EMAIL` 会被 ban IP；硬约束 7 已强制 UA + email，但 CI 仍要兜底检查。
- **上游 rebase 大爆炸**: 上游 2026-05 还在快速迭代，本 fork 改 `research_deep.py` 一旦上游同区域大改，冲突可能 1 天起步。**对策**: PR1（Backend 抽象）越早合上游越好；合不上就接受每周末 2-4 小时 rebase 成本。
- **paper_extractor 六模块迁移耦合**: paper_extractor 当前是 PyQt6 桌面工具，prompt + JSON schema 是核心可复用资产，但 UI 层要剥离；v0.2 拆分时只搬 `core/extractor.py` 与 `core/prompts.py`，不搬 UI。
- **MinerU / Docling 解析慢**: Docling 26 页 ~87 秒、MinerU 更慢；v0.4 必须做后台队列 + PushGate 完成通知，不能阻塞 vault 写入。
- **系统代理穿透学术 API**: `requests` 可能自动读取 Windows 系统代理（如 `127.0.0.1:1088`），导致 PubMed/arXiv 慢或失败；`lib/pubmed.py` 和 `lib/arxiv.py` 必须用 `Session.trust_env = False` 直连，详见 `TROUBLESHOOTING.md`。
- **⭐ 数 KPI 不一定能达**: 中文科研工具受众分散在微信/小红书/知乎，X / GitHub ⭐ 转化率低；如 v0.5 后 30 天 ⭐ < 20，KPI 5 调整为"真实安装用户 ≥ 30"。

---

**读完这份文档应能立刻 `git checkout -b feat/deepseek-pubmed-arxiv` 开干。**
