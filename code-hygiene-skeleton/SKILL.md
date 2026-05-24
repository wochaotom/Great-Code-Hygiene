---
name: code-hygiene-skeleton
description: Minimal blank template for building a custom code hygiene skill from scratch. Use when the user wants an empty scaffold without Great Code Hygiene source packs, PASS-100 corpus, fixtures, training lessons, promoted doctrine, or inherited scoring rules.
---

# Code Hygiene Skeleton

## Purpose

Use this as a blank starting point for a custom code hygiene workflow. It is
intentionally small: no source corpus, no PASS-100 suite, no fixtures, no
training lessons, no promoted doctrine, and no default compounding loop.

Before evolving it, ask the user what kind of codebase, risk model, tooling, and
verification standard they want. Treat any new rule as candidate behavior until
it is tested on real examples.

## Starter Workflow

1. Read repo instructions, relevant code, tests, manifests, and local patterns.
2. Define the smallest useful scope.
3. For bugs, build or request a deterministic feedback loop before fixing.
4. Make the smallest behavior-correct change.
5. Verify with commands or explicit evidence.
6. Report what was checked, what was not checked, and what risk remains.

## Bootstrap Questions

- What failures should this skill prevent?
- Which languages, frameworks, or repo types should it target?
- Which checks count as enough evidence?
- Should it be review-only, implementation-capable, or both?
- Should it ever train itself, or should it stay function-only?

## Guardrail

Do not import Great Code Hygiene source packs, PASS-100 scoring, fixtures, or
training lessons unless the user explicitly asks to build a derivative training
skill.
