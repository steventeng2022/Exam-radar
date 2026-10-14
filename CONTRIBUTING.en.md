# Contributing

[繁體中文](CONTRIBUTING.md) | **English**

Bug reports, suggestions, and pull requests are welcome through [GitHub Issues](https://github.com/steventeng2022/Exam-radar/issues) and the repository's pull requests. Discussions may be in Traditional Chinese or English. Please treat other participants respectfully.

## Development and validation

See [Local setup](README.en.md#local-setup) for requirements and startup instructions: Python 3.12+ and Node.js 22+.

Fork this repository, clone your fork, and create a branch for your changes. Use a Python virtual environment and install requirements.txt from the repository root. Run `npm install` inside `frontend/`.

Run the checks relevant to your changes, following GitHub Actions:

```bash
# From the repository root: backend and crawler
python -m pytest tests -q
python -m compileall -q backend crawler

# Frontend
cd frontend
npm run typecheck
npm run build
```

Tests use local fixtures; real school websites and model API keys are not required. For behavior changes, add a test that reproduces the problem. Documentation corrections do not require new tests.

## Reporting issues and submitting pull requests

- Include reproduction steps, expected and actual results, environment details, and error messages with sensitive information removed.
- Keep each pull request focused on one topic. Explain the reason for the change, resulting behavior, and checks you actually ran.
- Update the relevant documentation when changing configuration, APIs, or usage.
- State the license of any new dependency and preserve third-party copyright and license notices.

## Data and credentials

Do not commit .env files, real tokens, databases, crawled documents, or students' personal information. Use placeholders in configuration examples and test content you created and have permission to share publicly.

Crawler changes must continue to respect robots.txt, rate limits, source verification, and the human review workflow.

## Contribution license

Before submitting content, confirm that you have the right to contribute it. Unless explicitly stated otherwise and agreed by the maintainer, your original contributions are provided under the project's [MIT License](LICENSE).

Third-party dependencies and school announcements retain their respective rights. See the [README license section](README.en.md#license).
