---
name: github
description: GitHub workflow for Alpha-Quant — issue lifecycle, PR management, project board operations, and the phase system defined in AGENTS.md.
---

# GitHub for Alpha-Quant

## Phase Lifecycle

Work follows phases (P0 → P1 → ... → P6) with Refinement Sprints between phases. Each phase contains issues that go through the Full Issue Lifecycle.

## Project Board Constants

| Field | ID |
|-------|-----|
| Project ID | `PVT_kwHOAD316c4BaTNX` |
| Status Field ID | `PVTSSF_lAHOAD316c4BaTNXzhVLzJo` |
| Status: Todo | `f75ad846` |
| Status: In Progress | `47fc9ee4` |
| Status: Done | `98236657` |

## Full Issue Lifecycle

### Start an Issue

```bash
gh issue view <N> --json title,body
gh project item-list 1 --owner mblaauw --format json \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(i['id']) for i in d.get('items',d) if i.get('content',{}).get('number')==<N>]"
# Move to In Progress: optionId 47fc9ee4
gh issue edit <N> --add-assignee "@me"
```

### Create a PR

```bash
git checkout -b <scope>-<description>
# implement, commit, push
gh pr create --base main --head <branch> --title "<scope>: <title>" --body-file /tmp/pr_body.md
```

### Review a PR

```bash
gh pr diff <PR_NUMBER>
gh pr review <PR_NUMBER> --comment --body-file /tmp/review.md
```

### Merge

```bash
gh pr merge <PR_NUMBER> --squash --subject "<scope>: <title>" --body "Completes <scope> (closes #<N>)."
```

### Update Board — Done

Use `optionId: 98236657` for the Done status.

## Body Formatting

Always use `--body-file /tmp/body.md` for multi-line content — bash double quotes do not interpret `\n` as newlines.
