---
name: research-pilot
title: 拾知 (Research Pilot)
description: "Poll local capture files from browser extension, analyze webpage content against user-defined projects/goals, store structured per-project capture data. When data is sufficient, generate deep synthesis reports aligned with project goals. Supports configurable data paths and multiple storage backends. Supports manual trigger and cron auto-polling every 5 minutes."
when_to_use: "When user says 'check captures', 'process research', 'analyze captures', '开启研究助手', '关闭研究助手', or when new webpage captures are detected in ~/.ra/captures/. Also triggers on project management commands like creating projects, adding subgoals, reviewing project findings, generating reports, or building knowledge base from captured content."
---

# 拾知 (Research Pilot)

## Overview

This skill processes webpage captures saved by the RA-MCP-Server browser extension, orienting everything around **user-defined projects and goals**. Every analysis is contextual: the Agent reads the project's goal document first, then judges whether a captured page is relevant, and if so, generates **structured capture data** written specifically for that project's objective.

When enough capture data has been collected for a project, the user can ask the Agent to produce a **deep synthesis report** — an aggregated analysis that synthesizes all structured captures into insights aligned with the project's goal.

All data paths are **configurable** via `~/.ra/config.json`. The Agent never assumes fixed paths.

**Architecture:**
```
Browser Extension → Server → {captures_dir}/ → Agent → Analysis → Structured Data
                                    ↓                                      ↓
                            {processed_dir}/{project}/goal.md        Deep Report
                            {processed_dir}/{project}/captures/    {processed_dir}/{project}/reports/
                            {db_path} (optional SQLite)
```

- **Server** (`server.py`): HTTP server on port 8765, receives captures from browser extension, saves as JSON files to `captures_dir`. Already deployed and verified working.
- **Receiver Script** (`scripts/ra-agent-receiver-diag.py`): Handles `ra://` protocol URLs from browser, decodes data, saves captures. Diagnosis version with GUI feedback.
- **This Skill**: Agent reads captures, reads active project goals, matches captures to projects/subgoals, generates structured capture data, and optionally produces deep synthesis reports.
- **Cron Auto-polling**: Optional. Runs Mode 1 workflow every 5 minutes via system cron.

## Runtime requirements

- Browser login required: no
- Sandbox required: yes (for file operations)
- MCP required: no
- Page script required: no
- User local folder required: yes (`captures_dir` and `processed_dir` must be accessible)
- **Python execution: required for SQLite mode**
  - The Agent must be able to run `python` or `python3` commands
  - This is needed for creating/managing the `.db` file and executing queries
  - If Python is unavailable, the skill falls back to `"json"` mode automatically
  - **Check at startup**: Before first SQLite operation, verify `python --version` or `python3 --version` responds

## Configuration

All paths are resolved relative to the **data directory** specified in `~/.ra/config.json`.

### Config File: `~/.ra/config.json`

```json
{
  "data_dir": "~/.ra",
  "captures_dir": "{data_dir}/captures",
  "processed_dir": "{data_dir}/processed",
  "prompts_dir": "{data_dir}/prompts",
  "db_path": "{data_dir}/data.db",
  "storage_backend": "sqlite",
  "polling": {
    "enabled": false,
    "interval_minutes": 5
  }
}
```

**Path resolution rules:**
- `~` expands to user's home directory (via `os.path.expanduser`)
- `{data_dir}` is a template variable referencing the `data_dir` value
- All other paths are resolved relative to `data_dir` unless absolute
- The Agent must read this config at startup and resolve all paths before any file operations

**Storage architecture:** `sqlite` primary + `json` mirror

The skill uses **SQLite as the primary storage** for all structured data, with JSON files serving as a human-readable mirror and fallback.

- **SQLite (primary)**: All queries, aggregations, and report generation operate against the SQLite database. Fast even with hundreds of captures. Single `.db` file, zero configuration.
- **JSON (mirror)**: Each structured capture is also written as a JSON file in `{processed_dir}/{project}/captures/`. Human-readable, portable, and serves as a backup if SQLite becomes unavailable.

**Why this architecture:**
- SQLite handles complex queries efficiently (`WHERE relevance_score > 0.8`, `GROUP BY`, `ORDER BY LIMIT`)
- JSON files allow manual inspection, editing, or migration without database tools
- If the Agent environment loses Python execution capability, the JSON files preserve all data

