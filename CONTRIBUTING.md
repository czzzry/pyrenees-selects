# Contributing

Selects is an early local-first pre-editor. Small, testable changes that preserve source identity and user control are welcome.

## Set up

```bash
git clone https://github.com/czzzry/pyrenees-selects.git
cd pyrenees-selects
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
```

FFmpeg and ffprobe must also be available on `PATH` for media integration tests and manual workflows.

## Verify a change

```bash
make test
```

For interface changes, test the reusable app at narrow and wide widths, with keyboard-only navigation, an empty project, broken media, and at least one real full-source selection.

The automated product journey requires Node.js and Chromium once per machine:

```bash
npm ci
npx playwright install chromium
make test-browser
```

It exercises the neutral sample from calculated plan through overnight work, exact full-source review, reload, frozen assembly, low-resolution preview, Resolve export, responsive layout, and accessibility checks.

## Product boundaries

- Never modify or reorganize original footage.
- Preserve exact source identity and ranges independently from rendered previews.
- Keep manual use complete without an LLM.
- Treat assistant output as a proposal that requires explicit acceptance.
- Keep Pyrenees-specific recipes in the case-study layer; reusable behavior must work on a neutral project.
- Avoid adding precision finishing features that belong in Resolve unless a new product decision explicitly changes the boundary.

## Pull requests

Describe the user problem, the behavior change, tests performed, privacy or migration impact, and any known limitation. Do not commit personal footage, generated media, API keys, local databases, or application-data paths.
