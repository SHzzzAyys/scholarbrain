# v0.2 Spec · paper_extract.py 集成

> Status: design approved 2026-05-26, Day 1 in progress
> Parent: HARDEN_PLAN.md task v0.2 (paper_extractor → fork integration, 3 days)
> Branch: feat/deepseek-pubmed-arxiv

---

## 0. 目标

新增 `lib/paper_extract.py`，把 paper_extractor (D:\projects\paper_extractor) 的「六模块抽取 + 证据卡 + 反幻觉 schema」剥离桌面 UI，搬进 obsidian-second-brain fork 作为底层组件。Day 3 末 `/research-paper <id>` 命令可用，输入 PMID / arXiv ID / DOI / 本地 PDF 路径，输出落到 `Research/Papers/<slug>.md`。

---

## 1. Schema diff（在 paper_extractor 原 schema 上加 4 字段）

### 1.1 受控词表（强制 LLM 输出可比对值）

```python
MODEL_ORGANISM_VOCAB = [
    "Toxoplasma gondii", "Plasmodium", "Cryptosporidium", "Eimeria",
    "Leishmania", "Trypanosoma", "Schistosoma", "Giardia",
    "Mus musculus", "Rattus norvegicus", "Homo sapiens",
    "cell line (HFF/HeLa/HEK293/etc)", "organoid", "in silico", "other",
]

RESULT_DIRECTION = ["positive", "negative", "mixed", "null"]
# null = no significant effect found (区别于 negative=明确反面证据)

METHOD_TAGS_VOCAB = [
    "CRISPR-Cas9", "CRISPR-screen", "RNAi", "AID", "DiCre", "Tet-on/off",
    "RNA-seq", "scRNA-seq", "ChIP-seq", "ATAC-seq", "Ribo-seq", "CUT&RUN",
    "BioID/TurboID", "co-IP", "Y2H", "pull-down",
    "X-ray crystallography", "cryo-EM", "AlphaFold",
    "live-cell imaging", "super-resolution", "EM",
    "flow cytometry", "mass spec", "metabolomics", "lipidomics",
    "mouse infection", "organoid culture", "in vitro infection",
    "computational modeling", "phylogenetics", "GWAS",
    "other",
]
```

### 1.2 在原 Metadata / TechnicalRoute / MainResults 加 3 字段

```python
@dataclass
class Metadata:
    title: str = ""
    authors: List[str] = field(default_factory=list)
    journal: str = ""
    year: str = ""
    doi: str = ""
    model_organism: str = ""        # ← 新增

@dataclass
class TechnicalRoute:
    main_strategy: str = ""
    key_steps: List[TechStep] = field(default_factory=list)
    notable_methods: List[str] = field(default_factory=list)
    method_tags: List[str] = field(default_factory=list)       # ← 新增

@dataclass
class MainResults:
    primary_findings: List[Finding] = field(default_factory=list)
    secondary_findings: List[str] = field(default_factory=list)
    result_direction: str = ""      # ← 新增
```

### 1.3 vault frontmatter 字段（不进 LLM schema，note 写入时设默认）

```yaml
user_relevance: ""        # 用户手填 high|medium|low
research_priority: ""     # 用户手填 1|2|3|backlog
read_status: "unread"     # unread|skimmed|read|annotated
```

---

## 2. 领域 prompt · C 方案（通用 default + vault 覆盖）

### 2.1 默认 SYSTEM_PROMPT（fork 内通用版）

去掉弓形虫专属词表，保留方法论部分。完整通用 prompt 在 `lib/paper_extract.py` 顶部。

### 2.2 用户领域覆盖：vault 根目录 `_DOMAIN.md`

```markdown
---
applies_to: [research-paper, paper-extract]
---
# 我的研究领域

【弓形虫核心】
...用户自由填写的领域知识
```

paper_extract.py 启动时：
1. 若 `<vault>/_DOMAIN.md` 存在 → 解析 markdown 正文（去掉 frontmatter）当 `{domain_prompt}` 插入 SYSTEM_PROMPT
2. 否则 `{domain_prompt}` = "你的专长涵盖广泛的科研领域,根据论文实际主题灵活适配"

**用户的弓形虫 prompt 不丢**：Day 1 自动生成 `D:\ToxoVault\_DOMAIN.md`，内容来自 paper_extractor 现有 SYSTEM_PROMPT 的弓形虫部分。

---

## 3. PDF 全文抓取策略

| 输入源 | 实现 | Day | 备注 |
|---|---|---|---|
| 本地 PDF 路径 | 直接传给 parser | Day 1 ✅ | 用 `pymupdf` minimal 解析 |
| arXiv ID | 拼 `https://arxiv.org/pdf/<id>.pdf` 下载 | Day 2 | lib/arxiv.py 加 download_pdf() |
| PMID | NCBI 查 PMC ID → PMC OA PDF | Day 2 | 非所有 PMID 有 PMC OA, fallback abstract |
| DOI | Unpaywall / Crossref | 推到 v0.4 | 单独工程量 |

**Day 1 只做本地 PDF**（最简单、立刻能测）。

---

## 4. Day 1-3 任务清单

