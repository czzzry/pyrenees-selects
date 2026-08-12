# Support

Selects is an early open-source alpha maintained on a best-effort basis.

## Before asking for help

1. Read the [getting-started guide](docs/getting-started.md).
2. Run `.venv-selects/bin/selects doctor` and keep its non-sensitive output.
3. Retry with the built-in sample project. This separates installation problems from footage-specific problems.
4. Check the [current limits](README.md#current-limits) and existing GitHub issues.

## Where to ask

- Use a **Bug report** for reproducible failures in a supported workflow.
- Use a **Feature request** for a concrete problem that fits the pre-editor boundary.
- Use GitHub's private security-reporting flow for vulnerabilities. Do not post secrets, private footage, personal folder paths, or exploit details in a public issue.

Include the Selects version, macOS and Mac model, source codec and resolution, the last action that succeeded, the exact error text, and whether the sample project works. A short screen recording is helpful only if it contains no private media or paths.

## Support boundary

The declared desktop target is an Intel Mac running macOS 12 or later. Source installations require Python 3.11 or later plus FFmpeg and ffprobe. Public issues cannot guarantee response time, data recovery, compatibility with every camera codec, or support for modified builds.

Selects never needs a copy of private footage to begin diagnosing a problem. If a minimal media sample is essential, create or use synthetic footage unless you have explicit permission to share the original.