**Default config:**
```json
{
  "storage_backend": "sqlite",
  "db_path": "{data_dir}/data.db"
}
```

> The `storage_backend` field in config.json is reserved for future use (e.g., PostgreSQL, cloud storage). Current behavior is always `sqlite` + `json` mirror. If the Agent cannot execute Python, it falls back to pure JSON mode and informs the user.

> **Path portability note:** On Windows, `~/.ra` resolves to `C:\Users\<username>\.ra\`. The Agent must use `os.path.expanduser()` and never assume POSIX paths.

### Capture Directory

Resolved from config: `{captures_dir}`

Default (when `data_dir` is `~/.ra`):

| Platform | Path |
|----------|------|
| macOS / Linux | `~/.ra/captures/` |
| Windows | `%USERPROFILE%\.ra\captures\` |

### Processed Directory

Resolved from config: `{processed_dir}`

Contains projects, structured capture data, reports, and prompt templates.

```
{processed_dir}/
├── prompts/                     # User-editable prompt templates
│   └── report_generation.md
├── projects_index.json
├── 摸鱼/                        # Fallback for captures matching no project
│   └── captures/                # Simple summary captures (no project alignment)
├── {project_name}/
│   ├── goal.md
│   ├── subgoals/{sub}/goal.md
│   ├── captures/                # Structured capture data (project-aligned)
│   └── reports/                 # Deep synthesis reports
└── ...
```

### Prompt Directory

Resolved from config: `{prompts_dir}`

Default: `{processed_dir}/prompts/` or `{data_dir}/prompts/`

Contains user-editable prompt templates. The skill creates defaults on first use but never overwrites existing files.

## Data Storage Architecture

### Design Philosophy

The storage layer is designed around **Agent-native operations**. Agents excel at:
- Structured querying (SQL-like filtering)
- Batch reading with context window management
- Incremental updates

Therefore, the recommended architecture is:

**Primary: SQLite (`storage_backend: "sqlite"`)**
**Mirror: JSON files (`captures/` directory)**

This gives the best of both worlds:
- **SQLite**: Agent can query, filter, aggregate using SQL. Fast even with hundreds of captures. Single file, easy to backup.
- **JSON files**: Human-readable, portable, can be inspected or edited manually. Serve as a mirror/backup of the SQLite data.

### Why SQLite is Recommended

| Scenario | JSON files | SQLite |
|----------|-----------|--------|
| "Show me all captures for project X with relevance > 0.8" | Read every file, parse JSON, filter | Single SQL query |
| "How many captures per project this month?" | Iterate all files, group | `GROUP BY` query |
| "Top 10 most credible sources" | Read all, sort in memory | `ORDER BY credibility_score LIMIT 10` |
| 100+ captures in one project | Risk of context overflow | Query returns only needed rows |
| Report generation | Must read all files | Query aggregates first, then deep-read selected captures |

### How the Agent Operates SQLite

SQLite is **fully operable by the Agent** without any human setup:

1. **No installation needed**: Python's `sqlite3` is in the standard library. Any environment that can run `python` can use it.
2. **Agent creates everything**: The Agent runs Python code to create the `.db` file, execute `CREATE TABLE`, run `INSERT`/`SELECT`/`UPDATE`/`DELETE`.
3. **Typical Agent pattern**:
   ```python
   import sqlite3, json, os
   db_path = os.path.expanduser("~/.ra/data.db")
   conn = sqlite3.connect(db_path)
   conn.execute("CREATE TABLE IF NOT EXISTS capture_data (...)")
   conn.execute("INSERT INTO capture_data (...) VALUES (...)", (...))
   conn.commit()
   rows = conn.execute("SELECT * FROM capture_data WHERE project_id = ?", (project_id,)).fetchall()
   ```
4. **Agent writes and runs scripts**: The Agent can either use inline `python -c "..."` commands or write a `.py` script to disk and execute it. Both approaches work identically with sqlite3.
5. **The `.db` file is just a file**: It lives at `{db_path}` (configurable). It can be copied, moved, deleted, or inspected with any SQLite viewer. No daemon, no port, no credentials.

**If the Agent cannot execute code** (rare, but possible in heavily restricted environments):
- Fall back to `"json"` mode
- The Agent still designs the SQLite schema and writes a setup script for the user to run manually
- All other skill features work identically in JSON mode

**Agent handling of large datasets:**

When a user asks for a report and the project has many captures, the Agent **must not** silently discard data. The correct flow is:

1. Query SQLite for an overview (counts, date ranges, relevance distribution)
2. Present this overview to the user
3. Ask: "This project has 127 captures. I can analyze all of them, or focus on a subset (e.g., last 30 days, top 30 by relevance, or a specific subgoal). How would you like to proceed?"
4. Respect the user's choice. If they say "分析全部", the Agent reads all captures (potentially in batches for very large sets).

This preserves user agency while being transparent about scale.

### SQLite Schema (Recommended)

```sql
-- Projects
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    goal TEXT,
    active BOOLEAN DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);

