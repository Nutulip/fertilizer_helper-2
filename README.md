<div align="center">

# 🌱 Fertilizer Helper
### Greenhouse Fertigation Decision Support System
### 温室水肥一体化决策支持系统

**A WUR-benchmarked nutrient solution calculator for protected horticulture**
**基于 WUR 标准的设施园艺营养液精算系统**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://fertilizer-helper.onrender.com/)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Nutulip/fertilizer_helper-2)

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-127%20passing-brightgreen)](#-testing--验证)
[![Crops](https://img.shields.io/badge/crop%20matrices-47-1E4D2B)](#-tab-2--crop--phenological-stage-作物与物候期)
[![Bilingual](https://img.shields.io/badge/UI-EN%20%2F%20中文-blue)](#)
[![Status](https://img.shields.io/badge/status-non--commercial%20research-orange)](#-licence--attribution--许可与署名)

</div>

---

## 🔗 Links / 快速链接

| | |
|---|---|
| **🌐 Live Demo / 在线演示** | **https://fertilizer-helper.onrender.com/** |
| **📦 Repository / 代码仓库** | https://github.com/Nutulip/fertilizer_helper-2 |
| **📘 API Docs / 接口文档** | https://fertilizer-helper.onrender.com/docs |

> ⏳ **Cold-start notice.** The demo runs on Render's free tier, which suspends
> the service after ~15 minutes of inactivity. **The first request may take up
> to ~50 seconds** while the container wakes. Subsequent requests are immediate.
> Please be patient on first load — the app is not broken.
>
> ⏳ **冷启动提示。** 演示站点部署于 Render 免费套餐，闲置约 15 分钟后会自动休眠。
> **首次访问可能需要等待约 50 秒**唤醒容器，之后响应即刻恢复正常。请耐心等待，
> 并非程序故障。

---

## 📖 Overview / 项目简介

**EN** — Fertilizer Helper is a decision-support tool for growers running
hydroponic, substrate and soil-grown crops under protection. It converts a raw
water analysis and a root-zone measurement into a complete fertigation
prescription: acid dosing, nutrient recipe, leaching strategy, and a 100×
concentrated A/B stock tank bill — with every threshold traceable to a
published page number.

**中文** — 本项目面向设施园艺（无土栽培、有机基质、土壤栽培）种植者，
将原水水质分析与根际测定数据，转换为完整的水肥处方：加酸中和、营养液配方、
排液冲洗策略，以及 100 倍浓缩 A/B 母液罐配肥单。所有阈值均可追溯至
公开文献的具体页码。

### Why it exists / 设计初衷

Commercial fertigation software is expensive and opaque. The underlying
agronomy, however, is **published and freely available**. This project makes
that public standard directly usable — transparent formulas, cited thresholds,
and a bilingual interface so the reasoning is legible to growers who do not
read Dutch or English agronomic literature.

商业水肥软件价格昂贵且算法不透明，但其背后的农艺学标准本身是**公开可得的**。
本项目将这一公开标准直接工程化：公式透明、阈值可溯源、界面中英双语，
使不熟悉外文农艺文献的种植者也能读懂计算依据。

---

## 🎓 Academic Benchmark & Baseline / 学术基准与依据

**EN** — The physical-chemical calculation engine and all target recipes
(*Streefcijfers*) are **strictly derived from publicly available academic
literature**, specifically the Wageningen University & Research (WUR)
greenhouse fertigation benchmark:

**中文** — 本系统的理化计算引擎与全部目标配方（*Streefcijfers*，荷兰语"目标值"）
**严格源自公开的学术文献**，具体为瓦赫宁根大学与研究中心（WUR）设施园艺
水肥基准手册：

> **Van der Lugt, G.**, H.T. Holwerda, K. Hora, M. Bugter, J. Hardeman &
> P. de Vries (2020).
> ***Nutrient Solutions for Greenhouse Crops***, Version 4, 98 pp.
> ISBN 9789464021844.
> Published by Eurofins Agro, Nouryon, SQM and Yara.
> Derived from the Dutch *Bemestingsadviesbasis Glastuinbouw* (WUR).

Implemented from **Version 4 (September 2020)** — the edition the engine was
built and validated against. The extraction tooling in `tools/` can regenerate
the crop library against a newer edition should one be released.

当前实现基于 **第 4 版（2020 年 9 月）**——即引擎构建与验证所依据的版本。
`tools/` 目录下的数据提取工具可在新版本发布后重新生成作物数据库。

### What is derived vs. what is practice / 数据来源分级

Every value carries a provenance tag, surfaced in the UI and in all exports:

系统中每一项数值均带有溯源标记，并在界面与导出文件中显示：

| Tag / 标记 | Meaning / 含义 |
|---|---|
| `SRC:WUR` | Verbatim from the manual, with page citation / 直接引自手册并标注页码 |
| `SRC:DERIVED` | Arithmetic consequence, validated against the manual's own worked examples / 由手册公式推导，并以手册算例验证 |
| `SRC:PRACTICE` | **Commercial greenhouse practice — no basis in the manual.** Operator-configurable; must be validated locally. / **商业温室实践经验，手册中并无依据。** 可由使用者调整，须结合当地条件验证。 |

> ⚠️ Leaching fraction, wash cycles, dry-back targets and the emergency pH/EC
> thresholds are `SRC:PRACTICE` throughout — the source manual contains no such
> material. They are included because growers need them, and flagged because
> they do not carry the manual's authority.
>
> ⚠️ 排液比、洗盐循环、基质回干目标及紧急 pH/EC 阈值**全部**属于
> `SRC:PRACTICE`——原手册并未涉及。收录是因为生产确有需要，标注是因为
> 它们不具备手册的权威性。

---

## ⚖️ IP & Compliance Framing / 知识产权与合规声明

**EN**

- This is an **independent, non-commercial domain-exploration tool** built by an
  industry professional for technical study and decision support.
- It uses **publicly available, openly published research data**. The source
  manual is distributed free of charge by its publishers for industry use.
- **No proprietary algorithm, dataset or trade secret** from any commercial
  fertigation vendor is used, reproduced or reverse-engineered.
- The source manual is **cited, not redistributed**. This repository contains
  no copy of the PDF. Numerical parameters are cited with page references as
  factual data, in the same manner as any technical citation.
- All calculation logic was independently implemented from the published
  formulas and validated against the manual's own worked examples.
- This project is **not affiliated with, endorsed by, or produced by** WUR,
  Eurofins Agro, Nouryon, SQM or Yara.

**中文**

- 本项目为行业从业者出于技术研究与决策支持目的构建的**独立、非商业性领域探索工具**。
- 所用数据均为**公开发表的研究资料**，原手册由出版方免费提供给行业使用。
- **未使用、复制或逆向任何商业水肥厂商的专有算法、数据集或商业秘密**。
- 对原手册采取**引用而非再分发**的方式，本仓库不包含该 PDF 文件。
  数值参数以标注页码的方式作为事实性数据引用，与常规技术引注做法一致。
- 全部计算逻辑均依据公开公式独立实现，并以手册自带算例验证。
- 本项目**与** WUR、Eurofins Agro、Nouryon、SQM、Yara **无任何隶属或背书关系**。

---

## 🏗️ System Architecture / 系统架构

### Dual-Driven Hybrid Workflow / 双驱混合架构

```
┌──────────────────────────────────────────────────────────────────┐
│  PRESENTATION  ·  index.html                                     │
│  Bilingual shell · 5 tab workspaces · live status cards          │
└────────────────────────────┬─────────────────────────────────────┘
                             │  typed JSON
┌────────────────────────────▼─────────────────────────────────────┐
│  ORCHESTRATOR  ·  main.py (FastAPI)                              │
│  Request models · pipeline sequencing · gate arbitration         │
└──────┬───────────────────────────────────────┬───────────────────┘
       │                                       │
┌──────▼─────────────────────────┐  ┌──────────▼───────────────────┐
│  ⚙️  HARD ENGINE  ·  engine.py │  │  💬  ADVISORY LAYER          │
│  Deterministic · zero I/O      │  │  Narrative only              │
│                                │  │                              │
│  · unit & oxide conversion     │  │  · plain-language rationale  │
│  · ion balance / EC            │  │  · ion antagonism reading    │
│  · reference-EC normalisation  │  │  · agronomic context         │
│  · 7-step recipe pipeline      │  │                              │
│  · fertiliser mass solver      │  │  INPUT : computed facts only │
│  · A/B split + Ksp separation  │  │  OUTPUT: prose only          │
│  · ALL safety gates            │  │  NEVER  : a number           │
└──────────────┬─────────────────┘  └──────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────────┐
│  REFERENCE DATA  ·  constants.py + crops_wur.json                │
│  atomic weights · 26 fertilisers · 47 crop × substrate matrices  │
└──────────────────────────────────────────────────────────────────┘
```

**The split is structural, not stylistic.**

- **`engine.py` is a pure function library** — no network, no I/O, no model
  calls. Every dose, threshold and gate is computed deterministically and is
  reproducible byte-for-byte.
- **The advisory layer receives an already-computed result** and may only
  append prose. There is no code path by which narrative can alter a dose.
- **Zero-hallucination guarantee:** numeric output is *computed, never
  generated*.

**这一分层是结构性的，而非风格性的。**

- **`engine.py` 为纯函数库**——无网络、无 I/O、不调用任何模型。所有投加量、
  阈值与闸门均为确定性计算，结果可逐字节复现。
- **建议层仅接收已完成计算的结果**，只能追加文字说明。不存在任何代码路径
  可使叙述内容改变投加量。
- **零幻觉保证：** 数值输出为*计算所得，绝非生成*。

### Safety gate precedence / 安全闸门优先级

Gates are evaluated in fixed precedence. The first `BLOCKING` gate
short-circuits the pipeline and suppresses recipe output entirely.

闸门按固定优先级判定，首个 `BLOCKING` 级闸门将中断流程并完全隐藏配方输出。

```
1. Emergency meltdown   pH < 5.2 or EC > 4.5 mS/cm   → BLOCKING
2. Precipitation risk   Ca with SO₄ / PO₄ in a tank  → BLOCKING (never overridable)
3. Acid infeasibility   H⁺ demand > anion headroom   → CRITICAL
4. Sodium ceiling       Na above crop limit          → CRITICAL
5. Wash trigger         ΔEC ≥ 2.0 mS/cm              → CRITICAL
6. Water quality, corrections, chelate advisories    → WARNING / INFO
```

---

## 🧩 Core Functional Modules / 五大核心功能模块

### 💧 Tab 1 — Base Water Quality & Acid Neutralization / 原水水质与加酸中和

Classifies the irrigation water, neutralises excess bicarbonate, and credits
the water's own nutrients against the recipe.

评估灌溉水质，中和多余碳酸氢盐，并将原水自带养分抵扣入配方。

- **Water quality grading** — 3-level classification on Na/Cl and EC
- **HCO₃⁻ buffer control** — neutralises to a **retained 0.50–0.75 mmol/L
  buffer**, holding irrigation pH at 5.5–6.0. Neutralising *all* bicarbonate
  drops pH below 5.
- **Anion headroom constraint** — every mole of H⁺ drags in a mole of acid
  anion (NO₃⁻ or H₂PO₄⁻) that counts against the recipe. Exceeding the headroom
  raises `G-ACID-INFEASIBLE` with ranked remedies.
- **Dual dosing basis** — reports both the **100× stock tank** volume and the
  **1× working solution** volume. Confusing the two is a 100-fold dosing error,
  so both are always shown with the basis named.
- **Iron exclusion** — base-water Fe is *structurally never credited*; it
  oxidises and precipitates at the emitter before reaching the root.

### 🌾 Tab 2 — Crop & Phenological Stage / 作物与物候期

Cascading three-tier selector over the full WUR Section B crop library.

对 WUR 手册 B 部分完整作物库的三级联动选择器。

```
Crop Category (作物大类) → Crop (具体作物) → Growth Stage (生长阶段)
```

| Category / 大类 | Crops |
|---|---|
| 🍅 Fruiting Vegetables / 果菜类 | Tomato, Cucumber, Sweet Pepper, Eggplant, Melon |
| 🍓 Soft Fruits / 浆果类 | Strawberry, Raspberry, Blueberry |
| 🥬 Leafy Vegetables / 叶菜类 | Lettuce, Herbs, Microgreens |
| 🌹 Cut Flowers / 切花类 | Rose, Chrysanthemum, Gerbera, Carnation, Alstroemeria, Zantedeschia |
| 🪴 Potted Plants / 盆栽植物 | Phalaenopsis, Anthurium, Poinsettia, Bedding / Flowering / Foliage Plants |

- **24 crops · 47 crop × substrate matrices**
- **Substrate is part of the lookup key, never an attribute.** Targets differ by
  an order of magnitude between media, because organic values come from the
  **1:1.5 volume water extract** and soil from the **1:2 extract**. Tomato
  root-zone K is 8.0 mmol/L on inert substrate but **2.8 on organic material** —
  same plant, different measurement basis.
- **Stackable crop steering** — growth stages combine, and their adjustment
  deltas sum.
- **High Water Supply is a standalone toggle**, not a stage. Supply above
  5 L/m²/day is an orthogonal *condition* that can coincide with any phase.

### 🔬 Tab 3 — Root Zone Measurement & Diagnostics / 根际测定与诊断

Nine-column comparison table modelled on the Eurofins *Optifeed* report layout.

采用 Eurofins *Optifeed* 报告版式的九列对照诊断表。

- **Reference-EC normalisation** — analytical findings and target values must be
  compared at the same EC:
  ```
  EC_reference = EC_target − 0.30
  EC_nutrients = EC_analysed − 0.10 × Na_analysed
  Nutrient_ref = Nutrient_analysed × EC_reference / EC_nutrients
  ```
- **Single-side charge balance** (mmol_c/L):
  ```
  Cations = [NH₄⁺] + [K⁺] + [Na⁺] + 2[Ca²⁺] + 2[Mg²⁺] + [H⁺]
  Anions  = [NO₃⁻] + [Cl⁻] + 2[SO₄²⁻] + [HCO₃⁻] + [H₂PO₄⁻]
  EC      = (Cations + Anions) / 20
  ```
  The **H⁺ term is not optional** — acid protons participate as cations.
- **Three-level correction ladder** — 25 % deviation → ∓10–15 %; 50 % → a
  further ∓15–25 %. Micronutrients step **+50 / +25 / 0 / −25 / −50 %**.
- **Emergency meltdown gate** — pH < 5.2 or EC > 4.5 mS/cm returns a
  **hardcoded bilingual flush instruction set**, suppresses all recipe output,
  and bypasses the advisory layer entirely.
- **Ion antagonism screening** — deterministic pattern matching (K⊣Ca/Mg,
  Na⊣cations, Ca⊣Mg, NH₄⊣Ca/K, metals⊣Fe, high pH⊣P/micros).

### 🚿 Tab 4 — Irrigation & Leaching Fraction / 灌溉与排液比

> ⚠️ `SRC:PRACTICE` throughout — no basis in the source manual.
> ⚠️ 本模块全部为实践经验，原手册无相关内容。

```
LF = (V_drain / V_irrigation) × 100 %
ΔEC = EC_drain − EC_dripper
```

- **Wash trigger** at ΔEC ≥ 2.0 mS/cm.
- **Extra irrigation solver** — plant uptake is the conserved quantity, *not*
  drain:
  ```
  ΔV_extra = V_irrigation × ( (1 − LF_current) / (1 − LF_target) − 1 )
  ```
- **Tiered wash target** — a fixed target is only a *raise* while the crop is
  under-leaching:

  | Case | Condition | Target LF | ΔV |
  |---|---|---|---|
  | **Standard** | LF < 30 % | 32.5 % | > 0 |
  | **Moderate** | 30 % ≤ LF < 40 % | min(50 %, LF + 10) | > 0 |
  | **Anomaly** | LF ≥ 40 % | — | **0, by diagnosis** |

- **EC gap wash anomaly detection** — an EC gap persisting while over 40 % of
  applied water already drains is **not** a leaching deficit. `G-WASH-ANOMALY`
  fires instead of the wash gate and directs the grower to investigate
  **substrate channeling / preferential flow**, EC over-calibration, or severe
  salt accumulation — and to switch to shorter, more frequent pulses rather
  than adding water.

### 🧪 Tab 5 — 100× A/B Stock Tank Dosing Calculator / 100 倍 A/B 母液罐精算

- **Ksp thermodynamic separation** — all calcium fertilisers are separated from
  phosphate and sulphate fertilisers:

  | Product | Ksp |
  |---|---|
  | CaSO₄·2H₂O (gypsum) | 3.14 × 10⁻⁵ |
  | Ca₃(PO₄)₂ | 2.07 × 10⁻³³ |

  At 100× concentration both are far past saturation, so the separation is
  **absolute**. `G-PRECIP-RISK` is `BLOCKING` and **cannot be overridden** — the
  failure mode is an unrecoverable tank of sludge and a blocked irrigation line.

- **Fixed allocation order** (deterministic, must not be reordered):
  ```
  H⁺ → Cl → Ca → NH₄ → P → Mg → S → K    (NO₃ closes last, via KNO₃)
  ```
  Every step decrements co-delivered ions — calcium nitrate carries 5 Ca, 1 NH₄
  and 11 NO₃ per mole.

- **Mass solver:**
  ```
  Macronutrient:  kg = mmol/L × MW_per_driving_ion × (CF/1000) × (V/1000)
                  at CF = 100, V = 1000 L  →  kg = mmol/L × MW × 0.1
  Micronutrient:   g = µmol/L × atomic_weight / product_fraction × 0.1
  ```
  ⚠️ `MW_per_driving_ion` is grams of product per mole of the **driving ion**.
  Calcium nitrate is 1080 g/mol but carries 5 Ca → divisor **216**. Using 1080
  over-doses fivefold.

- **Iron chelate matching** by root-zone pH (the chelate must survive where the
  root is, not where the dripper is):

  | Root-zone pH | Chelate |
  |---|---|
  | ≤ 6.0 | Fe-EDTA acceptable, Fe-DTPA preferred |
  | 6.0 – 6.5 | **Fe-DTPA** |
  | **> 6.5** | **Fe-EDDHA / Fe-HBED** strongly recommended |
  | Calcareous soil | Fe-EDDHA / Fe-HBED, high *ortho-ortho* |

  Prophylactic replacement of 25 % (inert substrate) or 10 % (NFT) pre-empts
  pH drift.

- **Tank pH limits** — Tank A 3.5–5.0, Tank B below 5.0. Chelates break down at
  pH ≤ 3.5, so tank-A acid is capped and the remainder placed in tank B.

---

## 🛠️ Tech Stack / 技术栈

| Layer / 层 | Technology | Rationale / 选型理由 |
|---|---|---|
| **Backend** | FastAPI (Python 3.10+) | Schema-first, auto-generated OpenAPI docs |
| **Server** | Uvicorn (ASGI) | Lightweight, production-capable |
| **Validation** | Pydantic v2 | Type parity between engine and API |
| **Engine** | Pure Python, standard library only | Zero dependencies → fully testable in isolation |
| **Frontend** | Vanilla HTML5 / CSS3 / JavaScript | No build step, single file, no framework lock-in |
| **Styling** | Tailwind CSS | Utility-first, responsive |
| **Reference data** | JSON, checksum-validated on load | Auditable diffs, no silent drift |
| **Deployment** | Render (Docker / Procfile / render.yaml) | Free tier, GitHub auto-deploy |

The engine layer (`constants.py`, `engine.py`) uses **only the Python standard
library**. FastAPI and Pydantic are required by the web layer alone — the
calculation core can be imported into any Python project as-is.

计算核心（`constants.py`、`engine.py`）**仅依赖 Python 标准库**。
FastAPI 与 Pydantic 仅为 Web 层所需，计算内核可直接导入任意 Python 项目使用。

---

## 🚀 Quick Start / 快速开始

### Prerequisites / 环境要求

- Python **3.10 or newer** (3.12 recommended / 推荐 3.12)
- `git`

### Local setup / 本地部署

```bash
# 1. Clone the repository / 克隆仓库
git clone https://github.com/Nutulip/fertilizer_helper-2.git
cd fertilizer_helper-2

# 2. Create and activate a virtual environment / 创建并激活虚拟环境
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# 3. Install dependencies / 安装依赖
pip install -r requirements.txt

# 4. Start the development server / 启动开发服务器
uvicorn main:app --reload
```

Then open **<http://127.0.0.1:8000>** in your browser.
随后在浏览器中打开 **<http://127.0.0.1:8000>**。

The backend serves the frontend itself — one process, one URL, no separate
static server and no CORS configuration to get wrong.

后端直接托管前端页面——单进程、单地址，无需额外静态服务器，也不必配置 CORS。

| URL | Purpose / 用途 |
|---|---|
| `http://127.0.0.1:8000/` | Web interface / 网页界面 |
| `http://127.0.0.1:8000/docs` | Interactive OpenAPI docs / 交互式接口文档 |
| `http://127.0.0.1:8000/health` | Health check / 健康检查 |

### Environment variables / 环境变量

| Variable | Default | Meaning / 说明 |
|---|---|---|
| `PORT` | `8000` | Bind port; injected by most cloud platforms / 绑定端口 |
| `HOST` | `127.0.0.1` | Bind address; use `0.0.0.0` in containers / 绑定地址 |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS allowlist / CORS 白名单 |

### Optional: vendor Tailwind / 可选：本地化 Tailwind

The frontend loads Tailwind from `vendor/tailwind.js` and falls back to the CDN
if absent. Vendoring removes the external dependency, which matters on networks
where the CDN is slow or unreachable.

前端优先加载 `vendor/tailwind.js`，缺失时回退至 CDN。本地化可消除外部依赖，
在 CDN 访问受限的网络环境下尤为重要。

```bash
mkdir -p vendor && curl -L https://cdn.tailwindcss.com -o vendor/tailwind.js
```

---

## 🧪 Testing / 验证

```bash
python main.py test
```

**127 tests**, covering unit conversion, ion balance, the recipe pipeline,
fertiliser allocation, tank separation, every safety gate, and the bilingual
output contract.

**127 项测试**，覆盖单位换算、离子平衡、配方流程、配肥分配、分罐隔离、
全部安全闸门及双语输出约定。

### Golden vectors / 黄金校验向量

The engine is validated against the source manual's **own worked examples** —
these are release gates, not smoke tests:

引擎以原手册**自带的算例**为准进行验证，属于发布门禁而非冒烟测试：

| Vector | Source | Assertion |
|---|---|---|
| **GV-1** | Table 3, p. 23 | Seven-step recipe pipeline reproduces every published cell |
| **GV-2** | Tomato A+B recipe, p. 53 | All 13 fertilisers and 8 ion-closure checks |
| **GV-3** | Optifeed report, p. 30 | Nitric acid volume within 5 % |

Crop-library transcription is validated by the tables' own redundancy —
`mmol/L × atomic weight` must reproduce the printed ppm column. Verified
against nine hand-transcribed matrices: **332 values, zero mismatches**.

作物库转录以表格自带的冗余校验：`mmol/L × 原子量` 必须还原印刷的 ppm 列。
以九份人工转录矩阵比对：**332 项数值，零差异**。

---

## 📂 Project Structure / 项目结构

```
fertilizer_helper-2/
│
├── main.py                  # FastAPI app · 25+ routes · full test suite
├── engine.py                # ⚙️ Deterministic calculation core (no I/O)
├── constants.py             # WUR reference data · fertiliser catalogue
├── crops_wur.json           # 24 crops × 47 substrate matrices (checksum-validated)
├── index.html               # Single-file bilingual frontend
│
├── design.md                # Technical design document
├── requirements.txt         # Pinned production dependencies
│
├── Dockerfile               # Container build (HF Spaces / Zeabur / Fly.io)
├── render.yaml              # Render blueprint
├── Procfile                 # Heroku-style process definition
├── runtime.txt              # Pinned Python version
│
├── docs/                    # Project briefs
│
├── tools/                   # Data pipeline (dev only, not runtime)
│   ├── extract2.py          #   PDF table extractor, self-calibrating
│   ├── build_library.py     #   Crop library generator
│   ├── build_exports.py     #   Data asset generator
│   └── build_docs.py        #   Specification doc generator
│
└── exports/                 # 📦 Standalone deliverables
    ├── data/                #   JSON / CSV datasets
    ├── docs/                #   Markdown specification manuals
    ├── modules/             #   Zero-dependency Python modules
    ├── excel/               #   Formatted .xlsx workbooks with charts
    └── generate_excel_reports.py
```

---

## 🌐 Deployment / 部署

Deployed on **Render** via `render.yaml`. Any platform that can run a Python
web service works — `Dockerfile` and `Procfile` are included for container and
Heroku-style hosts respectively.

通过 `render.yaml` 部署于 **Render**。任何可运行 Python Web 服务的平台均可使用，
仓库同时提供 `Dockerfile` 与 `Procfile` 以适配容器与 Heroku 式托管环境。

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

> **Region note.** The free tier permits one region. `frankfurt` is best for
> Europe; `singapore` gives noticeably better latency for East Asia. Mainland
> China accessibility of any overseas free-tier host is variable and cannot be
> guaranteed — a custom domain behind a China-accessible CDN is the reliable
> path.
>
> **区域提示。** 免费套餐仅支持单一区域。欧洲用户建议 `frankfurt`，
> 东亚用户选择 `singapore` 延迟更低。任何境外免费托管服务在中国大陆的
> 可访问性均不稳定且无法保证——如需稳定访问，建议自有域名配合
> 中国大陆可达的 CDN。

---

## ⚠️ Agronomic Disclaimer / 农艺免责声明

**EN**

> **This tool provides decision support only. It does not replace professional
> agronomic advice, laboratory analysis, or the judgement of a qualified crop
> consultant.**
>
> - Nutrient solutions must be validated against **local water quality, climate,
> substrate condition and cultivar**. Published target values are starting
> points, not prescriptions.
> - Values tagged `SRC:PRACTICE` — including all leaching-fraction, dry-back and
> emergency-threshold logic — have **no basis in the source manual** and must
> be verified locally before use.
> - **Concentrated acids and fertiliser stock solutions are hazardous.** Follow
> the manufacturer's safety data sheets and wear appropriate protective
> equipment.
> - **Never mix calcium fertilisers with phosphate or sulphate fertilisers in
> the same stock tank.**
> - The source manual itself states that the conditions of use and application
> of its formulae are beyond the authors' control, that no warranty is made as
> to the accuracy of any data contained therein, and that its partners
> disclaim any liability relating to their use. **The same applies here.**
> - The author accepts **no liability** for crop loss, yield reduction, product
> quality decline, equipment damage or environmental impact arising from use
> of this software. **Use at your own risk.**

**中文**

> **本工具仅提供决策支持，不能替代专业农艺指导、实验室分析或合格作物顾问的判断。**
>
> - 营养液配方必须结合**当地水质、气候、基质状况与品种特性**验证。
> 公开目标值是起点，而非处方。
> - 标注 `SRC:PRACTICE` 的数值——包括全部排液比、回干与紧急阈值逻辑——
> **在原手册中并无依据**，使用前须结合当地条件核验。
> - **浓酸与母液具有危险性。** 请遵循厂商安全数据表并佩戴适当防护装备。
> - **切勿将钙肥与磷酸盐或硫酸盐肥料置于同一母液罐中。**
> - 原手册亦声明：其公式的使用条件超出作者控制范围，不对数据准确性作任何保证，
> 并对因使用而产生的责任予以免除。**本项目同样适用此声明。**
> - 作者对因使用本软件而导致的作物损失、减产、品质下降、设备损坏或环境影响
> **不承担任何责任。使用风险自负。**

---

## 📜 Licence & Attribution / 许可与署名

**EN** — This is a non-commercial research and educational project. No formal
`LICENSE` file has been added yet; until one is, **all rights are reserved by
default** under standard copyright. If you wish to reuse this code, please open
an issue.

**中文** — 本项目为非商业性研究与教育项目。目前尚未添加正式 `LICENSE` 文件，
在此之前依据著作权法**默认保留所有权利**。如需复用代码，请提交 issue 联系作者。

### Attribution / 署名

Agronomic parameters are cited from **Van der Lugt, G. et al. (2020),
*Nutrient Solutions for Greenhouse Crops*, Version 4, ISBN 9789464021844**,
published by Eurofins Agro, Nouryon, SQM and Yara, and derived from the Dutch
*Bemestingsadviesbasis Glastuinbouw* (Wageningen University & Research).

Full credit for the underlying agronomic science belongs to those authors and
institutions. This repository is an independent software implementation and
claims no authorship over the science it implements.

底层农艺科学的全部功劳归属于上述作者与机构。本仓库仅为独立的软件实现，
不对其所实现的科学内容主张任何著作权。

---

<div align="center">

**Built by an industry professional for the protected-horticulture community.**
**由行业从业者为设施园艺从业者构建。**

Engine values are computed deterministically and are never generated by a language model.
引擎数值均为确定性计算结果，绝非语言模型生成。

[⬆ Back to top / 返回顶部](#-fertilizer-helper)

</div>
