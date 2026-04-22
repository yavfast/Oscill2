# Plan: Auto Adjustment (PL_AAJ)

> **ID:** PL_AAJ
> **Status:** completed
> **Implements:** SP_AAJ
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Technology Decisions

- Pure Python, no external deps
- Recursive algorithms (bounded by step list length) rather than iterative for clarity

## Implementation Phases

- [DONE] V/div step navigation (find_next_vdiv/tdiv)
- [DONE] V/div auto-adjustment with fill factor check
- [DONE] T/div auto-adjustment with segment count check
- [DONE] V offset centering (single shot)
- [DONE] Trigger level to mean
- [DONE] Multi-type orchestrator with canonical ordering

## Backlog

- Fix t_step_ms bug in auto_adjust_t_div (Issue #1 in issues.md)
- Add frame refresh after each V/div change (currently uses stale frame from before the change)
- Consider adding a "no signal" explicit detection path instead of returning False silently
- V/div and T/div step lists are duplicated in JS (Issue #3) — expose via API