-- Subgoals
CREATE TABLE subgoals (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    name TEXT NOT NULL,
    goal TEXT,
    created_at TEXT,
    UNIQUE(project_id, name)
);

-- Raw captures (from browser extension)
CREATE TABLE raw_captures (
    id TEXT PRIMARY KEY,
    title TEXT,
    url TEXT,
    text TEXT,
    meta TEXT,          -- JSON
    structure TEXT,     -- JSON
    timestamp TEXT,
    saved_at TEXT,
    source TEXT
);

-- Structured capture data (project-specific analysis)
CREATE TABLE capture_data (
    id INTEGER PRIMARY KEY,
    capture_id TEXT REFERENCES raw_captures(id),
    project_id INTEGER REFERENCES projects(id),
    subgoal_id INTEGER REFERENCES subgoals(id),
    analyzed_at TEXT,
    relevance_score REAL,
    relevance_reasoning TEXT,
    credibility_score REAL,
    credibility_reasoning TEXT,
    credibility_source_type TEXT,
    credibility_source_notes TEXT,
    summary TEXT,
    key_findings TEXT,      -- JSON array
    implications TEXT,
    questions_raised TEXT,  -- JSON array
    confidence_qualifiers TEXT, -- JSON array
    entities TEXT,          -- JSON
    raw_json TEXT           -- Full JSON blob for portability
);

-- Deep reports
CREATE TABLE reports (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    scope TEXT,
    generated_at TEXT,
    content TEXT,           -- Markdown
    capture_count INTEGER,
    file_path TEXT          -- If also saved as .md file
);

-- Indexes for fast queries
CREATE INDEX idx_capture_data_project ON capture_data(project_id);
CREATE INDEX idx_capture_data_relevance ON capture_data(relevance_score);
CREATE INDEX idx_capture_data_credibility ON capture_data(credibility_score);
CREATE INDEX idx_capture_data_analyzed_at ON capture_data(analyzed_at);
CREATE INDEX idx_reports_project ON reports(project_id);
```

### JSON-Only Mode (`storage_backend: "json"`)

When SQLite is not available or preferred:

- Each structured capture data is a separate JSON file: `{processed_dir}/{project}/captures/{capture_id}.json`
- Each report is a separate Markdown file: `{processed_dir}/{project}/reports/{timestamp}_{scope}.md`
- `projects_index.json` serves as the project registry

**Agent strategy for large JSON collections:**

Even in JSON mode, the Agent should optimize reads:

1. **Metadata scan**: Read only the `relevance.score`, `credibility.score`, and `analyzed_at` from each file (these are always at the top level). This is a lightweight operation.
2. **Sort and filter**: Sort by relevance descending. Filter by date if requested.
3. **Deep read**: Only read the full `targeted_analysis` for captures that will be included in the report.
4. **Batching**: If the user wants all captures and there are many, process in batches (e.g., 30 at a time) and synthesize incrementally.

### Prompt Templates (Externalized)

Report generation prompts live outside the skill package so users can customize them without losing changes on skill updates.

**Default location:** `{prompts_dir}/report_generation.md`

**Prompt file lifecycle:**
1. On first report generation, if the prompt file does not exist, the Agent creates it using the **default prompt template** (see below).
2. The Agent reads this file for every report generation.
3. Users may edit it freely. The skill will never overwrite an existing prompt file unless explicitly requested.

**Default prompt template** (written to `{prompts_dir}/report_generation.md` on first use):

```markdown
# Deep Report Generation Prompt

