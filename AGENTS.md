# Alpha Quant — Agent Workflow

## Body Formatting Rule

**Always use `--body-file /tmp/body.md` for multi-line issue/PR bodies.** Never use inline `\n` in `--body "..."` — bash double quotes do not interpret `\n` as newlines, producing raw `\n` text in the GitHub UI.

Template:

```bash
cat > /tmp/body.md << 'EOF'
... multi-line content with proper newlines ...
EOF

gh <command> --body-file /tmp/body.md
```

---

## Phase Lifecycle

Work proceeds in phases (P0 → P1 → ... → P6). Between each phase, a **Refinement Sprint** is conducted. Within each phase, work follows the **Full Issue Lifecycle**.

```
┌─────────────────────────────────────────────────────────┐
│  Phase N                                                    │
│  ┌──────────────────┐   ┌──────────────────┐               │
│  │  Issue N.1       │ → │  Issue N.2       │ → ... → Done │
│  │  (Full Lifecycle) │   │  (Full Lifecycle) │               │
│  └──────────────────┘   └──────────────────┘               │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
              ┌────────────────────────────┐
              │  Refinement Sprint          │
              │  (PO + System Designer +    │
              │   Software Architect +      │
              │   Data Architect +          │
              │   Data Engineer)            │
              │  → Backlog for Phase N+1   │
              └────────────────────────────┘
                            │
                            ▼
                      Phase N+1 ...
```

---

## Full Issue Lifecycle

### 1. Pick Up Next Issue

```bash
# Find the next unstarted issue by priority (P0 → P1 → P2 ...)
gh issue list --state open --json number,title,labels --label P0

# View its full description and acceptance criteria
gh issue view <N> --json title,body
```

### 2. Update Board — Start

```bash
# Find the project item ID for the issue
gh project item-list 1 --owner mblaauw --format json \
  | python3 -c "import sys,json; data=json.load(sys.stdin); [print(i['id']) for i in data.get('items',data) if i.get('content',{}).get('number')==<N>]"

# Move to "In Progress" (optionId: 47fc9ee4)
gh api graphql -f query='
mutation {
  updateItem: updateProjectV2ItemFieldValue(
    input: {
      projectId: "PVT_kwHOAD316c4BaTNX"
      itemId: "<PROJECT_ITEM_ID>"
      fieldId: "PVTSSF_lAHOAD316c4BaTNXzhVLzJo"
      value: { singleSelectOptionId: "47fc9ee4" }
    }
  ) { projectV2Item { id } }
}'

# Assign to user
gh issue edit <N> --add-assignee "@me"
```

### 3. Create Branch

```bash
git checkout main && git pull origin main
git checkout -b <feature-branch-name>
```

Branch naming: `<scope>-<description>` (e.g. `port-interfaces-p0.2`, `fake-adapters-p0.6`).

### 4. Implement

- Follow existing code conventions (type hints, imports, patterns)
- Use `typing.Protocol` for ports or `abc.ABC` + `@abstractmethod` as specified
- All data models use `pydantic.BaseModel` with `frozen=True`
- Verify the code at every step (or use `make check`, `make format`, `make type` as aliases):

```bash
uv run ruff check alpha_quant/
uv run ruff format alpha_quant/
uv run ty check alpha_quant/
uv run pytest tests/ -q
```

- If golden replay fixture behavior changes, re-bless the golden hash:
  ```bash
  make bless-golden
  ```

### 5. Create PR

```bash
git add -A && git commit -m "<scope>: <title>"
git push origin <feature-branch-name>

cat > /tmp/pr_body.md << 'EOF'
## Summary

Completes <scope> (closes #<N>).

### Changes

- Bullet list of what was changed

### Verification

- `ruff check` — All checks passed
- `ruff format --check` — All files formatted
- `ty check` — All checks passed
- `pytest` — All tests passed
EOF

gh pr create \
  --base main \
  --head <feature-branch-name> \
  --title "<scope>: <title>" \
  --body-file /tmp/pr_body.md
```

PR body must include:
- A summary paragraph
- A `### Changes` section with bullet points
- An `### Verification` section with the 4 tool checks (ruff, format, ty, pytest)

