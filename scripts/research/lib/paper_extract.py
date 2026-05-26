"""Paper six-module extraction (ported from paper_extractor D:\\projects\\paper_extractor).

Core capability: given the full text (or abstract) of an academic paper, call
DeepSeek to produce a structured 6-module ExtractionResult JSON with controlled
vocabularies for cross-paper comparison.

Output schema follows paper_extractor's dataclass design with 3 additions for
review-writing use cases:
    - metadata.model_organism      (controlled vocab)
    - technical_route.method_tags  (controlled vocab, list)
    - main_results.result_direction (positive/negative/mixed/null)

Domain prompt strategy: generic default + vault override via `_DOMAIN.md`.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import deepseek
from .config import VAULT_PATH


# ============================================================
# Controlled vocabularies (cross-paper comparison friendly)
# ============================================================
MODEL_ORGANISM_VOCAB = [
    "Toxoplasma gondii", "Plasmodium", "Cryptosporidium", "Eimeria",
    "Leishmania", "Trypanosoma", "Schistosoma", "Giardia",
    "Mus musculus", "Rattus norvegicus", "Homo sapiens",
    "cell line (HFF/HeLa/HEK293/etc)", "organoid", "in silico", "other",
]

RESULT_DIRECTION_VOCAB = ["positive", "negative", "mixed", "null"]
# null = no significant effect (distinct from negative = clear opposite evidence)

METHOD_TAGS_VOCAB = [
    # Genome perturbation
    "CRISPR-Cas9", "CRISPR-screen", "RNAi", "AID", "DiCre", "Tet-on/off",
    "knockout", "knockdown",
    # Sequencing (bulk + single-cell)
    "RNA-seq", "scRNA-seq", "ChIP-seq", "ATAC-seq", "Ribo-seq", "CUT&RUN",
    "Bisulfite-seq", "MeRIP-Seq", "m6A-seq", "m5C-seq",
    # Protein-protein / RNA interaction
    "BioID/TurboID", "co-IP", "Y2H", "pull-down", "CLIP-seq",
    # Structural
    "X-ray crystallography", "cryo-EM", "AlphaFold",
    # Imaging
    "live-cell imaging", "super-resolution", "EM", "immunofluorescence",
    # Profiling
    "flow cytometry", "mass spec", "metabolomics", "lipidomics", "proteomics",
    # Basic molecular biology (surfaced as common gaps in real extraction)
    "qRT-PCR", "Western blot", "Northern blot", "ELISA",
    # In vivo / in vitro models
    "mouse infection", "organoid culture", "in vitro infection",
    # Computational / bioinformatics
    "computational modeling", "phylogenetics", "GWAS",
    "BLAST/BLASTP", "GO/KEGG enrichment", "differential expression analysis",
    # ML / CS (for non-bio papers using the same controlled vocab)
    "Transformer", "self-attention", "neural network", "diffusion model",
    "other",
]


# ============================================================
# Schema (dataclass mirror of paper_extractor + 3 new fields)
# ============================================================
@dataclass
class Metadata:
    title: str = ""
    authors: List[str] = field(default_factory=list)
    journal: str = ""
    year: str = ""
    doi: str = ""
    model_organism: str = ""  # NEW: controlled vocab


@dataclass
class ResearchPurpose:
    core_question: str = ""
    background_gap: str = ""
    significance: str = ""


@dataclass
class TechStep:
    goal: str = ""
    approach: str = ""
    key_technique: str = ""


@dataclass
class TechnicalRoute:
    main_strategy: str = ""
    key_steps: List[TechStep] = field(default_factory=list)
    notable_methods: List[str] = field(default_factory=list)
    method_tags: List[str] = field(default_factory=list)  # NEW: controlled vocab


@dataclass
class Finding:
    finding: str = ""
    evidence: str = ""
    figure_ref: str = ""
    robustness: str = ""  # 强/中/弱


@dataclass
class MainResults:
    primary_findings: List[Finding] = field(default_factory=list)
    secondary_findings: List[str] = field(default_factory=list)
    result_direction: str = ""  # NEW: positive/negative/mixed/null


@dataclass
class ActualNovelty:
    type: str = ""
    essence: str = ""
    honest_assessment: str = ""


@dataclass
class Innovations:
    claimed_novelty: str = ""
    actual_novelty: ActualNovelty = field(default_factory=ActualNovelty)


@dataclass
class Limitations:
    acknowledged: List[str] = field(default_factory=list)
    reviewer_perspective: List[str] = field(default_factory=list)


@dataclass
class RelatedWork:
    reference: str = ""
    key_difference: str = ""


@dataclass
class RelationToLiterature:
    builds_on: List[str] = field(default_factory=list)
    differs_from: List[RelatedWork] = field(default_factory=list)
    position_in_field: str = ""


@dataclass
class ExtractionResult:
    metadata: Metadata = field(default_factory=Metadata)
    research_purpose: ResearchPurpose = field(default_factory=ResearchPurpose)
    technical_route: TechnicalRoute = field(default_factory=TechnicalRoute)
    main_results: MainResults = field(default_factory=MainResults)
    innovations: Innovations = field(default_factory=Innovations)
    limitations: Limitations = field(default_factory=Limitations)
    relation_to_literature: RelationToLiterature = field(default_factory=RelationToLiterature)
    _missing: List[str] = field(default_factory=list)
    _raw_json: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractionResult":
        """Tolerant constructor — missing fields default to empty values."""
        result = cls()
        result._raw_json = json.dumps(data, ensure_ascii=False)

        if "metadata" in data:
            md = data["metadata"]
            result.metadata = Metadata(
                title=md.get("title", ""),
                authors=md.get("authors", []) or [],
                journal=md.get("journal", ""),
                year=str(md.get("year", "")),
                doi=md.get("doi", ""),
                model_organism=md.get("model_organism", ""),
            )

        if "research_purpose" in data:
            rp = data["research_purpose"]
            result.research_purpose = ResearchPurpose(
                core_question=rp.get("core_question", ""),
                background_gap=rp.get("background_gap", ""),
                significance=rp.get("significance", ""),
            )

        if "technical_route" in data:
            tr = data["technical_route"]
            result.technical_route = TechnicalRoute(
                main_strategy=tr.get("main_strategy", ""),
                key_steps=[TechStep(**s) for s in tr.get("key_steps", []) if isinstance(s, dict)],
                notable_methods=tr.get("notable_methods", []) or [],
                method_tags=tr.get("method_tags", []) or [],
            )

        if "main_results" in data:
            mr = data["main_results"]
            result.main_results = MainResults(
                primary_findings=[Finding(**f) for f in mr.get("primary_findings", []) if isinstance(f, dict)],
                secondary_findings=mr.get("secondary_findings", []) or [],
                result_direction=mr.get("result_direction", ""),
            )

        if "innovations" in data:
            inn = data["innovations"]
            an = inn.get("actual_novelty", {}) or {}
            result.innovations = Innovations(
                claimed_novelty=inn.get("claimed_novelty", ""),
                actual_novelty=ActualNovelty(
                    type=an.get("type", ""),
                    essence=an.get("essence", ""),
                    honest_assessment=an.get("honest_assessment", ""),
                ),
            )

        if "limitations" in data:
            lim = data["limitations"]
            result.limitations = Limitations(
                acknowledged=lim.get("acknowledged", []) or [],
                reviewer_perspective=lim.get("reviewer_perspective", []) or [],
            )

        if "relation_to_literature" in data:
            rl = data["relation_to_literature"]
            result.relation_to_literature = RelationToLiterature(
                builds_on=rl.get("builds_on", []) or [],
                differs_from=[RelatedWork(**d) for d in rl.get("differs_from", []) if isinstance(d, dict)],
                position_in_field=rl.get("position_in_field", ""),
            )

        result._missing = data.get("_missing", []) or []
        return result


# ============================================================
# Prompts — generic SYSTEM_PROMPT + vault `_DOMAIN.md` override
# ============================================================
GENERIC_DOMAIN_FALLBACK = """你的专长涵盖广泛的科研领域。根据论文实际主题灵活适配:
认真识别该篇论文所在的领域(分子生物学 / 临床医学 / 机器学习 / 物理 / 化学 等),
调用对应的领域常识与方法论标准评判。"""


SYSTEM_PROMPT_TEMPLATE = """你是一位严谨的科研文献分析者。你的专业训练让你:
- 不做表面叙述,关注实验设计严谨性(对照、重复数、统计检验)
- 评估结论与证据之间的逻辑距离
- 区分作者声称的创新 vs 真实的领域贡献
- 识别 reviewer 视角的潜在问题