你是一位擅长将数据转化为人类可读叙述的研究分析师。你的任务是把结构化捕获数据合成一篇**短论文式报告**，像人类专家写给另一位人类读者那样——有观点、有节奏、有重点，而不是数据罗列。

## 写作原则

1. **短论文风格**：500-2000字，像一篇公众号深度文章或知乎回答，不是学术长文
2. **叙述性文字为主**：用段落讲故事、论证观点，避免过多项目符号和列表
3. **数据是配角，观点是主角**：不要把每个capture都写一遍。只选取最核心的2-4个发现深入展开，其余数据作为背景支撑
4. **有趣、有温度**：可以适当加入类比、场景化描述，让读者觉得"这是人写的"
5. **链接即来源**：提到任何事实时，用 Markdown 链接 `[描述](URL)` 指向原始来源
6. **关键原文展示**：在结构化数据中如果有 `key_quotes`，选择1-3条最有力的原文直接引用，用引用格式展示

## 输入

1. **Project Goal** (from goal.md): 项目的目标、关注点、忽略项
2. **Structured Capture Data**: 每个capture包含：
   - capture metadata (title, url)
   - relevance / credibility scores
   - targeted_analysis (summary, key_findings, implications, key_quotes)
   - entities

## 输出格式

```markdown
# {Project Name} - 调研短报
**生成时间：** {timestamp}  
**数据范围：** {N} 条来源，{date_start} 至 {date_end}

## 核心发现

1-2段高度概括。像文章导语，回答"这篇报告最值得你知道的是什么"。

## 正文：有重点的叙述

用2-4个小节深入展开。每个小节围绕一个核心观点，用叙述性段落论证，必要时引用关键数据和原文。

**写作要点：**
- 每个小节是一个完整的"小论点"，有开头（观点）、中间（证据+分析）、结尾（小结）
- 引用数据时自然融入句子，不要堆砌数字
- 如果有 `key_quotes`，选择最有力的一条，用引用格式展示：
  > "原文内容"  
  > —— 来自 [来源标题](URL)
- 对于低置信度来源的声明，用"据称""有用户反馈"等弱化表述

## 值得关注的信号

1-2段。有哪些矛盾、风险、或尚未验证的说法？这部分可以简短，但要有。

## 下一步建议

2-3条具体、可执行的建议。不要泛泛而谈。

## 来源速览
| 来源 | 相关度 | 置信度 | 链接 |
|------|--------|--------|------|
| ... | ... | ... | ... |
```

