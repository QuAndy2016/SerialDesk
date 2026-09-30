# Changelog

## [v0.2.13] - 2026-09-30

### Changed

- README rewritten as a fully bilingual document (U17): every section now carries a Chinese and an
  English version; features, roadmap, quick start, layout, acknowledgements and support are all mirrored
- Donation section follows option C (U18): overseas readers are explicitly told that the personal WeChat
  QR only works in mainland China and pointed to stars / issues / sharing instead of an unusable channel
- Default quick-send row count (10) documented in the feature list

## [v0.2.12] - 2026-09-30

### Fixed

- Baud box gave no visual cue that the right-hand part is a dropdown (U20): the dropdown area now has a
  left separator line plus a down-arrow icon (two colour variants, one per theme), and a tooltip explains
  "type a custom baud rate, or use the arrow to pick from 26 presets"
- Baud box now marks invalid input immediately (red border via `QComboBox[invalid="true"]`) instead of
  only reporting "波特率格式错误" when the port is opened

### Changed

- Theme QSS resolves asset paths via a `__ASSETS__` placeholder (`ui.theme.qss()`), so image resources work
  from source and from the PyInstaller bundle; build workflow now bundles the whole `assets/` directory

## [v0.2.10] - 2026-09-30

### Added

- README: "支持这个项目 / Support" section with a WeChat donation QR code
  (`assets/donate_wechat.png`, cropped from the payment card, 420x447 PNG, ~30 KB) and donation copy

## [v0.2.9] - 2026-09-30

### Added

- Quick-send panel now seeds 10 blank command rows on first run (no config.json yet), instead of
  starting empty; existing configs keep their stored row count (U15)

### Fixed

- Dark theme: the quick-send scroll area left a large white/light block below the rows
  (`QScrollArea` styled transparent but its viewport/container still painted the default palette
  background). Added `QScrollArea > QWidget > QWidget { background: transparent; }` to both palettes (U13)
- Dark theme: the View menu (QMenuBar/QMenu) was unstyled and fell back to the system light palette.
  Both palettes now style QMenuBar / QMenu / QMenu::item / QMenu::item:selected (U14)

## [v0.2.8] - 2026-09-30

### Changed

- CI: bumped `softprops/action-gh-release` from `v2` (final v2 release, Node 20 runtime deprecated)
  to `v3` (Node 24). No packaging or application changes.

## [v0.2.7] - 2026-09-30

### Changed

- Windows packaging switched from PyInstaller `--onefile` to `--onedir` and is now shipped as a zip
  archive (`SerialAssistant_vX.Y.Z-win64.zip`): exe + runtime folder + 使用说明.txt.
  The onefile self-extracting bootloader is a known trigger for Defender / SmartScreen false positives.
- Build workflow now packages the zip, writes a `.sha256` checksum file, uploads both as artifacts and
  attaches both to the GitHub Release.
- README download section rewritten: zip extraction guidance, SmartScreen / Edge keep-file steps,
  checksum verification.

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [v0.2.6] - 2026-09-30

### Added

- README rewrite: project intro, full v0.2.x feature list, roadmap aligned with the local dev task list,
  acknowledgements section, and a "Download Windows EXE" guide pointing at Releases
- GitHub Releases publishing (strategy B): pushing a `v*` tag builds the Windows EXE and attaches it to
  the matching release; branch pushes keep uploading build artifacts as before
- Tag/version consistency guard in the build workflow (tag must equal `app.__version__`)

### Changed

- Version constant bumped to `0.2.6`

### Fixed

- Acknowledgements: all external links verified and written as Markdown hyperlinks inside parentheses
  (no raw URLs in prose). SSCOM site (http://www.daxia.com) is http-only; LLCOM GitHub and VOFA+ verified

## [v0.2.5] - 2026-09-30

### Added

- View menu with manual theme switch: follow system / dark / light, choice persisted to config.json (U9)

## [v0.2.4] - 2026-09-30

### Fixed

- Quick-send delete button rendered blank: global QSS padding (5px 14px) squeezed the 28px button to
  zero content width; padding is now overridden per button (U8)

## [v0.2.3] - 2026-09-30

### Added

- Single-source version constant in `app/__init__.py`; window title shows the version
- EXE and Actions artifact are named with the version (`SerialAssistant_vX.Y.Z.exe` / `SerialAssistant-vX.Y.Z-win64`) (U7)

### Changed

- CHANGELOG entries added for v0.2.1 / v0.2.2

## [v0.2.2] - 2026-09-30

### Added

- UART waveform logo (assets/icon.png + icon.ico, 7 sizes) (U6)
- Window icon (title bar + taskbar)
- EXE icon via PyInstaller `--icon` in build workflow

## [v0.2.1] - 2026-09-30

### Fixed

- Duplicate send-format combo caused an orphan label in the connection bar (U1)
- Tooltips added to all format / split / timestamp / checksum dropdowns (U2)
- Typing a frame header now auto-switches to header-split mode (U3)
- Quick-send button sizing: delete btn 28px, send btn min 52px, panel 380-420px (U4)
- Status light now shows port + baudrate (U5)

## [v0.2.0] - 2026-09-30

### Added

- Baud rate: 26 presets (110 ~ 3000000, LLCOM-compatible) + editable custom input
- Receive format dropdown: ASCII / HEX / HEX+ASCII dual display
- Send format dropdown: HEX / ASCII
- Frame splitting by time gap: off / auto (3.5-char rule by baud rate, 5ms USB floor) / manual ms / by header
- Timestamp prefix dropdown: none / HH:MM:SS / HH:MM:SS.mmm / yyyy-MM-dd HH:MM:SS.mmm
- Checksum append dropdown: none / CRC16-Modbus / CRC16-CCITT / CRC32 / SUM8
- Quick send panel: add/delete commands, max 99, persisted to config.json
- Receive buffer cap (20k blocks) to prevent unbounded memory growth

### Changed

- SerialWorker.received now carries a monotonic timestamp for frame splitting
- Main window layout: left (rx/tx) + right (quick send panel), resizable splitter
- README quick-start updated with the real repo URL

### Tests

- Unit tests: 25 cases (HEX/ASCII, CRC16-Modbus, CRC16-CCITT, CRC32, SUM8, append_checksum, Modbus frames)

## [v0.1.0] - 2026-09-30

Initial release.

### Added

- COM port enumeration with 3s auto-refresh
- Baud rate selection (1200 ~ 921600)
- Open/close serial port with status indicator
- HEX/ASCII send & receive with timestamps
- RX/TX byte counter
- CRC16-Modbus append & validate option
- Background QThread reading (UI responsive)
- Unit tests: 16 cases (HEX/ASCII, CRC16-Modbus, Modbus frames)

### Project setup

- MIT License
- Bilingual README (Chinese + English)
- Business model declaration (open source forever, optional Pro tier after 500 stars)
