# Contributing / 参与贡献

Thanks for wanting to help. SerialDesk is a one-person project, so small, focused
contributions are the easiest to review and merge.

中文说明见下方。

## Ways to help

- **Report a bug** - use the issue template; the version number, your Windows version and
  the exact steps make the difference between "fixable today" and "guesswork".
- **Suggest a feature** - open an issue and describe the workflow you are trying to get
  through, not only the control you want. The "why" decides the design.
- **Send a pull request** - keep it to one topic per PR. If it changes the UI, say which
  screen and in which language you checked it.
- **Tests** - `python -m pytest -q` must pass. UI changes should keep the offscreen smoke
  run working.
- **Translations** - the UI strings live in `app/i18n.py` as `{zh, en}` pairs. Adding a
  language means adding a key to each entry; the language menu picks it up automatically.

## Ground rules

- No new runtime dependency without a note in the PR explaining why it is worth it.
- Keep the existing style: UI strings go through `tr()`, colours come from `ui/theme.py`,
  and settings are persisted in `config.json` with a default for older files.
- Windows is the current release target; source runs on macOS/Linux are welcome but not
  packaged yet.

---

# 参与贡献

- **报 bug**：用 issue 模板，写清版本号、Windows 版本和复现步骤。
- **提需求**：说清你想完成的工作流，而不只是想要哪个控件 —— "为什么"决定设计。
- **提交 PR**：一个 PR 只做一件事；改界面的话说明在哪个界面、哪种语言下验证过。
- **测试**：`python -m pytest -q` 必须通过；改界面要保持离屏冒烟可跑。
- **翻译**：界面文案在 `app/i18n.py` 里是 `{zh, en}` 成对的，加一种语言就是给每条补一个键。

## 基本要求

- 不新增运行时依赖，除非在 PR 里说明为什么值得。
- 保持现有风格：文案走 `tr()`，颜色取自 `ui/theme.py`，配置项写进 `config.json` 并给旧文件留默认值。