## 规则
- 不编造 structured data 中没有的事实
- 不把所有 captures 都写进去，只选最相关的深入展开
- 低置信度 source 的声明用弱化表述（"有用户称""某匿名回答提到"）
- 报告要有"人味"，避免机器感的数据罗列
```

## Workflow

### Initialization (First Run)

Before any project or capture processing, the Agent performs environment checks:

**Step 1: Read config**
- Read `~/.ra/config.json` (create with defaults if missing)
- Resolve all paths (`data_dir`, `captures_dir`, `processed_dir`, `db_path`)

**Step 2: Check Python execution capability**
- Run `python --version` or `python3 --version`
- If succeeds → use SQLite + JSON mirror mode
- If fails → switch to pure JSON mode, inform user: "Python 不可用，已切换到 JSON 模式。所有数据将以 JSON 文件形式存储。"
- Record capability in memory for the session (do not re-check on every operation)

**Step 3: Initialize storage**
- Create directory structure at resolved paths
- If SQLite mode: create `.db` file and run `CREATE TABLE IF NOT EXISTS` for all tables
- JSON files are created on-demand during capture processing

### Mode 0: Project Management

Projects must be created **before** captures can be analyzed against them. The user may also update goals or create subgoals at any time.

**Create a project:**
```
User: "新建项目：互联网大厂动向追踪，目标是追踪头部公司产品发布和战略调整"
```
Agent actions:
1. Read `config.json` to resolve `processed_dir`
2. Create folder `{processed_dir}/互联网大厂动向追踪/`
3. Create `captures/` and `reports/` subfolders
4. Write `goal.md` based on user description + Agent refinement
5. Add entry to `{processed_dir}/projects_index.json`
6. If using SQLite, insert into `projects` table

**Add a subgoal:**
```
User: "给项目 互联网大厂动向追踪 添加子目标：美团业务线，重点关注外卖和无人机"
```
Agent actions:
1. Create folder `{processed_dir}/互联网大厂动向追踪/subgoals/美团业务线/`
2. Write `goal.md` for the subgoal
3. Update parent project's `goal.md` subgoals list
4. If using SQLite, insert into `subgoals` table

**Configure data paths:**
```
User: "把数据目录改到 D:\ResearchData"
```
Agent actions:
1. Update `config.json`: `"data_dir": "D:\\ResearchData"`
2. Create directory structure at new location
3. Inform user that existing data is not automatically migrated (provide migration guidance if requested)

### Mode 1: Capture Processing (Manual or Cron)

Triggered by user commands like:
- "检查捕获" / "check captures"
- "分析研究" / "analyze research"
- Cron job every 5 minutes (if enabled)

**Steps:**
1. Read `config.json`, resolve all paths
2. List all `research_*.json` and `capture_*.json` files in `{captures_dir}/`, sorted by modification time
3. Read `{processed_dir}/polling_state.json` to get already-processed IDs
4. Filter to unprocessed captures only
5. Read `{processed_dir}/projects_index.json` to get active projects
6. For each active project, read its `goal.md` (and all subgoal `goal.md`s)
7. For each unprocessed capture (batch up to 10 per run):
   a. Read the capture JSON
   b. **Project Matching Phase**: For each active project, judge relevance
   c. **Structured Data Generation Phase**:
      - If matched to ≥1 project: For each matched project, generate full structured capture data (project-aligned analysis)
      - If matched to 0 projects: Generate a **simple summary** and save to `{processed_dir}/摸鱼/captures/{capture_id}.json`
   d. **Write data** (always dual-write):
      - INSERT into `capture_data` table (SQLite primary, with `project_id = null` for 摸鱼 captures)
      - Also write to `{processed_dir}/{project}/captures/{capture_id}.json` (JSON mirror, or `{processed_dir}/摸鱼/captures/` for no-match)
   e. Add capture ID to polling state
8. Report summary to user

**Important rules:**
- One capture → N projects → N structured data files (project-aligned)
- One capture → 0 projects → 1 simple summary file (in 摸鱼 folder)
- 摸鱼 captures are still marked as "processed" to avoid re-analysis

### Mode 2: Cron Auto-Polling

When enabled, a system cron job runs the skill every 5 minutes.

**Enable:**
1. Create a cron entry: `*/5 * * * *` running the skill entrypoint
2. Set `config.json.polling.enabled = true`

**Disable:**
1. Remove the cron entry
2. Set `config.json.polling.enabled = false`

**Cron job behavior:**
1. Execute Mode 1 workflow automatically
2. If new captures found and matched, notify user with brief summary
3. If no new captures or no matches, stay silent
4. Update `last_poll_time` in polling state

### Mode 3: Query / Review Project Data

User asks about collected intelligence:
- "项目 互联网大厂动向追踪 最近有什么新发现？"
- "关于美团无人机的结构化数据有哪些？"

**Steps:**
1. Read `config.json`, resolve paths
2. Read the project's `goal.md`
3. Query structured data:
   - SQLite: `SELECT * FROM capture_data WHERE project_id = ? AND analyzed_at > ?`
   - JSON: Read files from `{project}/captures/`, filter by date
4. Synthesize and present findings

### Mode 4: Deep Report Generation

User asks for a synthesized report:
- "给项目 互联网大厂动向追踪 写一份报告"
- "基于项目 Skill白鼠鼠账号运营追踪 的数据，写一份运营分析"

**Steps:**
1. Read `config.json`, resolve paths
2. Read the project's `goal.md` (and subgoal `goal.md`s if specified)
3. Determine scope (time window, subgoal, or all)
4. **Query data** (do NOT silently truncate):
   - SQLite: `SELECT COUNT(*), MIN(analyzed_at), MAX(analyzed_at) FROM capture_data WHERE project_id = ? [AND subgoal_id = ?] [AND analyzed_at > ?]`
   - JSON: Count files in `{project}/captures/`
5. **If count is large (>50 or whatever the Agent deems its comfortable processing limit):**
   - Present overview: "该项目有 127 条结构化数据，时间跨度 2026-06-01 至 2026-08-11"
   - Ask user: "我可以分析全部数据，也可以聚焦某个范围。你希望怎么处理？"
   - Options: (a) 分析全部 (b) 最近 N 天 (c) Top N 条高相关度 (d) 特定子目标
   - Wait for user response before proceeding
6. Read `{prompts_dir}/report_generation.md` (create from default if missing)
7. Feed project goal + selected structured data + prompt template into LLM
8. Generate deep synthesis report in Markdown
9. Save to `{processed_dir}/{project}/reports/{timestamp}_{scope}.md`
10. If using SQLite, also INSERT into `reports` table
11. Report to user: report location, key highlights, caveats

## Structured Capture Data Schema

### Project-Aligned Captures

When a capture is matched to a project, generate full structured data:

```json
{
  "capture_id": "original_id",
  "capture_title": "Page Title",
  "capture_url": "https://example.com/page",
  "analyzed_at": "ISO timestamp",
  "target_project": "项目名称",
  "target_subgoal": "子目标名称（如有，否则 null）",
  "relevance": {
    "score": 0.85,
    "reasoning": "..."
  },
  "credibility": {
    "score": 0.75,
    "reasoning": "...",
    "source_type": "news",
    "source_notes": "..."
  },
  "targeted_analysis": {
    "summary": "...",
    "key_findings": ["..."],
    "implications": "...",
    "questions_raised": ["..."],
    "confidence_qualifiers": ["..."],
    "key_quotes": [
      {
        "quote": "原文中对该目标最有佐证价值的一句话或一段话",
        "source_url": "https://example.com/page",
        "context": "这句话在原文中的上下文/段落主题"
      }
    ]
  },
  "entities": {
    "people": [],
    "organizations": [],
    "products": [],
    "technologies": [],
    "urls": []
  }
}
```

### 摸鱼 Captures (No-Project Match)

When a capture matches **zero** active projects, it goes to the `{processed_dir}/摸鱼/captures/` folder. The structured data is simplified — no project alignment, just a normal summary.

```json
{
  "capture_id": "original_id",
  "capture_title": "Page Title",
  "capture_url": "https://example.com/page",
  "analyzed_at": "ISO timestamp",
  "target_project": null,
  "target_subgoal": null,
  "relevance": {
    "score": 0.0,
    "reasoning": "与当前所有项目目标均不相关"
  },
  "credibility": {
    "score": 0.0,
    "reasoning": "未做深度可信度评估",
    "source_type": "unknown",
    "source_notes": "摸鱼捕获，仅做概括摘要"
  },
  "targeted_analysis": {
    "summary": "网页内容的正常概括摘要，100-200字",
    "key_findings": [],
    "implications": null,
    "questions_raised": [],
    "confidence_qualifiers": [],
    "key_quotes": []
  },
  "entities": {
    "people": [],
    "organizations": [],
    "products": [],
    "technologies": [],
    "urls": []
  }
}
```

**Key differences from project-aligned captures:**
- `target_project` and `target_subgoal` are always `null`
- `relevance.score` is always `0.0`
- `credibility` is not deeply assessed — basic source type only
- `targeted_analysis` contains only a `summary` — no key_findings, implications, etc.
- No `key_quotes` (not worth extracting for unaligned content)

**Purpose:** The 摸鱼 folder preserves captures that might become relevant later (e.g., when new projects are created). Users can review it periodically or retroactively assign captures to new projects.

### Core Metrics

#### 1. Relevance (相关度) — `relevance.score` 0.0~1.0

| Score | Meaning | Example |
|-------|---------|---------|
| 0.9-1.0 | Directly on-target | 项目=产品调研，文章是该产品的深度技术拆解 |
| 0.7-0.89 | Strongly relevant | 项目=产品调研，文章是对比评测，深入分析了该产品 |
| 0.4-0.69 | Moderately relevant | 项目=产品调研，文章泛泛介绍10个同类产品 |
| 0.1-0.39 | Weakly relevant | 项目=产品调研，文章仅在列举时提到该产品 |
| 0.0 | Irrelevant | 与项目目标完全无关 |

#### 2. Credibility (置信度) — `credibility.score` 0.0~1.0

| Score | Typical Source | Nuance |
|-------|---------------|--------|
| 0.85-1.0 | Official website / whitepaper | Primary source |
| 0.65-0.84 | Reputable industry media | Check author background |
| 0.45-0.64 | Promotional content / KOL review | Marketing intent reduces score |
| 0.2-0.44 | Social media / anonymous posts | May reflect genuine sentiment |
| 0.0-0.19 | Unverifiable rumor | Discard |

**Key principle:** Credibility requires intelligent analysis of author, platform, originality, and promotional intent.

## Capability Routing

| Step | Tool | Purpose |
|------|------|---------|
| Read config | `e2b_read` | Resolve all paths |
| List capture files | `e2b_glob` | Find captures in `captures_dir` |
| Read capture JSON | `e2b_read` | Get raw capture content |
| Read project goals | `e2b_read` | Load `goal.md` |
| Analyze content | LLM | Match, assess, generate targeted analysis |
| Write structured data | `e2b_write` / SQL | Save per-project capture data |
| Query for reports | SQL / `e2b_read` | Aggregate data for synthesis |
| Read prompt template | `e2b_read` | Load report generation prompt |
| Generate deep report | LLM | Synthesize into Markdown |
| Write deep report | `e2b_write` | Save to `reports/` |
| Update polling state | `e2b_read` + `e2b_write` | Track processed IDs |

## Files in This Skill

| File | Purpose |
|------|---------|
| `SKILL.md` | Main skill instructions |
| `scripts/list_new.py` | Find unprocessed captures |
| `scripts/ra-agent-receiver-diag.py` | Browser protocol handler with GUI |

## Output Contract

### On successful capture processing with matches:

```
✅ 拾知: Processed N capture(s), matched M project-target(s)