### 6. Code Review Loop (Iterative) — MANDATORY

**ALWAYS do a thorough code review of the PR after pushing. Do NOT skip this step.** The review is your own critical assessment — read every changed line, run the code mentally, and check every acceptance criterion from the issue.

The review MUST produce visible PR comments (not just mental notes). This creates an audit trail of issues found and fixes applied.

#### 6a. Review PR diff against each AC item

```bash
gh pr diff <PR_NUMBER>
gh issue view <N> --json body
```

For every acceptance criterion in the issue:
- Read the corresponding code in the diff
- Verify the code actually satisfies the criterion
- Check edge cases, error handling, typing, and performance
- For each criterion, note PASS or FAIL

#### 6b. Post PR review comments for every issue found — MANDATORY

For each issue found (unmet AC, bug, style problem, missing edge case, performance concern, etc.), **you MUST post a PR review comment** before making any fixes:

**Always use `--body-file /tmp/review.md` with proper Markdown formatting.** Never use inline `--body "..."` — bash double quotes do not interpret `\n` as newlines, producing raw `\n` in the PR review UI.

Template for a failing review:

```bash
cat > /tmp/review.md << 'EOF'
**Issue found in review**

| # | File | Issue |
|---|------|-------|
| 1 | `sizing.py:44` | Formula missing `* price` factor — see CRIT-1 |
| 2 | `risk.py:76` | Trailing stop never trails |

**AC Verification**
- AC 1 (fix formula): ❌ — see issue 1 above
- AC 2 (update tests): ✅ — all 260 pass

**Notes**
- Edge case: negative equity not handled
- Performance: O(n) is acceptable
EOF

gh pr review <PR_NUMBER> --comment --body-file /tmp/review.md
```

Template for a passing review (no issues found):

```bash
cat > /tmp/review.md << 'EOF'
**Code Review — Passed**

**AC Verification**
- AC 1 (unified scoring path): ✅ — `bars_up_to` helper extracted and used by both files
- AC 2 (no behavior change): ✅ — 260/260 tests pass

**Quality checks**
- Follows existing patterns in `_loop.py` (typed, pure, consistent naming)
- No edge cases missed
- No performance concerns

**Verdict:** Ready to merge.
EOF

gh pr review <PR_NUMBER> --comment --body-file /tmp/review.md
```

This creates a readable, structured audit trail on GitHub. Even self-found issues must be commented. The PR review tab should show all discovered problems.

Example:
```bash
cat > /tmp/review.md << 'EOF'
**Issue found in review**

| # | File | Issue |
|---|------|-------|
| 1 | `sizing.py:44` | Formula missing `* price` factor — see CRIT-1 |
| 2 | `risk.py:76` | Trailing stop never trails |
EOF

gh pr review <PR_NUMBER> --comment --body-file /tmp/review.md
```

#### 6c. Fix every issue

For each issue found in the review:
- Fix the code locally
- Re-run the 4 tool checks:
  ```bash
  uv run ruff check alpha_quant/
  uv run ruff format alpha_quant/
  uv run ty check alpha_quant/
  uv run pytest tests/ -q
  ```
- Amend the commit: `git add -A && git commit --amend --no-edit`
- Force-push: `git push --force-with-lease origin <branch>`

#### 6d. Re-review the PR

After all fixes are pushed:
- Read the updated diff to confirm each issue is resolved: `gh pr diff <PR_NUMBER>`
- Verify no new issues were introduced
- If new issues found, go back to step 6b

**The review-fix-re-review cycle must converge to zero issues before proceeding.** Only when every AC item is demonstrably satisfied and no issues remain should you move on.

### 7. Update Issue Status

After the code review loop passes (zero issues), update the issue body to check off all completed AC items:

```bash
cat > /tmp/issue_body.md << 'EOF'
## Description

<updated description>

## Acceptance Criteria

- [x] <criterion 1>
- [x] <criterion 2>

## Technical Details

<details if needed>
EOF

gh issue edit <N> --body-file /tmp/issue_body.md
```

### 8. Squash & Merge

```bash
gh pr merge <PR_NUMBER> --squash \
  --subject "<scope>: <title>" \
  --body "Completes <scope> (closes #<N>). <brief summary>."
```