【领域适配】
{domain_prompt}

输出语言: 中文(专业术语、基因名、株系名、方法名、化合物名保留英文原词,不翻译)
"""


def load_domain_prompt(vault_path: Optional[Path] = None) -> str:
    """Load domain-specific prompt from <vault>/_DOMAIN.md if it exists.

    File format:
        ---
        applies_to: [research-paper, paper-extract]
        ---
        # <user's domain knowledge in markdown>

    Returns the markdown body (frontmatter stripped). Falls back to
    GENERIC_DOMAIN_FALLBACK on any failure.
    """
    if vault_path is None:
        try:
            vault_path = VAULT_PATH
        except Exception:
            return GENERIC_DOMAIN_FALLBACK

    domain_file = Path(vault_path) / "_DOMAIN.md"
    if not domain_file.exists():
        return GENERIC_DOMAIN_FALLBACK

    try:
        text = domain_file.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[paper_extract] _DOMAIN.md read failed: {e}", file=sys.stderr)
        return GENERIC_DOMAIN_FALLBACK

    # Strip YAML frontmatter if present
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end >= 0:
            text = text[end + 4:]

    text = text.strip()
    return text or GENERIC_DOMAIN_FALLBACK


def build_system_prompt(vault_path: Optional[Path] = None) -> str:
    domain = load_domain_prompt(vault_path)
    return SYSTEM_PROMPT_TEMPLATE.format(domain_prompt=domain)


# ============================================================
# TASK_PROMPT — 6-module extraction with 4 new fields + vocabs
# ============================================================
TASK_PROMPT = """请从下面的论文文本中,按六模块结构化提取信息。