### Day 1（~8 小时）— 核心抽取组件

| # | 任务 | 工时 | 完成判定 |
|---|---|---|---|
| 1.1 | 新建 `lib/paper_extract.py` 骨架（dataclass + 4 新字段 + 3 受控词表） | 1h | py_compile 通过 + `ExtractionResult().to_dict()` 含新字段 |
| 1.2 | 迁通用 SYSTEM_PROMPT + 加载 `_DOMAIN.md` 机制 | 1.5h | 单测：vault 有/无 `_DOMAIN.md` 两种情况下 system prompt 差异正确 |
| 1.3 | 迁 TASK_PROMPT 加 4 新字段约束 + 受控词表 | 1h | TASK_PROMPT 含 model_organism / method_tags / result_direction + 词表清单 |
| 1.4 | 写 `extract(text, vault_path=None) -> ExtractionResult` 主入口，复用 fork 的 deepseek.call | 1h | 喂手工 abstract 跑出完整 6 模块 + 4 新字段 |
| 1.5 | 生成 `D:\ToxoVault\_DOMAIN.md`（迁 paper_extractor 弓形虫部分） | 0.5h | 文件存在,内容完整 |
| 1.6 | 真测：抓 paper_extractor 现成 PDF 样本 → pymupdf 解析 → extract() | 2h | 6 模块全填 + method_tags 命中 ≥2 受控词 + result_direction ∈ 词表 |
| 1.7 | commit + 写 PROGRESS.md | 1h | feat(extract): port paper_extractor's 6-module schema as lib/paper_extract.py |

### Day 2（~8 小时）— 抓取层

| # | 任务 | 工时 |
|---|---|---|
| 2.1 | `lib/arxiv.py` 加 `download_pdf(arxiv_id) -> Path` | 1.5h |
| 2.2 | `lib/pubmed.py` 加 `pmid_to_pmc_pdf(pmid) -> Optional[Path]` | 2h |
| 2.3 | `lib/pdf_load.py` 统一入口 `load_text(source: str) -> str`（前缀路由 arxiv:/pmid:/local path） | 2h |
| 2.4 | 真测：3 种输入源跑 extract() 验证一致 | 2h |
| 2.5 | commit | 0.5h |

### Day 3（~8 小时）— 命令 + 集成

| # | 任务 | 工时 |
|---|---|---|
| 3.1 | `scripts/research/research_paper.py` 主脚本 | 2h |
| 3.2 | vault 模板：`Research/Papers/<YYYY-MM-DD>__<first-author-year>-<short-title>.md` | 1.5h |
| 3.3 | `commands/research-paper.md` 文档（英中双 trigger） | 1h |
| 3.4 | 集成 PushGate 通知 | 0.5h |
| 3.5 | 端到端真测：3 个真实 case | 2.5h |
| 3.6 | commit + tag v0.2.0 + 更新 HARDEN_PLAN | 0.5h |

---

## 5. 与上游同步策略

### 新增 fork 独占文件（rebase 永远保留 fork 版）

- `scripts/research/lib/paper_extract.py`
- `scripts/research/lib/pdf_load.py`（Day 2）
- `scripts/research/research_paper.py`（Day 3）
- `commands/research-paper.md`（Day 3）
- `V02_PAPER_EXTRACT_SPEC.md`（本文档）

### 修改上游文件（冲突时 fork 优先）

- `scripts/research/lib/arxiv.py`（加 download_pdf）
- `scripts/research/lib/pubmed.py`（加 pmid_to_pmc_pdf）

---

## 6. 关键技术决策汇总（避免后续遗忘）

1. **schema 4 新字段全加**，因为加字段成本 << 删字段
2. **领域 prompt 走 C 方案**：通用 default + vault `_DOMAIN.md` 覆盖
3. **PDF 全文优先**（不是 abstract）：质量 > 速度
4. **lib 命名 `paper_extract.py`**：对齐 paper_extractor 项目名
5. **复用 fork 已有 deepseek.call**：不再迁 paper_extractor 的 LLMBackend 三件套
6. **`_extract_json` 函数直接搬**：paper_extractor 已经验证过的 markdown 剥离 + 最外层大括号兜底
7. **max_tokens=8000 强制**（paper_extractor 已知坑：6000 截断、8000 完整）

---

## 7. 风险与对冲

| 风险 | 概率 | 对冲 |
|---|---|---|
| DeepSeek 输出 method_tags 不在受控词表 | 高 | TASK_PROMPT 列受控词表 + 允许 fallback "other"；从 LLM 输出加白名单过滤一道 |
| `_DOMAIN.md` 解析失败导致 prompt 注入空字符串 | 中 | load_domain_prompt 函数兜底 try/except + 缺失时用通用 default |
| PDF 解析层质量差（pymupdf minimal） | 中 | Day 1 用 pymupdf 验通流程；MinerU/Docling 升级推到 v0.4 |
| 中文 prompt + 英文论文导致输出语言混乱 | 中 | TASK_PROMPT 显式 "输出语言: 中文(英文专有名词保留)"  |
| 上游 rebase 改了 lib/arxiv.py 撞我加的 download_pdf | 低 | 5 节策略已声明 fork 优先 |
