# Contributing

Thanks for helping build F1 Game Telemetry. Work is tracked on the
[F1 Game Telemetry Roadmap](https://github.com/users/rdgonzaga/projects/3).

## Workflow

1. **Pick an issue.** Start from an issue in the Ready column, or open one with the ticket template.
2. **Branch off `main`** using `<type>/<issue#>-slug`, e.g. `feat/9-cartelemetry2` or `fix/42-lap-delta`.
3. **Commit** with semantic subjects only, no body:
   `feat(parser): parse CarTelemetry2 packet`, `fix: handle flashback rewind`, `docs: add telemetry setup`.
   Types: `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `ci`, `build`, `chore`, `style`, `revert`.
4. **Open a pull request** using the template. The title must also be semantic, and the
   body must include `closes #<issue>`. Add the same labels as the issue.
5. **Merge** once CI passes. Pull requests are squash merged, so the PR title becomes the commit on `main`.

Keep branches up to date by rebasing on `main`.

## Issues

Titles use a category prefix: `[FEATURE]`, `[PARSER]`, `[ENDPOINT]`, `[DEV]`, `[CHORE]`, `[CI]`, `[DOCS]`, `[PERF]`, `[BUG]`.
Bodies follow the Description, Requirements, Acceptance Criteria and Notes format from the templates.

## Community

- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Report security issues privately as described in [SECURITY.md](SECURITY.md).
