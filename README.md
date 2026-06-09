# Tableau → Power BI Migration Pipeline

Automated agentic pipeline that converts any Tableau workbook (`.twb`) into a complete Power BI project (`.pbip`) — including semantic model AND report visuals.

## Prerequisites

- **VS Code** with GitHub Copilot extension (agent mode enabled)
- **Power BI Desktop** (June 2024+) to open generated `.pbip` files
- **Python 3.x** (for `validate_pbip.py` validator)
- Data files placed in `Data/{WorkbookFolder}/` alongside the `.twb`

## Quick Start

1. Open this workspace in VS Code
2. Place your Tableau workbook + data files in `Data/{YourFolder}/`
3. Open Copilot Chat in **Agent mode**
4. Run the `tableau-analysis` agent (or type: *"Analyze the Tableau workbook and generate a Power BI semantic model"*)
5. The full pipeline runs automatically — no manual steps needed
6. Open the generated `.pbip` from `Output/{WorkbookName}/` in Power BI Desktop

## Pipeline Stages (14 total — all automatic)

| Stage | Agent | Output |
|-------|-------|--------|
| 1 | `tableau-analysis` | `.specify/memory/{WorkbookName}/tableau-analysis-output.md` |
| 2 | `migration-constitution` | Reads universal `.specify/memory/constitution.md` |
| 3 | (speckit scripts) | Feature branch + `specs/{NNN}-{name}/` |
| 4 | `speckit.specify` | `specs/{NNN}-{name}/spec.md` |
| 5 | `speckit.clarify` | Clarifications encoded into spec |
| 6 | `dax-measures` | `.specify/memory/{WorkbookName}/dax-measures-output.md` |
| 7 | `star-schema` | `.specify/memory/{WorkbookName}/star-schema-output.md` |
| 8 | `speckit.plan` | `specs/{NNN}-{name}/plan.md` |
| 9 | `speckit.tasks` | `specs/{NNN}-{name}/tasks.md` |
| 10 | `pbip-generator` | `Output/{WorkbookName}/*.SemanticModel/` |
| 11 | (validators) | TMDL + PBIP validation |
| 12 | `speckit.analyze` | Cross-artifact consistency check |
| 13 | `report-visual-migration` | `Output/{WorkbookName}/*.Report/` |
| 14 | (validators) | Final end-to-end validation |

## Workspace Structure

```
├── .github/
│   ├── agents/                  # 20 pipeline agent definitions (.agent.md)
│   ├── skills/                  # 6 agent skill references
│   ├── prompts/                 # Reusable prompt assets
│   ├── scripts/                 # Pipeline helper scripts
│   └── copilot-instructions.md  # Pipeline orchestration instructions
├── .specify/
│   ├── memory/
│   │   ├── constitution.md          # Universal model migration rules (shared)
│   │   ├── report-constitution.md   # Universal report visual rules (shared)
│   │   ├── SalesCustomerDashboards/ # Per-workbook artifacts (analysis, DAX, schema, visuals)
│   │   ├── NetflixAnalysis/
│   │   ├── LoanPortfolioAnalysis/
│   │   └── Q3DealerBuyingEvent/
│   ├── scripts/                 # speckit feature/branch scripts
│   ├── templates/               # spec / plan / tasks templates
│   ├── workflows/               # Pipeline workflow definitions
│   ├── integrations/            # Integration configs
│   └── feature.json             # Active feature path resolver
├── .vscode/                     # Workspace settings
├── Data/                        # INPUT — .twb + data files per workbook
│   ├── Sales and Customer/      # .twb + CSVs
│   ├── Netflix/                 # .twb + CSV
│   ├── Loan/                    # .twb + CSVs
│   └── Q3 Buyer/                # .twb + CSV
├── Output/                      # OUTPUT — generated .pbip (Report + SemanticModel)
│   ├── SalesCustomerDashboards/
│   ├── NetflixAnalysis/
│   ├── LoanPortfolioAnalysis/
│   └── Q3DealerBuyingEvent/
├── plugins/                     # Validation tools + supplementary skills
│   ├── pbip/                    # TMDL/PBIR validators + format skills
│   ├── reports/                 # Report design & visual skills
│   └── semantic-models/         # DAX, Power Query, naming, review skills
├── specs/                       # Feature specifications per workbook
│   ├── 001-sales-customer-pbi/
│   ├── 004-q3-dealer-buying-event-pbi/
│   ├── 005-loan-portfolio-pbi/
│   └── 006-netflix-pbi/
├── .gitignore
└── README.md
```