📄 互联网大厂动向追踪 (3 matches)
   1. [相关度 0.85 / 置信度 0.75] "美团无人机配送商业化进展"
   2. [相关度 0.60 / 置信度 0.55] "10款低空经济产品盘点"
   3. [相关度 0.90 / 置信度 0.95] "美团浏览器数据智能处理工具官网"

📄 AI产品灵感 (1 match)
   1. [相关度 0.85 / 置信度 0.95] "美团浏览器数据智能处理工具官网"

💡 待关注问题：
   - 美团无人机单均成本数据尚未找到
```

### On deep report generation:

```
✅ 项目 有趣skill记录 调研短报已生成
   报告路径: {processed_dir}/有趣skill记录/reports/20260811_103000_full.md
   字数: 约 1,200 字
   核心发现: 3 个
   关键引用: 2 条原文
```

### On report generation with user choice:

```
📊 项目 互联网大厂动向追踪 数据概览
   总 captures: 127 条
   时间跨度: 2026-06-01 至 2026-08-11
   高相关度(>0.7): 43 条
   中高置信度(>0.6): 89 条

❓ 数据量较大，你希望如何处理？
   [1] 分析全部 127 条
   [2] 仅分析最近 30 天的数据
   [3] 仅分析相关度最高的 30 条
   [4] 指定子目标范围
