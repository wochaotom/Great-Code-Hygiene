# Source-Grounded Honing Protocol

Use this protocol when the user wants the skill to loop against authoritative documents.

## Honing Loop

1. Determine task domain from the code under review: general review, tests, security, config, API, frontend, observability, build/release, dependency, public package, safety-critical, or training-loop design.
2. Load `source-weights.json` and activate all `always` sources plus conditional sources matching the domain.
3. Read each activated source pack in `source-packs/` individually.
4. Review the code or candidate skill update against every checklist item in each activated pack.
5. Check `training-lessons.md` for existing lessons from prior scored target-dummy runs so the loop compounds without relearning the same miss.
6. Record a honing report with:
   - activated source IDs,
   - checklist items considered,
   - PASS-100 category scores,
   - evidence for deductions,
   - source-backed lessons,
   - candidate update decision.
7. Apply the candidate only if the promotion gates in `compound-loop.md` pass.
8. Repeat until the current phase threshold is reached or failures stop producing useful lessons.

## Enforcement Gate

For source-grounded honing, promotion requires a valid honing report:

```powershell
python scripts/validate_honing_report.py --report runs/honing-report.json
python scripts/promote_candidate.py --current . --candidate candidate-skill --score runs/score.json --honing-report runs/honing-report.json --require-honing-report --apply
```

The report must include activated sources, checklist results for every activated source, principles checked, PASS-100 score, a promotion decision, and source-backed lessons for promote decisions.

## Important Limits

- Do not download full source documents into the skill by default. Store copyright-safe distilled checklists with links to official documents.
- Browse live official sources only when refreshing the corpus, resolving a disputed interpretation, or checking whether a standard changed.
- Do not activate every conditional source for every run. That creates false pressure. Activate source packs by domain.
- For high-stakes security reviews, prefer live source verification and cite the exact authoritative page used.

## Report Template

```json
{
  "run_id": "phase-r2-honing-001",
  "run_type": "source-grounded",
  "target": "path or project summary",
  "activated_sources": ["google-eng-practices", "owasp-secure-coding"],
  "principles_checked": ["Preserve or improve code health", "Treat security as design"],
  "checklist_results": [
    {
      "source_id": "google-eng-practices",
      "checked": ["design", "functionality", "complexity", "tests"],
      "findings": ["No unrelated formatting churn found."],
      "deductions": []
    }
  ],
  "pass100_score": 0,
  "lessons": [],
  "promotion_decision": "promote | reject | needs-more-evidence"
}
```