### 9. Update Board — Done

```bash
# Move to "Done" (optionId: 98236657)
gh api graphql -f query='
mutation {
  updateItem: updateProjectV2ItemFieldValue(
    input: {
      projectId: "PVT_kwHOAD316c4BaTNX"
      itemId: "<PROJECT_ITEM_ID>"
      fieldId: "PVTSSF_lAHOAD316c4BaTNXzhVLzJo"
      value: { singleSelectOptionId: "98236657" }
    }
  ) { projectV2Item { id } }
}'
```

### 10. Clean Up

```bash
git checkout main && git pull origin main
git branch -D <feature-branch-name>
git push origin --delete <feature-branch-name>
```

---

## Refinement Sprint

A Refinement Sprint runs **between phases** (e.g., P2→P3, P4→P5). It is a cross-functional review involving the **PO**, **System Designer**, **Software Architect**, **Data Architect**, and **Data Engineer**.

### 1. PO creates a Refinement Issue

The PO creates a refinement issue with a multi-line body using `--body-file`:

```bash
cat > /tmp/refinement_body.md << 'EOF'
## Description

<clear description of what to evaluate>

## Acceptance Criteria

### ADR Audit
- [ ] Review all ADRs for relevance; flag any that are obsolete, superseded, or missing

### Dependency Fitness
- [ ] Evaluate every dependency (keep / remove / replace / add)
- [ ] Flag unused or outdated dependencies

### Duplicate Code
- [ ] Quantify duplicate code patterns across the codebase
- [ ] Propose refactoring targets

### Architecture Consistency
- [ ] Verify hexagonal architecture rules (domain → ports → adapters)
- [ ] Check for violations (domain importing from app/adapters, etc.)

### Data Architecture
- [ ] Review data models for correctness (accrual ratio, position sizing, etc.)
- [ ] Check schema consistency between models, store, and normalize layers

### Trading Logic Audit
- [ ] Review risk management formulas (stops, sizing, trailing, drawdown)
- [ ] Review fill model for edge cases (gap-through, partial fills)
- [ ] Verify composite ranking formulas (factor weights, double-counting)

### Future-Proofing
- [ ] Assess how upcoming phases (P3, P4, P5) integrate with current architecture
- [ ] Identify blocking issues for next phase

## Technical Details

<details if needed>
EOF

gh issue create \
  --title "P<N>.R: Technical refinement — <scope>" \
  --label "story,priority/p0,size/m,domain/backend,P<N>" \
  --body-file /tmp/refinement_body.md
```

### 2. Cross-functional evaluation

Each role evaluates their domain:

| Role | Focus |
|------|-------|
| PO | Backlog priorities, acceptance criteria, business value |
| System Designer | Architecture, code quality, dependency rules, module boundaries |
| Software Architect | Port interfaces, adapter patterns, event design, testability |
| Data Architect | Data models, store schema, normalization, data flow |
| Data Engineer | Connector robustness, caching, rate limiting, data integrity |

### 3. Produce outputs

- **Refactoring Punch List**: Save to `docs/adr/REFAKTORING_PUNCH_LIST.md` with P0/P1/P2 priority groupings
- **New ADRs**: Create files in `docs/adr/` following MADR template for each new architectural decision
- **Updated ADRs**: Update existing ADRs that are stale or superseded
- **New Backlog Issues**: Create issues for each actionable finding with priority/size labels
- **Updated Issue Descriptions**: Update existing issue bodies if scope changes

### 4. PO acts on outputs

- Review punch list with the team
- Assign priority/size labels to each new issue
- Update the backlog for the next phase
- Present to stakeholders if needed

---

## Project Board Constants

| Field | ID |
|-------|-----|
| Project ID | `PVT_kwHOAD316c4BaTNX` |
| Status Field ID | `PVTSSF_lAHOAD316c4BaTNXzhVLzJo` |
| Status: Todo | `f75ad846` |
| Status: In Progress | `47fc9ee4` |
| Status: Done | `98236657` |

## Tooling Requirements

- All code must pass: `ruff check`, `ruff format --check`, `ty check`
- Python 3.14+, pydantic v2, type-annotated
- No imports from `adapters/` or `data/` in port definitions