```

### On all captures going to 摸鱼:

```
✅ 拾知: Processed N capture(s), no project matches.
   全部 N 条已存入 摸鱼 文件夹。
   Active projects: 互联网大厂动向追踪, AI产品灵感
   建议：Review 摸鱼 captures or create a new project if captures are relevant to a different objective.
```

## Failure Handling

| Scenario | Action |
|----------|--------|
| Config file missing | Create with defaults, inform user |
| `data_dir` path invalid | Alert user, suggest fixing config |
| No active projects | Prompt user to create a project |
| Project goal.md missing | Recreate from index, or flag broken |
| Too many captures for report | Ask user to choose scope, never silently truncate |
| Prompt template missing | Create from default, continue |
| All captures go to 摸鱼 | Inform user, suggest reviewing 摸鱼 folder or creating new project |
| Disk full / write error | Alert user, stop processing |

## Quick Reference Commands

| User Says | Skill Does |
|-----------|-----------|
| "检查捕获" / "check captures" | Run manual capture processing |
| "开启拾知" | Set up cron job (`*/5 * * * *`) |
| "关闭拾知" | Remove cron job |
| "新建项目 XXX" | Create project folder + goal.md + captures/ + reports/ |
| "给项目 XXX 添加子目标 YYY" | Create subgoal folder + goal.md |
| "给项目 XXX 写报告" | Generate deep synthesis report |
| "把数据目录改到 XXX" | Update config.json, create new structure |
| "列出所有项目" | Show all projects and status |
| "暂停项目 XXX" | Deactivate project |
| "清除状态" | Reset polling state |
