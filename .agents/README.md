# Project Customizations for Antigravity IDE

Customizations, rules, and skills configured for the **Mababanaba Water System** project in Antigravity IDE.

## Directory Structure

```text
.agents/
├── rules/
│   └── rule.md                     # Always-active project guidelines & constraints
└── skills/
    ├── anti-ai-slop/               # Filter against generic AI aesthetics and bad design defaults
    ├── component-reference-design/ # Accessible reference patterns (cards, layouts, tables, typography)
    ├── frontend-design/            # Distinctive, intentional aesthetic and visual identity guidance
    ├── ui-ux-pro-max/              # Searchable design database (styles, colors, font pairings, charts)
    ├── icons/                      # Non-emoji icon sourcing (Iconify, SVGs, Lucide)
    ├── chrome-devtools/            # Live browser DOM inspection and debugging
    ├── web-design-guidelines/      # Web interface guidelines and accessibility compliance checks
    └── handoff/                    # Structured session handoff documentation (HANDOFF.md)
```

## Active Skills & Workflow

1. **Design & Anti-Slop Filter**: Use `anti-ai-slop` + `component-reference-design` + `frontend-design` to craft clean, accessible, brand-specific UI without generic AI defaults.
2. **Iconography**: Use `icons` to pull valid SVGs and Iconify glyphs (enforcing the strict rule: no emoji as icons).
3. **Design Intelligence**: Run `.agents/skills/ui-ux-pro-max/scripts/search.py` to query design systems, color harmonies, and typography pairings.
4. **Validation & DevTools**: Use `chrome-devtools` and `web-design-guidelines` for DOM verification and accessibility audits.