# 输出格式

严格输出 JSON(不要 markdown 代码块包裹,不要任何前后说明文字),结构如下:

```
{{
  "metadata": {{
    "title": "完整标题",
    "authors": ["第一作者", "通讯作者", "..."],
    "journal": "期刊名",
    "year": "发表年份",
    "doi": "DOI(若有)",
    "model_organism": "受控词表(见下),选最匹配的一个"
  }},

  "research_purpose": {{
    "core_question": "一句话核心科学问题(不超过30字,不要套话)",
    "background_gap": "2-3句说清此前研究缺什么、为什么这是个问题",
    "significance": "填补这个缺口对领域的意义"
  }},

  "technical_route": {{
    "main_strategy": "一句话总体策略",
    "key_steps": [
      {{
        "goal": "要证明什么子论点",
        "approach": "用什么方法",
        "key_technique": "关键技术(如 CRISPR screen / BioID / scRNA-seq)"
      }}
    ],
    "notable_methods": ["新颖或非常规的方法及用途(自由文本)"],
    "method_tags": ["受控词表(见下),从论文实际用到的方法中选 2-6 个"]
  }},

  "main_results": {{
    "primary_findings": [
      {{
        "finding": "核心发现(一句话)",
        "evidence": "支撑数据,必须含定量信息,如 'KO组感染率降低78%, p<0.001, n=6生物学重复'",
        "figure_ref": "对应图表,如 'Fig.2A-C' 或 'Table 1'",
        "robustness": "强/中/弱(基于重复数、对照设计、统计严谨性)"
      }}
    ],
    "secondary_findings": ["补充性或验证性发现"],
    "result_direction": "受控四选一: positive/negative/mixed/null(null=无显著效应; negative=明确反面证据)"
  }},

  "innovations": {{
    "claimed_novelty": "作者明确声称的创新",
    "actual_novelty": {{
      "type": "方法学创新 / 概念创新 / 数据创新 / 增量贡献(四选一)",
      "essence": "真正新的东西是什么(具体到分子/通路/方法)",
      "honest_assessment": "对照领域现状,这个新颖性的真实分量。诚实评判"
    }}
  }},

  "limitations": {{
    "acknowledged": ["作者明确承认的局限"],
    "reviewer_perspective": ["以同行审稿人视角识别出的额外问题"]
  }},

  "relation_to_literature": {{
    "builds_on": ["关键先驱工作 '第一作者+年份+一句话定位'"],
    "differs_from": [
      {{
        "reference": "最相关的1-2篇工作(作者+年份)",
        "key_difference": "与本文的关键差异"
      }}
    ],
    "position_in_field": "开创 / 跟进 / 修正 / 整合"
  }},

  "_missing": ["原文未提供的字段路径,如 ['research_purpose.significance']"]
}}
```

# 受控词表(必须严格使用)

