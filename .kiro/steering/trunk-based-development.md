# Trunk-Based Development

## Overview

We follow trunk-based development practices for fast, continuous integration and deployment.

## Branching Strategy

### Main Branch
- **Single source of truth** - All development flows through `main`
- **Always deployable** - Main branch must always be in a releasable state
- **Protected** - Requires pull request reviews and CI checks

### Feature Development
- **Short-lived branches** - Feature branches live for hours/days, not weeks
- **Small changes** - Keep commits and PRs small and focused
- **Frequent integration** - Merge to main multiple times per day

## Workflow

1. **Create feature branch** from main
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/short-description
   ```

2. **Make small, incremental changes**
   - Follow our incremental development principles
   - Commit frequently with conventional commit messages
   - Keep changes focused and reviewable

3. **Create pull request** to main
   - Run tests locally before creating PR
   - Ensure CI passes (lint, test, build)
   - Request review following our approval workflow

4. **Merge and delete branch**
   - Squash merge to keep main history clean
   - Delete feature branch immediately after merge

## Benefits

- **Fast feedback** - Issues caught quickly through frequent integration
- **Reduced conflicts** - Small, frequent merges minimize merge conflicts
- **Continuous deployment** - Always ready to deploy from main
- **Simplified workflow** - No complex branching strategies to manage

## CI/CD Integration

- **GitHub Actions** run on all PRs to main
- **Quality gates** prevent broken code from reaching main
- **Automated testing** ensures main branch stability
- **Path-based triggers** optimize CI resource usage

## Rules

- **No direct commits to main** - All changes via pull requests
- **Delete branches after merge** - Keep repository clean
- **Fix forward** - If main breaks, fix it immediately
- **Small PRs** - Aim for PRs that can be reviewed in < 30 minutes