## Validation

After generation, validators run automatically. You can also run them manually:

```powershell
# TMDL structural syntax validator
& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\{WorkbookName}\{Name}.SemanticModel\definition"

# Cross-cutting PBIP project validator
python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\{WorkbookName}"
```

Exit codes: 0 = clean, 1 = warnings, 2 = errors.

## Post-Generation Quality Reviews (Optional)

Two supplementary skills provide manual review capabilities after the pipeline completes:

### Review Semantic Model

Audits the generated model against quality, performance, and best practice standards.

**How to invoke:** Ask Copilot:
```
Review the semantic model at Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/
```

**What it checks:**
- Bidirectional/circular relationships, orphaned tables
- High-cardinality columns, DateTime splitting, Auto Date/Time bloat
- DAX anti-patterns (table filtering in CALCULATE, missing DIVIDE, nested iterators)
- Star schema violations, missing date table configuration
- AI/Copilot readiness (duplicate names, missing descriptions)
- Measure hygiene (implicit measures, duplicates, missing display folders)

**Skill location:** `plugins/semantic-models/skills/review-semantic-model/SKILL.md`

### Review Report Design

Evaluates report layout, visual spacing, chart selection, and accessibility.

**How to invoke:** Ask Copilot:
```
Check report design for Output/NetflixAnalysis/NetflixAnalysis.Report/
```

**What it checks:**
- 3-30-300 rule (detail gradient: KPIs top-left → details bottom-right)
- Visual spacing and alignment (equal gaps mandatory)
- Chart type selection and visual vocabulary
- Color accessibility (colorblind-safe palettes)
- Page titles, font sizing, theme usage
- Visual count per page (max 12-15 for performance)
- Slicer count (max 3 per page — prefer filter pane)

**Skill location:** `plugins/reports/skills/pbi-report-design/SKILL.md`

## Other Useful Skills

| Skill | Location | Purpose |
|-------|----------|---------|
| DAX Best Practices | `plugins/semantic-models/skills/dax/SKILL.md` | DAX performance optimization |
| Power Query | `plugins/semantic-models/skills/power-query/SKILL.md` | M query patterns |
| Naming Conventions | `plugins/semantic-models/skills/standardize-naming-conventions/SKILL.md` | Naming audit |
| TMDL Syntax | `plugins/pbip/skills/tmdl/SKILL.md` | TMDL authoring rules |
| PBIR Format | `plugins/pbip/skills/pbir-format/SKILL.md` | Report JSON structure |
| Theme Extraction | `plugins/reports/skills/tableau-theme-extraction/SKILL.md` | Extract Tableau theme colors |

## Important Notes

- Generated PBIP uses **absolute file paths** in M queries — each user must regenerate or update paths for their machine
- The pipeline is fully generic — place any `.twb` + data files in `Data/` and run
- **Constitutions are universal** — `constitution.md` and `report-constitution.md` are shared rulebooks, never overwritten per workbook
- **Memory is workbook-scoped** — each workbook's design artifacts live in `.specify/memory/{WorkbookName}/`
- All agents are in `.github/agents/`, skills in `.github/skills/`


## Quick commands
- Analyze the {Tableau workbook name} tableau report and migrate using the pipeline make sure it follows all steps carefully.