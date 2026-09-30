# Changelog

## [v0.6.6] - 2026-10-01

### Changed

- **The connection row now owns the top of the window (U72)**: the Settings button moved out of the menu bar to the
  end of the connection row, so Port / Baud / Refresh / Open / RX format / Port settings / Settings all sit on one
  line (verified: every control reports the same vertical centre). The menu bar is empty now and hidden, which
  removes a whole wasted row and lifts that line to the top of the window - it used to sit lower than the Settings
  button because the menu bar took a row of its own.
- **"Port settings..." left the Settings menu (U72)**: the button at the end of the connection row already opens the
  same dialog, so the duplicate entry is gone. The menu is now Theme / Language / Config / Auto-reconnect / About.

## [v0.6.5] - 2026-10-01

### Changed

- **Softer checked state in the dark theme (U71)**: a ticked box used to be a solid saturated cyan block, which
  glares against the dark background. It is now a calm dark-teal box with the bright accent reserved for the tick
  itself (#1f3a44 fill, #4b8fa3 border, cyan check mark), with matching hover and disabled variants. The light
  theme keeps its blue fill and white tick.

## [v0.6.4] - 2026-10-01

### Fixed

- **The split row drifted whenever the panes were resized (U70)**: the receive control row was a nested layout
  handed straight to the group's vertical box, so it absorbed spare height and centred its widgets - dragging the
  send pane down grew the receive group and visibly pushed the split/timestamp row downwards (the same for the
  send-side rows). Control rows (receive options, send history, format/checksum, repeat interval, file row) now
  live in holders with a fixed vertical size policy, and the data view takes every spare pixel, so each row is
  pinned to the top of its group with the data area starting right below it. Verified at three splitter
  positions: the control band stays constant at 46 px while the view grows 94 -> 207 -> 300 px.

## [v0.6.3] - 2026-10-01

### Changed

- **Quick-send deletion was redesigned (U68, plan A)**: the per-row "x" button is gone. Click any row to
  highlight it (the row frame gets an accent tint), then use the new **Delete selected** button in the panel
  header - or just press Delete while a row is focused. The 3 s undo stays, so a mistake is one click away from
  being undone. Rows are roomier without the button, and there is no longer a destructive control sitting next
  to "Send".

## [v0.6.2] - 2026-10-01

### Fixed

- **The Send button could disappear (U69)**: it trailed the crowded repeat-send row, so a narrow left column
  (splitter dragged, smaller window) could clip it out of view entirely - the button was there but pushed past
  the visible edge. The primary Send button now leads the bottom row (Send | Send file | progress | auto-reply |
  rules), is 110 px wide, and is verified visible even with the left column squeezed to 520 px. The send-history
  dropdown minimum dropped from 200 to 130 px, and the quick-send column now asks for at least 332 px, so its
  per-row buttons cannot be clipped either.

## [v0.6.1] - 2026-10-01

### Added

- **Choose which commands a sequence runs (U66)**: every quick-send row now carries a tick box. Ticked rows show
  a small number with their position in the sequence, and Run sends only those, in order; with nothing ticked the
  sequence behaves exactly as before (every filled row). The selection is persisted with the row.

### Fixed

- **Check boxes looked "filled but unticked" (U67)**: the checked state was a flat colour block without a visible
  tick, which made several options hard to read. Both themes now draw a real check mark (shipped as assets) with
  hover and disabled states.
- **Scroll bars were a hairline (U67)**: they are 13 px wide now, with rounded hoverable handles and no arrow
  buttons, in both themes.
- **Layout polish from the review screenshot (U67)**: the connection row sits closer to the top of the window, the
  receive/send groups lost their extra padding so the control row hugs the group top, the split-mode hint is no
  longer clipped, and the per-row delay box is about a third narrower.

## [v0.6.0] - 2026-10-01

### Added

- **Auto-reconnect after an unexpected loss (T14)**: with the new "Auto-reconnect" switch in Settings, an
  unplugged or wedged adapter is re-opened automatically with a 0.5-5 s backoff (up to 60 attempts, then it
  gives up and says so). A manual close never triggers it, the choice is persisted, and the status bar
  reports every attempt ("Connection lost - reconnecting (attempt n)...") and the outcome.
- **Windows installer (U34)**: every tagged release now also ships
  `SerialDesk_vX.Y.Z-win64-setup.exe`, built with Inno Setup in CI - next / next / finish, no more unzipping a
  folder by hand. It installs per-user by default, creates Start-menu and optional desktop shortcuts, and the
  portable zip remains available for people who prefer it.

### Changed

- **Config and logs moved out of the program folder (U34)**: they now live in `%APPDATA%\SerialDesk` (or the
  platform equivalent), so a frozen build never writes into `%TEMP%` or into Program Files. Dropping an empty
  `portable.txt` next to the executable switches back to portable mode (everything stays beside the exe).
- **The download is roughly half the size (U34)**: the bundle no longer carries the QML/Quick/PDF engines, the
  software-OpenGL fallback or Qt's own translation files - pieces this application never uses.

## [v0.5.1] - 2026-10-01

### Changed

- **Serial parameters moved into their own dialog (U35-P3)**: data bits, parity, stop bits, flow control,
  encoding, plus DTR/RTS and the CTS/DSR/DCD/RI signal lines, are configured once and rarely touched, so they
  now live in a modeless "Port settings" window (opened from the Settings menu or the button beside the port
  selector). The main window keeps a one-line summary of the active parameters ("8N1 - None - ASCII"), which
  completes the U35 layout work: the data panes keep the space those controls used to occupy and the settings
  stay one click away. The parameter controls are still disabled while a port is open, and the open/send paths
  read them exactly as before.

## [v0.5.0] - 2026-10-01

Batched usability release: the ten remaining "small" items from the task list, shipped together instead of
one release per fix.

### Added

- **Keyboard shortcuts (U39)**: Ctrl+Enter sends, Ctrl+L clears (undoable), Ctrl+S quick-saves the log,
  Ctrl+K focuses the send box, F5 opens/closes the port, Ctrl+F opens the find bar and Esc leaves it or
  stops a repeat/sequence run.
- **Find bar in the receive pane (U41)**: Ctrl+F shows a find row with next/previous and wrap-around search.
- **About box (U44)**: Settings -> About shows the version, PySide6/pySerial versions, the licence and the
  project link - the version was previously invisible in the UI.
- **Auto-scroll toggle (U43)**: the receive pane follows new data by default; unticking the new checkbox
  pauses it, and scrolling by hand pauses it automatically.
- **Undoable clear (U42)**: clearing the pane (Ctrl+L) keeps a five-second undo that restores every line with
  its colouring and the previous counters.
- **First-run hint (U48)**: one restrained status-bar tip on the very first launch.
- **Display-cap warning (U45)**: when the receive pane reaches its 20 000-line cap it says so once instead of
  silently dropping the oldest lines.
- **Menu access keys (U40)**: Settings, Theme, Language, Config and their entries now carry Alt-navigation
  access keys in both languages.

### Changed

- **Tooltips state the defaults (U46)**: the repeat interval, per-row delay and manual split gap tooltips now
  name their range and default value.

## [v0.4.18] - 2026-10-01

### Fixed

- **A device that stopped honouring hardware flow control could still wedge the process (U65)**: with RTS/CTS
  enabled and a peer that never asserts CTS, Windows can leave the process inside a serial driver call that
  never returns - the window stops responding and even Task Manager cannot close it.
  - With hardware flow control on, a frame is now dropped when CTS is not asserted (or cannot be read)
    instead of calling `write()`, so the app never enters the driver's blocking path. The status bar explains
    it: "Peer CTS is not asserted - the frame was dropped. If the device does not drive CTS, set Flow to None".
  - After a write timeout the port is marked degraded and further sends are refused ("Sending paused: the
    device stopped responding. Re-open the port to continue") instead of walking back into the stuck driver.
  - Re-opening the port clears the degraded state; the repeat loop stops on either condition.

## [v0.4.17] - 2026-10-01

### Fixed

- **Repeat-sending into a device that stopped reading froze the window and blocked exit (U64)**: with hardware
  flow control (RTS/CTS) and a peer that never asserts CTS, every write timed out and the repeat loop kept
  refilling the queue, so the worker thread sat inside `write()` and the receive path starved (RX stayed 0).
  Closing the port from the GUI then blocked inside the driver, which is what turned into "Not Responding"
  and an app that would not quit.
  - The worker now drains at most two frames per loop turn, so signal polling and the receive path keep
    running while a device is stuck.
  - A write timeout clears the stale backlog instead of retrying it forever, and stops the repeat loop with
    the existing red timeout message.
  - `close_port()` no longer touches the port from the GUI thread: it asks the worker to stop and returns
    immediately, and the owning thread closes the handle on its way out. Shutdown waits at most 1.5 s, so
    quitting can never hang.

## [v0.4.16] - 2026-09-30

### Fixed

- **The non-collapsible flags added in v0.4.15 were set too early (U63)**: `setCollapsible()` was called
  before the panes were added, so Qt ignored it ("index out of range") and the splitters still reported their
  children as collapsible. The flags now go on after both panes exist, and the guard is asserted in testing:
  no matter how far a divider is dragged, the receive pane keeps >= 170 px, the send pane >= 190 px, the left
  column >= 360 px and the quick-send column >= 300 px, so a pane can never vanish or look "swapped".

## [v0.4.15] - 2026-09-30

### Fixed

- **Dragging the pane divider could collapse or "swap" the receive and send areas (U63)**: the vertical
  splitter allowed a child to be squeezed to zero height, so pulling the handle all the way down made the
  send pane disappear (and the receive pane's contents look scrambled), and the horizontal splitter could do
  the same to the quick-send column. Both splitters are now non-collapsible: the receive pane keeps at least
  170 px, the send pane 190 px, the left column 360 px and the quick-send column 300 px, so dragging always
  stops at a usable layout. (Saved proportions that fall outside those limits are clamped on restore.)

## [v0.4.14] - 2026-09-30

### Changed

- **The receive pane now has one control row instead of two (U35-P2)**: the split / timestamp controls and the
  log toolbar share a single row (the button cluster is right-aligned so the two groups never fight for
  width), and the RX/TX byte counters moved to the status bar where the rest of the global state lives. That
  reclaims roughly 34 px of height plus about 140 px of horizontal room.
- **The send pane is two rows lighter (U35-P1)**: the checksum selector moved onto the format row, and the
  primary Send button now sits at the end of the repeat-send row instead of owning a row of its own, giving
  the data panes back about 70 px of height.

## [v0.4.13] - 2026-09-30

### Changed

- **The dark theme's receive pane was glary (U62)**: alternating RX/TX lines used #e0e0e0 (13.6:1) and the
  bright cyan #8be9fd (13.0:1), which made dense HEX logs tiring to read. The dark palette is softer now -
  payload text #c0c0c0 (9.9:1) and TX data a calm blue #7fb3d5 (8.0:1) - and the timestamp plus direction
  marker are drawn in a dim grey (#7d8590 dark / #6d6d78 light) so the eye lands on the payload instead of
  the prefix. The kind of every fragment (RX / TX / metadata) is stored on its text format, so a theme switch
  re-colours each part correctly.

## [v0.4.12] - 2026-09-30

### Fixed

- **Sends were echoed and counted even when nothing was sent (U61)**: with the port closed, pressing Send (or
  the repeat loop, or a quick-send row) still pushed a TX echo line into the receive pane and increased the
  TX byte / sent counters, so the display claimed data had been sent while the status bar said the send had
  failed. Send actions now check the port first and only echo and count a frame that was actually queued; the
  repeat loop refuses to start without an open port, and a quick-send/sequence payload that cannot be sent
  stops the sequence instead of continuing silently.

## [v0.4.11] - 2026-09-30

### Fixed

- **The Settings button was cramped and pushed against the window edge (U60)**: the top-right button is now
  sized from its own label (minimum 92 px, so the English "Settings" fits with room to spare instead of being
  clipped), sits 14 px away from the right edge inside a small holder widget, keeps a 26 px minimum height,
  and gets a hover background + border in both themes. It is re-measured whenever the UI language changes.

## [v0.4.10] - 2026-09-30

### Fixed

- **HEX lines ran together in the "Off" and "By header" split modes (U59)**: with frame splitting off (or
  in header mode) a received group was appended to whatever was already on the line, so two 10-byte frames
  whose edge digits met collapsed into `... 39 3031 32 ...`, and an RX group could also glue itself onto a
  TX echo line. The receive pane now tracks which direction owns the current line: an RX group following a
  TX line always opens a fresh timestamped line, and a HEX group continuing the current RX line is separated
  by a single space. ASCII mode still runs on without a separator, which is the point of "Off". Header mode
  goes through the same emitter, so its frames - and the leading fragment that continues a frame across
  reads - are separated correctly as well.

## [v0.4.9] - 2026-09-30

### Changed

- **Settings moved to the top-right corner (U33)**: theme, language and config import/export now live in a
  single "Settings" button pinned to the top-right of the menu bar, and the old "View" menu is gone. Low
  frequency options sit in one predictable place instead of competing with the data for a menu row.
- **Receive and send panes are a draggable splitter (U35-P0)**: the data pane and the send pane can be
  resized by dragging; the proportion is remembered in `config.json` when the app closes, and the receive
  pane keeps the larger share by default.
- **The quick-send column can be widened (U47)**: the hard 380-420 px width cap is gone (minimum 300 px,
  maximum whatever the horizontal splitter allows).
- **Explicit Tab order (U54)**: focus walks the five zones in reading order (port -> baud -> open ->
  receive options -> receive pane -> send options -> send -> quick send) instead of widget creation order.
- **Minimum window size (U55)**: 980x600, below which the five zones stop being usable.

## [v0.4.8] - 2026-09-30

### Fixed

- **Received frames were occasionally split in the middle (U57)**: USB-serial adapters hand a frame over in
  several chunks (1-16 ms apart), while the old rule opened a new line as soon as two chunks were more
  than 2 ms apart - below typical USB jitter, so a 5-byte frame could end up on two lines. Chunks are now
  collected by a new `FrameAssembler` (`app/framing.py`) and emitted only after a 10 ms settle window
  (`rx_settle_ms` in config.json), with the line break decided between *flushes*; genuine inter-frame gaps
  (e.g. 130 ms) still produce separate lines. The automatic threshold floor is now 10 ms, and pending data
  is flushed on mode change, clear and port close so the tail frame is never lost.
- **Clear only reset the RX side (U56)**: the clear button emptied the display and zeroed the RX counter
  but left the TX byte count and the sent counter untouched. It now resets display, RX, TX and sent count
  together.

### Changed

- **Quick-send delete is much harder to trigger by accident (U58)**: the destructive button is separated
  from "Send" by fixed spacing, uses a dim style that only turns red on hover (new `#qsDel` rule in both
  themes), and every deletion now offers a 3 s **Undo delete** button in the status bar that restores the
  row with its content, format, delay and original position.

## [v0.4.7] - 2026-09-30

### Fixed

- **The app could freeze solid after a few sends (U52)**: all serial I/O now runs on the worker thread,
  and every blocking path is bounded or cached.
  - Outgoing frames are enqueued (`send()` never touches the port) and written by the worker, so a stalled
    device can no longer block the GUI thread.
  - The port is opened with `write_timeout=0.3`: a driver that never completes a transfer (for example
    hardware flow control waiting for a CTS that never arrives) now raises instead of hanging forever, and
    the app reports "Send timed out: the device is not draining its buffer" persistently in red.
  - Modem status lines (CTS / DSR / DCD / RI) are polled on the worker thread every 200 ms and cached; the
    GUI only reads the cache, so those device ioctls can no longer freeze the interface.
  - The send queue is bounded (64 frames) and reports "Send queue is full" instead of growing without limit
    when the port stops draining.
  - Send history is persisted with a 2 s debounce instead of one `config.json` read + write per click; the
    old path did synchronous disk I/O on every send (painful with real-time antivirus scanning).

## [v0.4.6] - 2026-09-30

### Added

- **Precise HEX validation with actionable errors (U36)**: the HEX parser now accepts `0x` prefixes and
  space / tab / newline / comma / dash separators, and every failure points at the offending character
  ("'Z' at position 5 is not a valid hex digit", "odd length: one digit missing after position 3").
  Full-width characters typed with a Chinese IME get their own message; malformed input is flagged live
  in the send box (red border + tooltip) instead of only after pressing Send.
- **Status-bar message levels (U30 / U36)**: all 16 status-bar messages now go through a single
  `_notify()` exit with three levels - info (auto 5 s), warning (auto 10 s) and error (persistent until
  the next action). Colours follow the active theme and were measured against WCAG AA
  (error `#ff7b72` dark / `#c62828` light, both >= 4.5:1).
- **Actionable serial-open failures (U37)**: opening a port that is denied, busy or missing now shows a
  persistent red message explaining the cause and what to do, instead of a fleeting raw pyserial error.
- **Split-mode slot (U50)**: the receive "Split:" row shows exactly one control that follows the mode -
  an explanatory hint for Off / Auto, the ms box for Manual, the header box for By-header - inside a
  fixed 120 px slot, so nothing shifts when the mode changes. The always-visible grey boxes are gone.
- **Handshake signals grouped by direction (U32)**: DTR / RTS are labelled as outputs (checkable),
  CTS / DSR / DCD / RI as read-only inputs rendered as High/Low text plus colour and a per-line tooltip
  explaining each signal - readable without relying on colour alone.
- **Dark native title bar (U51)**: the Windows title bar now follows the app theme
  (`DWMWA_USE_IMMERSIVE_DARK_MODE` via ctypes, plus Qt 6.8 `styleHints.setColorScheme`), re-applied on
  every theme switch; no-op on Linux / macOS.

### Changed

- **Millisecond inputs unified (U31)**: the repeat interval and the per-row sequence delays are plain
  number fields with the unit in the label ("Interval (ms)") - no spin arrows, no clipped " ms" suffix,
  range-checked with sane fallbacks.
- **Baud rate field widened (U49)**: minimum width raised to 124 px so 1000000 / 3000000 are no longer
  clipped (the editable area grew from 60 px to 83 px).
- **Connection indicator colours (U38)**: the status light is theme-aware and measured >= 4.5:1
  (dark `#7ee787` / `#ff7b72` / `#9a9a9a`, light `#176c2c` / `#c62828` / `#5f5f5f`); previously the
  light theme's green sat at 1.75:1 and was barely readable.
- **Checkbox indicators (U29)**: check boxes are drawn by the stylesheets in both themes (unchecked /
  checked / disabled) instead of the pale system indicator.

### Fixed

- The HEX parser silently swallowed a stray `0x` inside a compact string (e.g. `010x03`); it is now
  reported as an invalid character with its position.
- Whitespace-only HEX input is still treated as empty, but a string made only of separators is reported
  as an explicit "empty content" error instead of being accepted.

## [v0.4.5] - 2026-09-30

### Fixed

- **Theme switch left old text in the previous theme's colours (U27)**: lines inserted while the light
  theme was active kept near-black / dark-blue colours, so after switching to dark the RX lines became
  almost invisible and the TX lines were washed out. The receive pane is now re-coloured whenever the
  theme changes (per-line, TX lines detected by their `-> ` marker).
- **Spin boxes were unstyled (U28)**: the sequence delay and repeat-interval `QSpinBox` widgets fell back
  to the system palette (pale grey with grey text in the dark theme). Both themes now style `QSpinBox`
  (background, border, hover) and ship their own up/down arrow icons; the boxes were also widened so the
  " ms" suffix is no longer clipped.

## [v0.4.4] - 2026-09-30

### Added

- **TX echo in the receive pane (U26)**: sent data is now mirrored into the receive pane so RX and TX
  share one timeline. Direction is shown twice over — a colour (TX blue in light theme, cyan in dark,
  never red) and an equal-width ASCII marker placed *after* the timestamp (`<- ` for RX, `-> ` for TX),
  which keeps HEX columns aligned and does not touch the data itself. Controlled by a "显示发送 / Echo TX"
  checkbox in the receive toolbar (on by default); file transfers and auto-replies do not echo so the log
  cannot be flooded, and echoed lines are still written to the auto-save log.

## [v0.4.3] - 2026-09-30

### Added

- **Command sequence (T13, shipped early)**: the quick-send panel gained a sequence mode — tick
  "序列模式 / Sequence mode" and each row shows a delay box (0-60000 ms). Press Run and the rows are sent
  one by one, each waiting its own delay, with a "Step i/n" indicator; Run turns into Stop at any time,
  the sequence stops when the port closes, and invalid rows are skipped with a message instead of
  breaking the run. Per-row delays are persisted in config.json.

## [v0.4.2] - 2026-09-30

### Changed

- **Receive-area log buttons are easier to find (U25)**: the receive group now has its own toolbar row above
  the text pane — [保存日志 / Save log] [另存为… / Save as…] [自动保存 / Auto-save] [清空 / Clear], with the
  RX/TX counters moved to the right of that row. The parameter row above keeps only splitting / header /
  timestamp controls.

### Added

- **One-click save (U25-D)**: "保存日志" now writes the receive pane straight into `logs/` with a timestamped
  file name and reports the full path in the status bar; "另存为…" keeps the file dialog for choosing a location.

## [v0.4.1] - 2026-09-30

### Added

- **Config import / export (T15, shipped early from the v0.5.0 batch)**: "视图 → 配置 / View → Config"
  offers *Export config…* and *Import config…*. The export writes a JSON file containing a small header
  (`_app`, `_version`, `_exported`) plus the whole config (quick-send list, theme, language, send
  history, auto-reply rules and its on/off flag). Import merges those keys back into config.json and
  applies them immediately — quick-send rows are rebuilt, history and rules reloaded, theme and language
  switched. Plain config.json files are accepted too, and malformed files are rejected with a message.

## [v0.4.0] - 2026-09-30

Feature batch T6-T10.

### Added

- **Send file (T6)**: pick a text / HEX / binary file and stream it in 4 KB chunks with a progress bar,
  size + estimated duration and a cancel button; `.hex` files are parsed line by line.
- **Encodings (T7)**: ASCII / UTF-8 / GBK / GB2312 for both received text and sent text
  (`decode_text` / `encode_text` in app/protocol.py), so GBK Chinese frames stop garbling.
- **Escape parsing toggle (T8)**: `\r` `\n` `\t` `\xNN` are interpreted by default; untick to send the
  literal characters.
- **DTR/RTS control and status lines (T9)**: DTR/RTS checkboxes plus a live CTS/DSR/DCD/RI indicator,
  refreshed every 50 ms from the serial worker.
- **Auto-reply rules (T10)**: a rule editor (match string -> reply string, HEX or ASCII, per-rule enable),
  persisted in config.json; a matching frame triggers the reply automatically.

### Changed

- All new UI strings are bilingual and switch live with the language menu.
- `SerialWorker` gained `set_dtr()` / `set_rts()` / `signals()`.

## [v0.3.0] - 2026-09-30

Feature batch T1-T5 (the "core serial feature set" release).

### Added

- **Full serial parameters (T1)**: data bits (5-8), parity (none/odd/even/mark/space),
  stop bits (1/1.5/2) and flow control (none / XON-XOFF / RTS-CTS). A second toolbar row holds the
  new dropdowns; they are locked while a port is open and applied when it is opened.
- **Repeat send (T2)**: a "Repeat send" checkbox with a 10-60000 ms interval sends the current input
  over and over, shows a sent counter, updates the interval live and stops automatically when the port closes.
- **Append CRLF (T3)**: optional `\r\n` appended on send in ASCII mode (AT-command friendly);
  the checkbox is disabled in HEX mode. The checksum is still computed over the payload, before the CRLF.
- **Receive log to file (T4)**: "Save log" writes the receive pane to a .txt file of your choice, and
  "Auto-save" streams incoming data into `logs/` with a new segment every 2 MB or 30 minutes.
- **Send history (T5)**: the last 50 sent commands are recorded (deduplicated, newest first), persisted
  in config.json and offered in a dropdown above the send box; picking one refills the input.

### Changed

- All new UI strings are bilingual (zh/en) and switch live with the language menu.
- `SerialWorker.open_port()` now passes `rtscts` / `xonxoff` through to pyserial.
- `logs/` is git-ignored (runtime data is never committed).

## [v0.2.16] - 2026-09-30

### Changed

- **New logo (U24)**: the UART-waveform icon was replaced by a simple "SD" monogram — navy rounded
  square, white bold letters and a cyan underline bar. It stays legible down to 16 px (taskbar, Explorer,
  repository avatar), unlike the previous waveform artwork.
- `assets/icon.png` is now 512×512 and `assets/icon.ico` ships six sizes (16/32/48/64/128/256);
  the window, taskbar and EXE icons all use it, and the README now shows the logo in its header.

## [v0.2.15] - 2026-09-30

### Added

- **Bilingual UI (U19)**: the whole interface is now available in Chinese and English. A new
  "视图 → 语言 / View → Language" submenu offers 跟随系统 / 中文 / English; the choice is persisted in
  config.json (`language`) and defaults to the OS locale.
- `app/i18n.py`: small key -> {zh, en} string table plus `tr()`; every visible string (window title,
  menus, group boxes, labels, buttons, combo items, tooltips, placeholders, status bar and log lines)
  is translated and re-applied live when the language changes, without touching serial logic.

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

- README: paragraph layout reworked (Chinese first, English in a collapsed section at the bottom) and
  every external link checked for reachability before being written as a Markdown hyperlink in parentheses

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

- Baud rate: 26 presets (110 ~ 3000000) + editable custom input
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
