---
description: Generate a concrete implementation plan from an existing spec/design markdown file.
argument-hint: "<docs/superpowers/specs/...-design.md>"
---

# spec-plan

## Purpose

Generate an implementation plan from an existing spec/design document.

Use this skill when the user says:

- `/spec-plan`
- `spec-plan`
- `spec plan`
- `根据这个 spec 写 plan`
- `根据这个设计文档写计划`
- provides a `docs/superpowers/specs/*.md` path and asks for a plan

## Inputs

The primary input is a spec/design markdown file, normally under:

```text
docs/superpowers/specs/YYYY-MM-DD-name-design.md
```

If the user does not provide a path, search `docs/superpowers/specs/` by the topic they mentioned and prefer the newest matching file.

## Output Path

Default output path is derived from the spec path:

```text
docs/superpowers/specs/YYYY-MM-DD-name-design.md
-> docs/superpowers/plans/YYYY-MM-DD-name.md
```

If the target plan already exists, do not overwrite it silently. Explain the target file and impact, then wait for explicit user approval before modifying it.

## Workflow

1. Read `AGENTS.md` first and follow the repository rules.
2. Read the full spec/design document.
3. Read 1-3 recent files under `docs/superpowers/plans/` to match local plan style.
4. Write a concrete implementation plan with task checkboxes.
5. Do not implement code unless the user explicitly asks to continue from the plan into implementation.

## Required Plan Structure

The plan should include:

- Title
- Agentic worker note, if this repository's existing plans use it
- Goal
- Architecture
- Tech Stack
- Spec document path
- File Map
- Phased tasks with `- [ ]` checkboxes
- Tests and verification commands
- Design decisions
- Out of scope

## Quality Bar

- Convert the spec into execution order, not a loose summary.
- Keep task ownership clear by file path.
- Call out backend/frontend contract boundaries.
- Include verification commands that match the touched areas.
- Preserve existing repository conventions and naming.
- Avoid adding implementation details that contradict the spec.
