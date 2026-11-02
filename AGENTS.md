# Repository Guidelines

## Project Structure & Module Organization

This repository is a Markdown publishing CLI for WeChat articles and videos. Primary Python entry points and reusable modules live in `scripts/`: `wechat_publisher.py` renders and creates drafts, `styles.py` manages built-in and custom styles, and `video_publisher.py` coordinates HTML scenes, Edge TTS, subtitles, and FFmpeg. Keep supporting rendering and media code beside its owning workflow. Node dependencies are limited to MathJax; Python dependencies are pinned in `requirements.txt`.

Place unit tests in `tests/` as `test_<area>.py`. Use `evals/files/` for Markdown evaluation fixtures, `assets/` for checked-in visual assets, and `references/` for behavior and style notes. Do not commit generated previews, videos, `tmp/` contents, local virtual environments, or `node_modules/`.

## Build, Test, and Development Commands

- `./install.sh` creates `.venv`, installs Python and Node dependencies, and installs Playwright Chromium.
- `.venv/bin/python3 -m unittest discover -s tests -v` runs the complete offline test suite.
- `.venv/bin/ruff check scripts tests` runs the configured Python error lint checks.
- `.venv/bin/python3 -m compileall -q scripts templates` verifies Python modules compile cleanly.
- `.venv/bin/python3 scripts/wechat_publisher.py --md article.md --style swiss --dry-run --out-html /tmp/preview.html` renders a local preview without calling WeChat.
- `.venv/bin/python3 scripts/styles.py --list` lists available style presets.
- `npm ci` restores the locked Node toolchain when only JavaScript dependencies need refreshment.

Video work also requires system `ffmpeg`; use `video_publisher.py --project-dir /tmp/video --duration 60 --out /tmp/video.mp4 --dry-run` before producing media.

## Coding Style & Naming Conventions

Follow the existing Python style: four-space indentation, `snake_case` functions and variables, `PascalCase` classes, and type hints where they clarify public or non-trivial code. Keep CLI behavior in a `main()` function behind an `if __name__ == "__main__":` guard. Prefer small, testable helpers and preserve the current standard-library `unittest` approach. No formatter or linter is configured; format touched code consistently with its surrounding module.

## Testing Guidelines

Add focused `unittest.TestCase` coverage for renderer output, parsing, configuration, and failure paths. Name tests `test_<expected_behavior>` and avoid live WeChat, TTS, browser, or network calls; use fixtures and mocks instead. Run the full discovery command above before opening a pull request. For visual rendering changes, also inspect a `--dry-run` HTML output locally.

## Commit & Pull Request Guidelines

Use the established Conventional Commit style: `feat(video): ...`, `fix(publisher): ...`, `docs: ...`, or `chore: ...`. Keep each commit narrowly scoped. Pull requests should describe user-visible behavior, list verification commands, link relevant issues, and include preview HTML or screenshots for rendering/style changes.

## Security & Configuration

Copy `env.example` to `.env`; never commit credentials, access tokens, or generated API responses. Treat `--no-verify-ssl` as a local troubleshooting option, not a default.

## Synchronized Installation

- `~/.agents/skills/publish-md-to-wechat` is a **symlink to this repository** (2026-11-02, replacing the former manual dual-copy sync). Both pod-pipe and the standalone skill therefore use this copy; renderer fixes and regression tests need to land here only once. The skill's `.env` credentials are this repo's `.env` (verified identical at migration). The pre-symlink copy is backed up at `~/.agents/backups/publish-md-to-wechat.bak-20261102`.
