# LinkedIn ABM Audit (ZenABM)

A Claude Cowork / Claude Code skill that **audits a company's live LinkedIn ads and ABM performance** from their
last 30 days of spend and hands back a branded, downloadable **"[Company] LinkedIn Ads & ABM Audit"** (HTML + PDF)
with a prioritized fix list.

It pulls real spend, CPC, CPM, CTR, ad count, format mix, deal influence, campaign trends and account engagement
through the [ZenABM](https://app.zenabm.com/) MCP, grades every ad format against ZenABM's 2026 B2B SaaS
benchmarks, and tells the user exactly what to fix.

> This is the **diagnostic** skill (trailing 30 days, fix-list). For a monthly stakeholder **report** on the last
> calendar month, use the companion **linkedin-abm-report** skill.

## What it produces

A branded audit with:

- **Scorecard** — spend, ads live, CPC, CPM, CTR, effective cost-per-LP-click, each vs benchmark.
- **Are you running the right number of ads?** — affordable healthy ad count vs actual, per-ad delivery health.
- **Where your budget goes** — spend share and ad count per format.
- **What's influencing your deals** — format → influenced deals/pipeline (HubSpot), or a connect prompt if no CRM.
- **Benchmark grade by format** — CTR, CPC, effective CTR/CPC-to-LP, CPM, each ✓/✗. Link-driving formats (Single
  Image, Carousel, Video) are graded on **effective CPC to landing-page click**, not raw CPC.
- **Reallocate your budget** — current vs recommended split, with dollar moves.
- **Campaign trends** — period-over-period efficiency verdict, best/worst, CTR spikes explained.
- **Ad insights** — best/worst ads, TLA effective CTR/spend, decaying ads.
- **Red flags / green flags** and a ranked **fix list**.

## Requirements

- Claude **Cowork** (or Claude Code) with the artifact + outputs tools.
- The **ZenABM MCP** connected and authorized: `https://app.zenabm.com/api/mcp`
  (free trial at https://app.zenabm.com/signup, then connect your LinkedIn ads account).
- Optional but recommended: connect HubSpot in ZenABM (https://app.zenabm.com/data/crm-sync) for the
  deal-influence section.

## Install

**Cowork (one click):** download `linkedin-abm-audit.skill` from this release, open it in Cowork, click **Save
skill**. Then run **`/linkedin-abm-audit`** or ask *"Audit my LinkedIn ads."*

**From source:** copy the `linkedin-abm-audit/` folder (SKILL.md + `references/` + `assets/`) into your
Cowork/Claude Code skills directory, then reload skills.

## What's in this bundle

```
linkedin-abm-audit/
  README.md                       this file
  SKILL.md                        the skill
  references/                     benchmarks, metrics, data-playbook, flags, onboarding
  assets/                         branded report template + ZenABM logos
linkedin-abm-audit.skill          one-click Cowork installer (zip of the folder above)
```

## Rebuild the installer

```bash
zip -r linkedin-abm-audit.skill linkedin-abm-audit
```

---

Built with ZenABM · https://zenabm.com · Benchmarks: https://zenabm.com/linkedin-abm-benchmarks-report