## model_organism (单选)
{model_organism_vocab}
若实际不在表内,用 "other" 并在 _missing 末尾追加一行说明。

## method_tags (多选,2-6个)
{method_tags_vocab}
原文实际涉及哪些方法就选哪些;不在表内的归 "other"。

## result_direction (单选)

定义:
- positive: 几乎所有 primary_findings 的 robustness 都是"强",没有矛盾结果
- mixed:    出现下列任一情况:
            * 至少 1 条 primary_findings 的 robustness 是"弱"
            * 作者承认 ≥2 条 limitations 且属于核心假设的反例
            * 不同实验条件/模型下出现矛盾结果(如体外 OK 但体内 fail,或某一突变体反向)
- negative: 主要假设被明确反驳/与作者预期相反
- null:     未检测到显著效应(实验做了但 p>0.05 或 effect size 接近 0)

**校准提示**: 不要默认 positive。高影响因子期刊的论文实际上 ~30% 应该是 mixed
而不是 positive,因为顶刊也常含 caveats。如果你纠结 positive 还是 mixed,
看一眼 primary_findings 的 robustness 分布:有"弱"或"中"就倾向 mixed。

# 强制约束

1. **不允许编造**:所有定量数据、figure_ref、引用的先驱工作必须能在原文找到。原文没有就置空字符串 "" 并把字段路径加入 `_missing`。
2. **强制定量化**:primary_findings.evidence 必须含数字/统计量/效应大小。
3. **拒绝套话**:禁止"本研究旨在揭示/具有重要意义/为后续研究提供基础"。
4. **创新性判断要诚实**:不因期刊影响因子高就拔高,不因方向冷门就贬低。
5. **reviewer_perspective 至少 1-2 条**。
6. **输出纯 JSON**:不要 markdown 代码块标记,第一个字符 `{{`,最后一个字符 `}}`。
7. **元数据来源**:metadata 通常位于 `<FRONT_MATTER>` 区块(首页信息),优先从那里提取;缺失再从 `<ABSTRACT>` 等处补全。

# 论文文本

"""


def build_task_prompt(paper_context: str) -> str:
    """Fill controlled vocab + concat the paper context."""
    return TASK_PROMPT.format(
        model_organism_vocab="\n".join(f"- {v}" for v in MODEL_ORGANISM_VOCAB),
        method_tags_vocab="\n".join(f"- {v}" for v in METHOD_TAGS_VOCAB),
    ) + paper_context


# ============================================================
# JSON extraction (verbatim from paper_extractor/core/extractor.py)
# ============================================================
def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Pull JSON from LLM output. Tolerant of markdown code fences + leading prose."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text.strip(), flags=re.MULTILINE)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        candidate = text[first:last + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


# ============================================================
# Main entry point
# ============================================================
def extract(
    paper_text: str,
    *,
    vault_path: Optional[Path] = None,
    max_tokens: int = 8000,
) -> ExtractionResult:
    """Extract 6-module structured info from paper text using DeepSeek.

    Args:
        paper_text: full paper text or abstract (already parsed from PDF / fetched
                    from PubMed). Caller is responsible for sectioning markers
                    (<FRONT_MATTER>, <ABSTRACT>, etc.) if relevant.
        vault_path: override VAULT_PATH for domain prompt loading. Defaults to
                    config.VAULT_PATH so _DOMAIN.md is picked up automatically.
        max_tokens: DeepSeek max_tokens. Default 8000 — lower truncates the JSON
                    on long Chinese outputs (paper_extractor empirical finding).

    Returns:
        ExtractionResult with all 7 sections + 4 new fields filled by the model.
        On JSON parse failure, returns a stub with _missing=["JSON_PARSE_FAILED"]
        and _raw_json holding the raw model output for debugging.
    """
    system_prompt = build_system_prompt(vault_path)
    user_prompt = build_task_prompt(paper_text)

    # Re-encode the prompt into a single string for deepseek.call()
    # (deepseek.call uses {role: user} only; system prompt is folded into the
    #  user message so the schema-strict output is preserved.)
    combined_prompt = f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}"

    response = deepseek.call(combined_prompt, max_tokens=max_tokens)
    raw_output = response["text"]

    parsed = _extract_json(raw_output)
    if parsed is None:
        result = ExtractionResult()
        result._raw_json = raw_output
        result._missing = ["JSON_PARSE_FAILED"]
        return result

    return ExtractionResult.from_dict(parsed)
