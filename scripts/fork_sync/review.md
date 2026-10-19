This directory is a scratch copy of the user's Hermes fork, unattended. NousResearch's main ({upstream}) has been merged into the fork ({fork}); the merge is committed unless git hit conflicts.

Git conflicts: {clashes}

Triage flagged these NousResearch commits as meeting the user's changes:

{flags}

For each, read his change (FORK.md; plugins and skills live outside this copy) and the commits (`git show <hash>`), and apply the rules at the top of FORK.md. In short: same change, theirs wins and his entry moves to "Retired"; partial overlap or different behaviour, his version stays as the only one and his entry moves to "Pending review" with the differences; code his change hooks into changed, adapt his change. Resolve any conflicts the same way. For a plugin or skill, change nothing here and say what it needs.

Make sure `"{python}" -c "import run_agent, hermes_cli.main, gateway.run"` works, then commit (`git commit --no-verify`). If something cannot be settled well, run `git merge --abort` (or `git reset --hard {fork}` if the merge was already committed); the update then waits.

Your final reply is the user's note. He is not a programmer: one short plain-English paragraph per flagged item saying what NousResearch did and what you did; for "Pending review", the differences.
