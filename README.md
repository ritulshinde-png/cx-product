# CX Product

A collaborative workspace for the product team — PRDs, data exploration, system architecture, and design specs, all version-controlled and organized.

---

## 📁 Repository Structure

```
cx-product/
├── requirements/      # Product feature work (PRD, exploration, strategy)
├── uat/               # Testing, bugs, sign-off during dev cycle
├── intelligence/      # Reusable data knowledge base
├── designs/           # UI/UX design specs
├── systems/           # Technical architecture docs (HLD, LLD, APIs)
└── README.md
```

### `requirements/`
Everything related to a product or feature lives here — PRDs, data exploration, analytics, and strategy docs. Organized by product area.

```
requirements/
└── search/
    ├── auto-suggest-v1.md            # PRD
    ├── auto-suggest-exploration.md   # Data exploration
    └── auto-suggest-strategy.md      # Strategy & decisions
```

### `uat/`
Dev-cycle testing — test scenarios, bug lists, QA checklists, and sign-off tracking. Organized by product area, mirroring `requirements/`.

```
uat/
└── search/
    └── auto-suggest-uat.md     # Test cases, bugs found, sign-off
```

### `intelligence/`
Shared, reusable data knowledge that isn't tied to a single product. Think of it as the team's data library.

```
intelligence/
├── schemas/     # Table & schema documentation
├── queries/     # Base SQL queries, reusable templates
├── metrics/     # Metric definitions & calculation logic
```

### `designs/`
UI/UX specs, wireframes, interaction flows, and visual design references.

### `systems/`
Technical architecture for the product team — HLDs, LLDs, API references, and debugging guides.

```
systems/
├── search/
│   ├── HLD-search-service.md
│   └── API-search-endpoints.md
└── cart/
    └── LLD-cart-flow.md
```

---

## 🌿 Branching Convention

### Branch Naming

**Format:** `<folder>/<product-area>-<feature>`

The branch prefix mirrors the top-level folder where the primary work lives.

| Branch | When to use | Example |
|--------|-------------|-----------|
| `requirements/<area>-<feature>` | Working on a product feature (PRD, exploration, strategy) | `requirements/search-auto-suggest` |
| `uat/<area>-<feature>` | UAT testing, bug tracking during dev cycle | `uat/search-auto-suggest` |
| `intelligence/<topic>` | Adding shared queries, schemas, or metric definitions | `intelligence/clickhouse-base-queries` |
| `designs/<area>-<feature>` | Adding design specs or wireframes | `designs/search-results-page` |
| `systems/<area>-<topic>` | Documenting architecture or APIs | `systems/search-hld` |

---

## 📄 File Naming Convention

**Format:** `AREA-Topic-Description.md`

Use kebab-case for filenames. Prefix with a category when helpful.

| Type | Example |
|------|---------|
| PRD | `auto-suggest-v1.md` |
| Exploration | `auto-suggest-exploration.md` |
| Strategy | `auto-suggest-strategy.md` |
| UAT | `auto-suggest-uat.md` |
| HLD | `HLD-search-service.md` |
| LLD | `LLD-cart-flow.md` |
| API Reference | `API-search-endpoints.md` |
| Query | `base-search-impressions.sql` |
| Schema | `clickhouse-search-tables.md` |

---

## 🚀 Getting Started

```bash
# Clone the repo
git clone https://github.com/xtmx7/cx-product.git
cd cx-product

# Create a feature branch
git checkout -b requirements/search-auto-suggest

# Make your changes, then commit & push
git add .
git commit -m "Add PRD for search auto-suggest v1"
git push -u origin requirements/search-auto-suggest
```

---

## 🤝 Contributing

1. Pick the right folder for your work
2. Follow the naming conventions above
3. Create a branch, push your changes, and open a PR
4. Tag relevant team members for review
