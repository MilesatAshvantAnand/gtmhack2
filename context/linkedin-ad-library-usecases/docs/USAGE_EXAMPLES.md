> **⚠️ LEGACY / SUPERSEDED — historical reference only**
>
> This document describes the **PAUSED Streamlit chat agent** (`src/agent/`, `src/tools/`, `src/ui/`, `app.py`). It is kept for historical reference only and is **not** an accurate description of current API behavior.
>
> **For current, authoritative API behavior, use [`docs/api-knowledge-base/`](api-knowledge-base/)** — the fixture-backed audit. It supersedes any API claim made in this file.
>
> **Specific warning:** Any statement here that the `countries` or `ad_type`/`adType` parameters work is **WRONG**. The LinkedIn Ad Library API rejects **both** with HTTP 400. Do country and ad-type filtering **client-side** after fetching. See [`docs/api-knowledge-base/constraints.md`](api-knowledge-base/constraints.md) §1–2.
>
> **Repo direction:** the project is now a foundation knowledge base plus shareable skills — see [`CLAUDE.md`](../CLAUDE.md) and [`docs/architecture.md`](architecture.md). This chat agent is not part of that direction.

---

# Usage Examples

Real conversation examples showing how the LinkedIn Ad Library AI Assistant works.

---

## Beginner-Friendly Interactions

### Vague Request - Agent Asks for Clarification

```
User: Tell me about Userpilot

Agent: Happy to help! To give you the most useful info about Userpilot's
LinkedIn ads, I have a few questions:

**What time period?**
1. Last month (January 2026)
2. Last quarter (Q4 2025)
3. Last 6 months
4. All time
5. Custom dates - just tell me

**What would you like to know?**
1. **Ad volume** - how many ads they're running and what types (video, images, etc.)
2. **Estimated budget** - rough estimate of their spend (note: this is an estimate)
3. **Where they advertise** - which countries and regions
4. **Compare to competitor** - side-by-side with another company
5. **Everything** - full overview of all the above

Just pick the numbers (like "1 and 5") or describe what you need!
```

```
User: 1 and 5

Agent: Perfect! Analyzing Userpilot's LinkedIn ads for January 2026...

*fetches data*

**Userpilot - January 2026 Overview**

**Ad Volume:**
- 327 total ads

**Ad Types:**
- 285 Sponsored Status Updates (87%) - static image/text posts
- 32 Sponsored Videos (10%)
- 10 Sponsored Carousels (3%)

**Geographic Focus:**
- United States: 55%
- United Kingdom: 22%
- Germany: 8%
- Canada: 5%
- Other: 10%

**Estimated Monthly Spend:** $8,200 - $24,600
(Based on impression volumes and industry CPM benchmarks)

**Key Insight:** Userpilot relies heavily on static image ads (87%), which
is typical for B2B SaaS. Their strong US/UK focus suggests they're targeting
English-speaking enterprise markets.

Would you like me to:
- Compare this to a competitor?
- Show their targeting details?
- Look at a different time period?
```

---

## Handling Unavailable Data

### When User Asks About Keywords

```
User: What keywords is Userpilot targeting?

Agent: Good question! LinkedIn actually works differently from Google Ads -
there's no keyword bidding on LinkedIn.

Instead, LinkedIn advertisers target audiences based on:
- **Job titles** (like "Product Manager", "VP of Marketing")
- **Industries** (like "SaaS", "Technology")
- **Company size** (startup, enterprise, etc.)
- **Skills** listed on profiles
- **Seniority** (entry level, director, C-suite)

I can show you:
1. **Geographic targeting** - what regions Userpilot focuses on
2. **Language targeting** - what languages their ads are in
3. **Available audience data** - any segments we have info on

Would any of these help?
```

### When User Asks About CTR

```
User: What's Userpilot's click-through rate?

Agent: Unfortunately, click-through rates aren't available in LinkedIn's
Ad Library - they only make impression counts public, not clicks or engagement.

Here's what I CAN tell you:
1. **Impression volumes** - how many people saw their ads
2. **Ad counts** - how many ads they're running
3. **Estimated spend** - based on industry benchmarks
4. **Ad types** - what formats they use (video tends to get higher engagement)

Would any of these help with what you're trying to figure out?
```

---

## Competitive Analysis

### Comparing Two Companies

