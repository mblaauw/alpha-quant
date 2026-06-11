# Alpha Quant — Agent Workflow

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
- Verify the code at every step:

```bash
uv run ruff check alpha_quant/
uv run ruff format alpha_quant/
uv run ty check alpha_quant/
```

### 5. Create PR

```bash
git add -A && git commit -m "<scope>: <title>"
git push origin <feature-branch-name>

gh pr create \
  --base main \
  --head <feature-branch-name> \
  --title "<scope>: <title>" \
  --body "## Summary\n\nCompletes <scope> (closes #<N>).\n\n### Changes\n\n- Bullet list of what was changed\n\n### Verification\n\n- \`ruff check\` — All checks passed\n- \`ruff format\` — All files formatted\n- \`ty check\` — All checks passed"
```

PR body must include:
- A summary paragraph
- A `### Changes` section with bullet points
- An `### Verification` section with the 3 tool checks

### 6. Code Review Loop (Iterative)

**ALWAYS do a thorough code review of the PR after pushing.** Do NOT skip this step. The review is your own critical assessment — read every changed line, run the code mentally, and check every acceptance criterion from the issue.

#### 6a. Review PR diff against each AC item

```bash
gh pr diff <PR_NUMBER>
gh issue view <N> --json body
```

For every acceptance criterion in the issue:
- Read the corresponding code in the diff
- Verify the code actually satisfies the criterion
- Check edge cases, error handling, typing, and performance
- For each criterion, note PASS or FAIL in your head (or in a PR comment)

#### 6b. Add PR review comments for every issue found

For each issue (unmet AC, bug, style problem, missing edge case, performance concern, etc.):

```bash
# Add a PR review comment pointing at the specific code
gh pr review <PR_NUMBER> --comment --body "<file>:<line> — <what's wrong>"
```

#### 6c. Fix every issue

For each issue:
- Fix the code locally
- Re-run the 3 tool checks:
  ```bash
  uv run ruff check alpha_quant/
  uv run ruff format alpha_quant/
  uv run ty check alpha_quant/
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
gh issue edit <N> --body "<updated body with [x] checks>"
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

## Refinement Workflow

When the PO calls for a technical refinement, the Software Designer evaluates the current state and reports back.

### 1. PO creates a Refinement Issue (P1.R style)

Issue title: `P1.R: Technical refinement — <scope>`
Labels: `story, priority/p0, size/m, domain/backend, P1`
Body includes:
- Acceptance criteria organized in sections (ADR audit, dependency fitness, duplicate code, architecture consistency, future-proofing)
- Required outputs: updated ADRs, refactoring punch list (P0/P1/P2), library recommendation report

### 2. Software Designer completes evaluation

- Reviews every ADR for relevance
- Evaluates every dependency (keep / remove / replace / add)
- Quantifies duplicate code patterns
- Proposes ADR amendments or new ADRs (status: Proposed)
- Produces the refactoring punch list

### 3. Software Designer commits ADR updates

Files in `docs/adr/` — new ADR files following MADR template. Updated `docs/adr/README.md` index.

### 4. PO acts on outputs

- Creates refactoring issue(s) from punch list (P1.RA, P1.RB, etc.)
- Updates remaining P1.x issue descriptions if ADR changes affect their scope
- Updates priority/size labels on affected issues

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