```
User: Compare Userpilot vs Pendo for January 2026

Agent: Let me fetch the latest data for both companies...

*fetches data for both*

**Userpilot vs Pendo - January 2026**

|                  | Userpilot | Pendo | Difference |
|------------------|-----------|-------|------------|
| Total Ads        | 327       | 163   | +164 (2x)  |
| Status Updates   | 285 (87%) | 142 (87%) | Similar mix |
| Video Ads        | 32 (10%)  | 15 (9%)   | Similar mix |
| Carousels        | 10 (3%)   | 6 (4%)    | Similar mix |
| Est. Spend/mo    | $8.2-24.6K | $4.1-12.3K | ~2x |

**Geographic Focus:**
- Userpilot: US (55%), UK (22%), DE (8%)
- Pendo: US (71%), UK (12%), DE (5%)

**Key Insights:**
1. Userpilot is outspending Pendo roughly 2:1 on LinkedIn
2. Both use similar ad format mix (mostly static images)
3. Userpilot has broader European presence
4. Pendo is more US-focused (71% vs 55%)

This suggests Userpilot is being more aggressive with LinkedIn advertising,
particularly in expanding to European markets.

Want me to dig deeper into anything specific?
```

---

## Growth Signal Detection

### Finding Companies Ramping Up Ads

```
User: Which companies are increasing their LinkedIn ad spend?

Agent: Let me check for growth signals...

*analyzes data*

**Companies Showing Growth Signals**

**Top Tier (Score 85+) - High Intent:**

1. **TechStartup AI** (Score: 95)
   - Signal: Explosive growth
   - Change: +145% ads (20 → 49)
   - Est. spend: $4,900 - $14,700/mo
   - Insight: Likely just raised funding or launching new product

2. **DataFlow Inc** (Score: 88)
   - Signal: New entrant
   - Change: First-time advertiser (35 ads)
   - Est. spend: $3,500 - $10,500/mo
   - Insight: Just started LinkedIn advertising

3. **SaaSMetrics** (Score: 82)
   - Signal: Strong growth
   - Change: +78% ads (18 → 32)
   - Est. spend: $3,200 - $9,600/mo

**Why This Matters:**
Companies ramping up LinkedIn ads are often:
- Growing and have budget
- Launching new products
- In "buying mode" for tools/services

Would you like details on any of these companies?
```

---

## Working with Cached Data

### Agent Mentions Cached Data

```
User: Show me Microsoft ads for January 2026

Agent: I have Microsoft data from about 45 minutes ago. Want me to:
1. **Use cached data** - instant, same results
2. **Fetch fresh data** - takes a moment, gets latest

Which would you prefer?
```

```
User: Cached is fine

Agent: Using cached data from 45 minutes ago...

**Microsoft - January 2026**
- 892 total ads
- Primary format: Sponsored Status Updates (62%)
- Heavy video investment (28%)
- Global targeting with US focus (45%)

*Data from cache - fetched 45 minutes ago*
```

### User Requests Fresh Data

```
User: Get me fresh data for Google

Agent: Fetching fresh data from LinkedIn...

*makes API calls*

**Google - January 2026** (Fresh data)
- 1,247 total ads
- ...

Note: Fresh data fetched just now. This counts against the hourly API limit
(~100 requests/hour).
```

---

## Export and Analysis

### Exporting Data

```
User: Export Userpilot ads to CSV

Agent: I'll export Userpilot's ad data to CSV...

**Export Complete**
- File: `userpilot_ads_20260203.csv`
- Location: `data/exports/userpilot_ads_20260203.csv`
- Records: 327 ads

The CSV includes:
- Advertiser name
- Ad type
- Impressions (min/max)
- Geographic distribution
- First/last impression dates

You can open this in Excel or Google Sheets for further analysis.
```

---

## Tips for Best Results

1. **Be specific about time periods** - "January 2026" works better than "recently"
2. **Name companies clearly** - Use official names when possible
3. **Ask for what you need** - The agent will clarify if unsure
4. **Use cached data** - Saves API calls, same accuracy for recent queries
5. **Understand limitations** - CTR, actual spend, and keywords aren't available

---

---

## Handling Ambiguous Company Names

### When Multiple Companies Match

```
User: Show me Pendo ads

Agent: I found multiple companies matching "Pendo":

1. **Pendo.io** (ID: 5071271) - Product analytics platform
2. **Pendoah** (ID: 90798130) - Different company

Which one did you mean? Just say the name or number.
```

```
User: Pendo.io

Agent: Got it! Searching for Pendo.io specifically...

*Uses advertiser_id="5071271" for exact match*

**Pendo.io Ads**
- 163 total ads
- 142 Sponsored Status Updates (87%)
- ...
```

---

## Quick Reference

| If you want to... | Say something like... |
|-------------------|----------------------|
| Search for ads | "Show me Microsoft ads for January 2026" |
| Compare companies | "Compare Userpilot vs Pendo" |
| Estimate spend | "How much is Salesforce spending?" |
| Find growth | "Which companies are ramping up ads?" |
| Analyze formats | "What types of ads does HubSpot run?" |
| Check geography | "Where does Stripe target their ads?" |
| Export data | "Export Google ads to CSV" |
| Track company | "Start tracking ZenABM" |
| Clarify company | "Which Pendo do you mean?" |
