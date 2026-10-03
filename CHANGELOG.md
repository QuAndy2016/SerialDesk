# Changelog

## [Unreleased]

### Fixed

- **A failed read of the repeat count can no longer turn into "send forever"**: the repeat loop
  used to fall back to its unlimited value (0) whenever the count field could not be read. It now
  falls back to a single send, the same choice the quick-send rounds already made.
- **The send-area and quick-send tooltips describe the ∞ switch**, in both languages, instead of the
  old "0 = unlimited" rule - that rule is gone, the count field only takes 1..N now.
- **A late update-check answer can no longer raise inside its worker thread**: the check runs in the
  background and can outlive the window it reports to. The answer is dropped when the window is gone;
  before, the error was printed to stderr, which the packaged windowed build does not show.

## [v1.9.8] - 2026-10-03

### Changed

- **The "will send N bytes" hint moved next to Increment** (Andy 2026-10-03): it describes the
  payload the input box holds, so it sits with it now, in the info colour instead of body text.
  The action column (Send / History / repeat) is narrower as a result and hands the width to the
  input box.

### Fixed

- The ∞ switch shows its glyph in full: it was pinned to 24 px while the glyph needs 34, so the
  character was clipped. It is sized naturally now; the redundant "loops" caption paid for the
  width (the panel's minimum window width dropped to 1235 px as a side benefit).
- README screenshots regenerated for the new send area (20 shots).


## [v1.9.7] - 2026-10-03

### Changed

- **"Unlimited" is an explicit switch, not a count of 0** (Andy 2026-10-03, who rightly called
  the old rule out): both the quick-send sequence rounds and the send-area repeat count are now
  plain 1..N fields with an ∞ switch beside them. Ticking ∞ disables the count and keeps going
  until stopped by hand; unticking it makes the count apply. The send-area chip shows "∞" while
  the switch is on.


## [v1.9.6] - 2026-10-03

### Fixed

- **The quick-send loop count defaults to endless** (Andy 2026-10-03): it started at 1 round;
  the panel now opens at 0, shown as ∞.
- **The loop-count steppers work again** (Andy 2026-10-03): its width was computed from the text
  plus a fixed 26 px, which left no room for the arrows - the number was clipped and the up/down
  buttons did nothing. It is sized like the other numeric fields now, and spin boxes / combos
  keep a 28 px floor so their arrows are never squeezed.

### Changed

- Documentation wording: the small popup buttons are called "dropdown buttons" throughout the
  README instead of the misleading word used before, and a corrupted character in the
  repeat-count row is fixed.


## [v1.9.5] - 2026-10-03

### Changed

- **Deleting quick-send rows asks first** (Andy 2026-10-03): the Delete button now opens a
  confirmation - "delete the N selected command row(s)?" - with Cancel as the default button so
  an accidental Enter deletes nothing. The rows are captured before the dialog opens, so nothing
  that happens to the highlight while the dialog is up can turn the confirmation into a no-op.
  The 3-second undo stays.


## [v1.9.4] - 2026-10-03

### Fixed

- **A Delete click that cannot delete now says why** (Andy 2026-10-03, after a Windows report):
  clicking Delete with nothing armed used to do nothing at all - the worst possible feedback.
  The action now reports "nothing selected - click the row first", and it also honours what was
  armed when the button went down, so a press that drops the highlight can no longer turn the
  click into a silent no-op.


## [v1.9.3] - 2026-10-03

### Fixed

- **The quick-send Delete button could not be used after ticking a row** (Andy 2026-10-03): the
  row tick is the sequence's member flag, but it looked exactly like a selection, so ticking a
  row and reaching for Delete did nothing. The tick is now shown only in sequence mode, and
  inside that mode ticking a row also selects it - there the tick *is* the row's primary state,
  so deleting a ticked row works. Outside the mode the click highlight is the selection
  (Ctrl / Shift for several), and a disabled Delete explains itself in its tooltip instead of
  being a dead grey button.


## [v1.9.2] - 2026-10-03

### Added

- **The installer lets you choose where things go** (Andy 2026-10-03): the setup wizard always
  shows the destination page - Inno's default hides it once the same AppId is installed, which is
  why the folder looked fixed on re-install - and a new page picks the default log folder. The app
  resolves the log folder as: portable copy -> `config.json:log_dir` -> the installer's
  `logs_dir.txt` -> the per-user default; a folder it cannot write falls back to the default
  instead of failing to start.


## [v1.9.1] - 2026-10-03

### Added

- **A receive-throughput read-out** (data-path P2): the status bar shows a rolling one-second
  window - RX rate, batches per second, fragments merged per batch, the worst batch cost and
  the fragments dropped while the display was paused. "Can it keep up?" is a number on screen
  instead of a feeling.

### Changed

- **Keyword highlighting is incremental** (data-path P2): freshly received data used to
  trigger a full-document search on every refresh; the pass now only scans the new tail (with
  a lookback so a match straddling the boundary is still found), so the cost tracks the new
  data instead of the whole receive log.
- **The throughput bench is an assertion now** (data-path P2): `tools/rx_bench.py` fails on
  byte loss, on a batch p95 above `--limit-ms` (default 16 ms) and when the pane's block count
  no longer matches the row model. The insert path itself was measured before being touched
  (1 Mbps: p50 1.72 ms, p95 2.05 ms - the target is 16 ms), so it was left as it is instead of
  rewritten for a gain that is not there.
- **UI review L1 closed** (U193): pointer targets sit on a 24 px floor (305 controls under 24x24
  -> 1, a spin box's internal editor), the connection state shows CONNECTING and an open failure,
  the dynamic rows carry accessible names (14 -> 0), and control heights converge to three tiers
  (24/28/32) instead of nine values.


## [v1.9.0] - 2026-10-03

### Fixed

- **The ASCII view keeps line structure** (data-path, Andy 2026-10-03): `\t`, `\n` and `\r`
  arriving from the device were rendered as "." like any other non-printable byte, so a
  three-line `T=24.6C\nVIN=12.12V\n` collapsed into one very long line - a correctness bug
  and a layout performance trap at once. Line control characters pass through now; every
  other non-printable byte still shows as ".". Measured batch cost at 1 Mbps: p50 36.56 ->
  1.70 ms, p95 67.65 -> 2.27 ms.
- **One row model for the pane and the fragment store** (data-path P0): the display and the
  fragment store could disagree about line structure (an embedded newline was one store entry
  but two document blocks). Both derive from `display.rows_from_fragments()` now.
- **The receive loop no longer busy-sleeps** (data-path P1): `sleep(0.001)` became a 5 ms
  blocking read plus coalescing (4096 B or 10 ms of silence), so a fast line cannot overflow
  the driver buffer - "data stops mid-stream" is gone.

### Changed

- **Counters, fragment formats and dropped frames** (data-path P1): status counters coalesce
  on a 100 ms timer, per-kind `QTextCharFormat`s are cached (and invalidated on a theme
  change), and a full TX queue reports a running count instead of a single toast.
- **Log writes are batched** (data-path P1): auto-save flushes in 8 KB / 200 ms windows
  (flushed when a session closes), so a crash costs at most 200 ms of log.
- **Quick-send sequence rounds** (U185, Andy 2026-10-03): the header carries the run count
  (1 = one pass) and the "sent N" hint is smaller.
- **Quick-send delete follows the click** (U186, Andy 2026-10-03): ticking belongs to sequence
  mode; a plain click selects a row for deletion, and the hover tint no longer reads as a
  selection.
- **Quieter dark-theme selection** (U187): the text-selection colour no longer swallows the
  text in dark mode.
- **Settings is an icon-only button** (U188): the connection row got about 60 px back.

- **The send row is one tight block** (U190/U192, Andy 2026-10-03): the repeat interval and
  count moved into a small chip, so the action column drops from 411 px to 200 px and the
  payload box grows from 364 px to 575 px (dead space on its right: 252 px -> 2 px). "Escapes"
  and "Send file" moved into the send-settings chip (now "HEX · none ▾": format / checksum /
  escapes / send file); the row keeps the line-ending picker, and while a file is being sent
  the row still shows the progress, the file info and a Cancel button.
- **The History button reads as secondary, not disabled** (U191, Andy 2026-10-03): a grey
  fill is the app's disabled language, so secondary buttons are outlined now (transparent
  fill, border that lifts on hover). The button still greys out only when there is no history.
- **The receive "More" button matches the row** (U189, Andy 2026-10-03): it uses the same
  border, radius and height as Save log / Clear, with a themed dropdown arrow.


## [v1.8.9] - 2026-10-02

### Changed

- **HEX mode no longer hides the line-ending picker** (U184-A, Andy 2026-10-02): the send
  box's line-ending and escape controls used to disappear in HEX mode, which made the
  option look unsupported. They stay visible and switch off instead, the tooltip explains
  that HEX sends bytes exactly (write `0D 0A` yourself), and the HEX placeholder says the
  same thing. Behaviour is unchanged: only ASCII appends the ending.
- **Selecting a quick-send row works in every mode** (Andy 2026-10-02): the row ticks
  used to be greyed out unless sequence mode was on, so "select a row, then delete" was
  impossible in normal use. Ticking and clicking both select now, and the button reads
  just "Delete" (the old "Delete selected (N)" wording is gone).
- **The line-ending picker now covers quick send** (Andy 2026-10-02): picking CRLF
  (or CR / LF) in the send area also ends every quick-send ASCII row - single sends and
  sequence steps alike. HEX rows stay byte-exact, the same rule the send box follows in
  HEX mode.


## [v1.8.8] - 2026-10-02

### Changed

- **The send box always wraps** (Andy 2026-10-02): the "Wrap input" switch was removed -
  long payloads soft-wrap with a vertical scrollbar by default instead of offering a
  setting to hunt for.
- **The receive pane always wraps** (Andy 2026-10-02): the "Wrap" item left the More menu
  as well; long RX lines wrap by default.
- **One Clear action** (Andy 2026-10-02): the receive area's split button (clear display /
  clear + counters / reset counters, drawn with a grey fill and a dropdown glyph that read
  as a tick) is a single plain "Clear" button now - one click clears the display and the
  counters together, still undoable within 5 s. The duplicate "reset counters" entry left
  the Settings menu and Ctrl+L does the same thing.


## [v1.8.7] - 2026-10-02

### Added

- **Send-history multi-select and batch delete** (U183): the list takes Ctrl/Shift
  clicks, Ctrl+A selects the visible rows (filtered-out rows stay untouched), the
  delete button reads "Delete selected (N)" and greys out with nothing selected, and
  one click drops the whole selection (indices removed high-to-low, metadata cleaned,
  config persisted). Enter/double-click fill is unchanged.

### Internal quality (no user-visible change)

- Documentation: the README download section now describes each release asset
  (installer, portable zip and their checksums), the feature list became five
  categorised tables with worked examples for the `{i}` placeholder, a development
  progress block was added, and the "If Windows blocks it" section was dropped.


## [v1.8.6] - 2026-10-02

### Fixed

- **The send-history list follows the app theme** (Linux/macOS and anywhere the app does
  not switch the native colour scheme): the list had no style rule and inherited the OS
  palette, so it rendered light inside the dark dialog (Windows only looked right because
  the app turns the native colour scheme dark there). Both sheets now style the list's
  background, text and selected row.


## [v1.8.5] - 2026-10-02

### Changed

- **The send pane is compact now** (Andy): about two button rows instead of a tall
  column, so the data area above keeps the space. The actions sit in two tight rows
  beside the input - Send + History (with the payload hint) on the first, the repeat
  toggle + interval + count on the second - with smaller, side-by-side buttons.
- **The send box wraps and scrolls by default** (Andy): long payloads soft-wrap with a
  vertical scrollbar instead of running off the edge. The "Wrap input" switch is still
  there (now on by default) for anyone who wants the old single-line behaviour.

### Internal quality (no user-visible change)

- The send pane's minimum height is 129 px (was 335 px in v1.8.2) and the default
  divider split gives the rest to the receive pane (TX_PANE_MIN_H 190 -> 120).


## [v1.8.4] - 2026-10-02

### Changed

- **Send area is exactly two bands again** (Andy): the settings row on top, then one
  row split left / right - the payload box on the left, and Send / History / repeat
  in a compact column on the right, flush with the box's top edge. The extra caption
  band added in v1.8.3 ("send content") is gone; it had pushed the buttons below the
  box's top edge and made the structure three bands instead of two.


## [v1.8.3] - 2026-10-02

### Changed

- **Send area re-planned** (Andy): the payload box now owns the left side and the
  actions form a column on the right edge - Send, History, then the repeat controls
  (repeat / interval / count) - so the primary button sits right under the hand.
  The "send content (text input)" caption stays above the box, and the payload hint
  moved under the buttons.

### Internal quality (no user-visible change)

- The send pane's minimum height dropped from 335 px to 235 px, because the action
  rows no longer stack underneath the input; the window's minimum width is unchanged
  (1175 px on Linux), and the UI gate (overflow / min-width / contrast) stays clear.


## [v1.8.2] - 2026-10-02

### Added

- **The send area is labelled by its sections** (Andy's annotated layout): a muted
  "send content (text input)" caption sits above the payload box, and a "repeat send"
  caption now opens the loop cluster (stop / interval / count), so the area no longer
  reads as one long run of unlabelled controls.

### Fixed

- **"Delete selected" works after ticking rows** (B2): the row tick (the sequence
  checkbox) and the click highlight looked like the same thing, but only the highlight
  armed the delete button - ticking rows and pressing Delete did nothing. Either now
  arms it, so both gestures delete.

### Changed

- **The quick-send fold toggle moved to the far right of the connection row** (S6):
  directly above the panel's right edge. Beside Settings it read as a Settings submenu
  (a chevron glued to a gear); on the panel's own edge the mapping is obvious.


## [v1.8.1] - 2026-10-02

### Fixed

- **Newly received rows are highlighted again** (B1): the keyword search used to run only
  when the query changed, so data arriving afterwards never matched. The search now re-runs
  (coalesced to one pass ~120 ms after the last fragment) while the highlight bar is visible.
- **The duplicate fold control is gone** (B3): the quick-send panel header carried its own
  fold arrow next to the loop spin box, duplicating the always-visible toggle beside Settings.
  The header one was removed; folding stays on the button beside Settings (and the hover rail).

### Added

- **Sequence "sent N times" counter** (S2): the quick-send header shows how many sequence
  rounds have been sent, cleared when a new run starts.
- **The row being sent is highlighted** (S3): while a sequence runs, the current row gets an
  accent border so it is obvious which command is on the wire.

### Changed

- **Spin-box arrows are readable at last** (B4): up/down arrows went from 8x5 px inside a
  16 px button to a 14x14 px glyph in a 22 px hit target (all spin boxes: loop count, repeat
  interval, increment parameters, split sizes).
- **The clear split button's dropdown arrow matches** (S1): 8x5 -> 14x14 px, with a 22 px
  menu button.

### Internal quality (no user-visible change)

- **One gate run executes the suite once**: `tools/dev_gate.sh` now calls the review battery
  with `--no-coverage --no-dynamic` and lets `tools/check_ui.py` own the single pytest +
  coverage run (previously pytest ran three times and `check_ui.py` twice per gate). CI gate
  time drops from ~479 s to ~200 s.
- **Gate results are stamped per tree**: `dev_gate.sh` writes a HEAD+diff hash on success and
  the pre-commit hook skips an identical tree, so "run once, then commit" is one gate run.


## [v1.8.0] - 2026-10-02

### Added

- **Auto-increment placeholder in the send box** (U180): put `{i}` (or `{i:N}`,
  `{i:N:le}`) in the payload and SerialDesk substitutes a running counter before
  sending. The new "Increment" chip opens a panel for enabled / start / step / width /
  endianness / radix / wrap / reset. Use `\{i}` to send a literal `{i}`. History keeps
  the template only, and the checksum follows the substituted frame.
- **Persistent keyword highlight bar** (U181): the find bar is now an always-on
  highlight bar (input highlights as you type instead of jumping); Enter / prev / next
  still navigate. A case-sensitivity switch was added and persisted.
- **Named quick-send commands with notes** (U182): each quick-send row is two lines - a
  name line (edit inline) plus the command-content line; a row right-click offers
  "edit command note". Name and note are saved with the row and shown as its tooltip.

### Changed

- **Find label renamed to "Highlight"** to match the always-on behaviour.
- **Old quick-send configurations migrate losslessly**: rows without name / note fields
  load with empty defaults instead of being rejected.

### Internal quality (no user-visible change)

- U180 logic lives in a pure `app/increment.py` layer (placeholder parsing, render,
  next value, wrap/stop) with its own unit tests.
- Row payload / restore / load / save all carry name + note; receive-row structure
  assertions updated for the two-line layout.


## [v1.7.0] - 2026-10-02

### Added

- **Sequence loop count** (U170): the quick-send sequence can repeat the whole run
  a set number of rounds (0 shows ∞ = keep going until stopped).
- **Repeat-send count** (U171): the repeat-send loop can stop after a set number of
  sends (0 shows ∞ = keep going until stopped).
- **Send-box soft-wrap switch** (U165): the input can wrap long content; off by
  default so a long HEX string still shows as one line.
- **Clear split button** (U169): one click clears the display; the menu also offers
  "clear display and counters" and "reset counters" (previously buried in Settings).
- **Port dropdown shows the full device name** (U172): the closed box stays short
  ("COM5"), the popup lists "COM5 — USB-SERIAL CH340 …".

### Fixed

- **"RX only" leaked the TX markers** and glued them onto the previous RX line (U176).
- **"TX only" hid the TX timestamps** (U177). Both were the same defect: the marker
  fragments carried no side, so the filter misclassified them.
- **Checkbox tick was drawn in the top-left corner**, not centred (U166) - the icon
  generator drew every glyph at fixed coordinates without centring it.
- **Fold arrows were off-centre single chevrons** (U174); they are centred double
  chevrons (<< / >>) now.
- **The settings gear read as a ring** (U173): the old radii ran past the canvas and
  clipped the teeth.

### Changed

- **Receive row re-plan** (U178/U179): the "Echo TX" checkbox duplicated the
  view-filter dropdown, so it is gone (TX is always captured); "Auto-scroll" moved
  back into the row (it is high frequency); "Save as…" is now "Save log as…".
- **Panel title** has an accent bar and title weight (U167).
- **Icons regenerated** on the centred 16x16 grid; checkbox indicator aligned to the
  asset size; fold-control icon size raised from 8x12 to 14x14.

### Internal quality (no user-visible change)

- Receive fragments now carry a 4-way kind (RX/TX payload, RX/TX marker) and the
  view filter is a pure, unit-tested function.
- Port dropdown grew a small `ui/port_delegate.py` (kept separate to avoid a circular
  import between the row builder and the port controller).


## [v1.6.3] - 2026-10-02

### Added

- **Receive-row More menu** (U164): right-click a receive row for copy / re-send / clear helpers
  without leaving the row; the split slot next to it was made narrower to match.
- **Split clear / reset counters** (U163a): clear one pane or zero the RX/TX counters independently.
- **RX/TX view filter** (U163b): show all rows, RX only, or TX only.
- **Column HEX view** (U163c): switch the receive area between line and column-aligned HEX layout.
- **Log folder quota** (U163d): the log directory is capped, oldest files pruned first.
- **Uninstall prompt** (U163e): the app can hand off to the Windows uninstaller.
- **Soft-wrap toggle** (U162) plus clean / line / raw copy semantics, so what you copy matches
  what you see.
- **First-run examples** (U128): a couple of ready-made lines are pre-filled so a new window is
  not empty.
- **Byte-stream split modes** (B3): the incoming stream can be split on a delimiter or fixed
  length, wired through a pure framing layer with its own tests.

### Fixed

- **Fold button paints its arrow on first open** (U161).
- **Shadowed eventFilter** removed (A5).
- Long-line tooltip added for truncated rows.
- **CI min-width gate** now takes a per-platform baseline, so the Linux runner no longer
  reports false overflow against the real 1366 px screen bound.

### Changed

- **UI batch 4**: colour convergence (U125) and a unified 16x16 icon grid (U126).
- Empty-row placeholder, RX context menu, find count + highlight, pause display and
  long-line no-wrap (U160 batch); row hover and keyboard reach on rows.
- Title weight unified across panels.

### Internal quality (no user-visible change)

- **Windows installer build fixed**: the `[Code]` section added in U163c-e used `;`
  comments, which the Inno Setup Pascal compiler rejects (`'BEGIN' expected`); switched to
  `//`. This only affected the installer packaging step, not the app itself.
- Broad `except` blocks narrowed (A3); dialog smoke tests added (A4).
- Review battery / UI gate threaded through a single `tools/dev_gate.sh` entry point.


## [v1.6.2] - 2026-10-01

### Added

- **Open logs folder** (config menu): one click opens the log directory in the file manager.
- **Manual update check** (settings menu, "Check for updates now"): always reports back -
  a newer version opens the download page, otherwise it tells you "up to date" or that the
  check failed (network). The startup check keeps its quiet behaviour.
- **Remember the last port**: the port that opened successfully is saved and pre-selected
  on the next launch (only when it still exists).

### Changed

- **UI batch 3**: type scale, metered palette budget, echo colour split from the brand
  colour, unified icons.
- **English copy is plural-safe**: strings no longer read "1 entries", "1 bytes" or
  "1 times"; they use unit-agnostic phrasing ({n} B, sent x{n}, {n} total, {n} pending).
- **Import hygiene (internal)**: 14 controller files had their top-level imports split
  into separate blocks by an early migration tool; they are merged back (56 statements
  removed, import region only) - no behaviour change.

### Internal quality (no user-visible change)

- Docstrings and parameter annotations for every public function (478/478 annotated).
- The nine functions over 60 lines were split into named builders (all <= 60 now).
- Dead i18n keys removed (12); the review battery no longer misreports keys referenced
  indirectly (shortcut table, tooltip dicts) as unused.
- The review battery went from 249 informational findings to 14 (pre-existing broad
  excepts only, each justified in place).


## [v1.6.1] - 2026-10-01

### Fixed

- **Repeat send had silently disappeared**: the "Repeat send" toggle and its interval box were built and filled in,
  but the line that attached them to the action area was lost when that area became a single-line toolbar (v1.5.1).
  Both widgets ended up with no parent, so they were never drawn - no error, no placeholder, the feature was just
  gone. They are back in the toolbar (`Send | History | Repeat send [Interval (ms): 1000]`), and a smoke test now
  asserts that every send-area control is parented and visible instead of trusting the code.

## [v1.6.0] - 2026-10-02

### Changed

- **The interface now runs on a colour-token system and every palette pair meets WCAG**: the 223 hard-coded colours
  in the stylesheet became 33 dark / 35 light tokens rendered from templates, and all 22 known contrast violations
  were fixed - disabled text, hover borders, and checkbox rings that were drawn in exactly the same colour as their
  fill. The contrast gate is strict from now on: a new violation fails the build instead of being recorded as debt.
- **The window was split into eighteen modules (2712 -> 645 lines of `ui/main_window.py`)**: the window keeps the
  wiring, while the regions, the menu, retranslation and twelve controllers (log, receive, send, connection,
  parameters, layout, configuration, actions, dialogs, startup, update) own the behaviour. Nothing user-visible is
  meant to change; the split exists so a fix lands in one file instead of a 2700-line one.

### Added

- **Quality gates that run without being remembered**: a review battery plus a UI gate (contrast, eight-state
  overflow audit, tests) run in CI, in a pre-commit hook and inside the test suite itself. Test count went 64 -> 100
  and coverage 9% -> 66%, with the extracted logic covered before any of it moved.

### Fixed

- **Switching language could raise an error**: a stale call left behind by the refactoring only executed on a live
  window (language/theme switch), which the audits never exercised. It is now covered by a smoke test.


## [v1.5.2] - 2026-10-01

### Fixed

- **The send box wrapped a single payload across several lines (U130)**: a 400-character command is one line of data, so
  wrapping it in the middle - sometimes inside a value - misrepresented it. The input no longer wraps and scrolls
  horizontally instead; wrapping moves to an explicit option.


## [v1.5.1] - 2026-10-01

### Fixed

- **Ctrl+A and Delete were stolen from every text field (U129)**: the quick-send panel installed its keyboard
  handling application-wide, so Ctrl+A in the send box selected the panel's rows (and copied the wrong thing), and
  Delete in any text field deleted quick-send rows. The shortcuts now only fire when the focus is inside the panel
  and not in a text field.
- **The input box was stuck at one line (U129)**: the action column beside it consumed nearly the whole pane, leaving
  the input ~27 px. The send area is regrouped - payload options on top (line ending and escape moved up next to the
  other options), the input owning the middle at full width (72 px at the default pane, 266 px when the pane is
  dragged), and the actions (Send / History / Repeat) as a toolbar underneath - and the input wraps long text and
  never goes below three lines.


## [v1.5.0] - 2026-10-01

### Added

- **Update check (U127)**: SerialDesk now quietly asks GitHub for the latest release - 2.5 s after launch, on a worker
  thread, 5 s timeout, standard library only. When a newer version exists the status bar mentions it once and Settings
  gains a "Version X is available…" entry that opens the download page. Settings also has "Check for updates at
  startup" if you would rather not; nothing about the machine is sent, and being offline, rate-limited or blocked all
  fail silently. Version handling is pinned by tests (`tests/test_update.py`), so the comparison stays honest without a
  network.


## [v1.4.0] - 2026-10-01

A quality pass: accessibility, diagnostics, one readable counter, and the shortcuts nobody could find.

### Added

- **A visible keyboard focus ring (U122)**: the stylesheet had no `:focus` rule at all, so keyboard users could not
  see where they were (WCAG 2.4.7). Inputs, combos, text areas and buttons now take a tinted focus state, and every
  control got an accessible name (tooltip first, then its label) so screen readers announce something useful.
- **Diagnostics you can send in a bug report (E3)**: `main.py` installs `faulthandler` plus an `excepthook` that
  append to `logs/lasterror.log`, and the About box has a **Copy diagnostics** button (version, OS, Python/PySide6/
  pyserial, port, formats, log folder, error-log path).
- **A shortcuts reference (U123)**: all twelve shortcuts, from the single table that also builds them, in
  Settings → Keyboard shortcuts.
- **An empty-state hint**: an empty receive pane now says that data will appear once a port is open.

### Changed

- **One counter in the status bar (U124)**: "已发送 N 次" and "RX / TX" were two widgets competing with the connection
  indicator; they are one readout now - `TX 12 次 · 39 B | RX 512 B` - in a monospace face, so the numbers no longer
  shift the layout as they change.

### Fixed

- **CI never ran the tests (E1)**: the build workflow packaged whatever was pushed, so a red test suite could ship an
  installer. `python -m pytest -q` now runs before packaging and fails the build.


## [v1.3.0] - 2026-10-01

A space-and-interaction pass over the quick-send panel and the send area.

### Changed

- **Quick-send rows are one line again (U118)**: format and delay moved into a small chip at the trailing edge
  (`HEX · 500 ms` - click it to change either). The row is ~31 px instead of ~56 px, so ten rows no longer scroll, and
  the command keeps the whole width.
- **The send options collapsed into a chip (U121)**: "格式: HEX" + "校验: 无" and their two labels used ~200 px of a row
  that had nothing else in it; they are now one chip ("HEX · 无") with a popup. The "N bytes to send" hint moved from
  the far end of that row to just under the input it counts.
- **The input box owns the send area's vertical space (U119/U121)**: it is one line at the default pane height and grows
  when the pane is dragged, when the window grows, or when HEX mode hides the line-ending row - measured 37 px at the
  default pane and 287 px after dragging it tall, instead of a fixed 30 px with the rest left blank.
- **The actions column sits on the options row's baseline (U119)**: it used to float in the middle of a tall pane.
- **Folding the quick-send panel costs nothing now (U120)**: the 28 px rail is gone at rest. There is a fixed toggle
  button beside Settings (with the usual `Ctrl+B` and menu entry), and the rail reappears when the pointer is near the
  window's right edge.

### Fixed

- **Selecting rows to delete was single-row only (U118)**: `删除选中` takes the usual list semantics now - click to
  select, Ctrl+click to add or remove, Shift+click for a range, Ctrl+A for all, Esc or a click outside to clear - and the
  button carries the count (`删除选中 (3)`). Deleting several rows undoes as one batch.
- **Only the row's background or its text box counted as a click on the row (U118)**: the whole row is the hit target
  now, so clicking its checkbox, chip or send button selects it too.


## [v1.2.1] - 2026-10-01

### Fixed

- **The send area could be laid out below its own rows (U117)**: the pane floors were measured once at startup, so
  anything that changes the metrics afterwards - a display at 125 % / 150 %, a window moved between monitors, or a
  format switch that shows the line-ending row - left the splitter free to squeeze the send pane until its rows
  overlapped. The floors are recomputed on a screen or DPI change, and the send pane's floor now comes from its layout
  (`minimumSize().height() + 10`, at least 120 px) instead of a hardcoded number.


## [v1.2.0] - 2026-10-01

A design pass over the send area and the quick-send panel, driven by a review of the shipped UI.

### Changed

- **The send area no longer grows with the window (U111)**: the vertical splitter gave the send area 40 % of every
  extra pixel of height, although the send area is one input box. Stretch is data-first now (`[560, 170]`, send floor
  120 px), and the input box is one line high by default and grows to four as you type - measured: 190 px of send area
  at both an 800 px and a 1000 px window, and a 30 px input for one line instead of 90 px.
- **The line-ending option says what it does (U112)**: "追加 \r\n" was escape notation in a label. It is a picker now -
  None / CR / LF / CR LF - defaulting to None so upgrading behaves exactly as before, with the old `crlf` boolean
  migrating automatically. Verified byte-for-byte: `AT` + CR LF sends `AT\r\n`, LF alone sends `AT\n`.
- **Settings is a real control (U110)**: the app-level entry was a borderless text label. It now has a gear icon, a
  bordered 32 px hit target, hover/pressed states, a divider that separates it from the connection parameters, and the
  Ctrl+, shortcut. The menu gained section headings and the destructive "Restore default settings" moved to the bottom
  under its own heading.
- **One control height across the connection row (U114-D4)** and a shorter send-box placeholder with the examples moved
  into the tooltip (D6).
- **The repeat interval box is sized to its content (U113)**: 112 px for a four-digit number became 60 px.
- **Quick-send panel**: the sequence status text left the toolbar (D1, it reports to the status bar now), the add button
  dropped to secondary weight (D3), the property line lines up with the text box (D5), row ticks grey out when sequence
  mode is off (D9), and the destructive delete sits apart from Run (D10).

### Fixed

- **A selected quick-send row stayed selected forever (U115)**: the highlight and the enabled "delete selected" button
  survived clicks anywhere else in the window. The selection is a transient state now - clicking outside (or on the
  panel's empty area), pressing Esc, folding the panel or starting a sequence drops it, while clicking the delete button
  itself keeps it.
- **The row highlight no longer uses the TX blue (U114-D7)**: "sending" and "selected" shared one colour; the selection
  is neutral now.


## [v1.1.0] - 2026-10-01

### Added

- **The quick-send panel folds both ways and stays visible while folded (U106)**: folding used to leave nothing behind - the
  only way back was a menu entry or Ctrl+B. The header now carries a themed icon button (24x24 hit target) at the trailing
  edge, and folding leaves a labelled 28 px rail you can click to bring the panel back.
- **Quick-send rows are two lines now (U105)**: the command gets the whole row (measured 238 px, up from about 105 px) and
  the row's properties moved to a second, indented line, where the delay field finally says `ms` (U104).

### Fixed

- **Sending from the quick-send panel never moved the send counter (U103)**: only the Send button incremented
  "已发送 N 次" while the TX byte counter counted every path, so the two numbers disagreed on screen (ten 5-byte sends read
  as "10 times" next to "TX: 500 B"). Quick send, the repeat loop and sequences now count too.
- **Folding the panel wiped the settings (U109)**: `save_config()` replaced config.json instead of merging it, so persisting
  the folded flag silently dropped the theme, language, log folder, auto-save settings and history. It merges now.
- **The idle file-progress bar read as a divider (U108)**: it stays hidden until a transfer actually starts.


## [v1.0.0] - 2026-10-01

**First stable release.** SerialDesk is feature-complete for everyday embedded work and
moves into long-term maintenance from here. Everything below is in the installer and the
portable zip; nothing needs Python.

### Serial

- 26 baud presets plus free text, data / parity / stop bits, hardware and software flow control
- HEX and ASCII views, HEX + ASCII dual view, framing (off / by baud rate / manual ms / by header)
- Timestamps, and a receive area that echoes what you send with a direction marker and its own colour

### Send

- Quick-send bank (up to 99 rows) with sequence mode and per-row delay, repeat send with an interval
- Checksums on send: CRC16-Modbus, CRC16-CCITT, CRC32, SUM8
- File transfer with progress, encodings (UTF-8 / GBK / ...), escape parsing, append CRLF
- Auto-reply rules, editable and persisted; send history with filter, and an undo window for deletions

### Reliability

- All serial I/O on a background thread, so the UI never freezes; auto-reconnect with backoff
- Receive logs: save a snapshot, or auto-save with a size and time limit, into one folder you choose

### Packaging and UI

- Single-file Windows installer and a portable zip; `portable.txt` keeps everything beside the exe
- Data lives in `%APPDATA%\SerialDesk` by default, and **settings from builds older than v0.6.0 are now migrated automatically** (U102) instead of silently resetting
- Dark / light / follow-system themes, Chinese / English UI, collapsible quick-send panel, connection and signal-line indicators

### Docs

- Bilingual README with an English first screen, screenshots, an "if Windows blocks it" walkthrough, and a bug-report issue form plus CONTRIBUTING

### Known limits

- Windows is the only packaged platform; the exe is unsigned, so SmartScreen warns on first run
- Waveform view (pyqtgraph) and TCP/UDP debugging are planned for after 1.0 and will be prioritised by user feedback


## [v0.15.0] - 2026-10-01

### Added

- **Settings survive the data-root move (U102)**: builds before v0.6.0 kept `config.json` beside the executable; the data
  root now lives in `%APPDATA%\SerialDesk` (or next to the exe when a `portable.txt` is present), so upgrading users were
  silently starting from defaults. On first run a new build now copies a legacy `config.json` found beside the exe into the
  new location. Source runs, portable copies and already-migrated installs are untouched.

### Verified

- **The status bar already carries the connection summary**: the connection indicator reads `已连接 COM3 @ 115200` once a
  port is open, so the open item "add a port@baud summary to the status bar" needed no code and is closed.

## [v0.14.0] - 2026-10-01

### Fixed

- **A divider drag could push labels out of their pane (U101)**: the left column had a hard-coded 360 px floor (U63) although its
  rows needed up to 805 px in English, so dragging the horizontal divider left squeezed the send and receive rows until the
  right-most controls were clipped. The column's floor is now measured from the panes' own measured floors (recomputed on a
  language switch), so no divider position can clip a row.
- **Every text control now pins its minimum width to its own label (U101)**: buttons, checkboxes, labels and the two option
  combos set their minimum to their current `sizeHint`, and buttons keep a fixed height, so a label can no longer be squeezed
  or truncated by a narrow column. Measured (label / width): 发送 56/104, 循环发送 82/82, 保存日志 82/82, 清空 56/56,
  Send 63/104, History (0) 99/104, Repeat send 112/112.

### Changed

- **The shrink order is a rule now**, not a judgement call: flexible items give way first (the input box, elidable labels and
  hints), then secondary controls are hidden or moved into a menu (as U50/U98/U99 already do), and only then is a container's
  floor raised. The font never changes with the window size - that is what breaks the type scale and the readability.

## [v0.13.1] - 2026-10-01

### Fixed

- **The connection bar stayed English in the Chinese UI (U100)**: "Port:" and "Baud:" were hard-coded labels rather than
  translation lookups, so switching to Chinese left English sitting in front of the two boxes. They now read 端口: and
  波特率: and follow the language switch like every other label.

## [v0.13.0] - 2026-10-01

### Changed

- **The send area is two blocks instead of three (U99)**: the input row now carries the text box on the left and one
  action column on the right - Send and History on the first line, the repeat controls right below them - so nothing
  competes with the box for width.
- **File sending moved up beside the checksum (U99)**: the Send file button, its progress bar and the file message
  now sit on the options row, immediately right of the checksum dropdown.
- **The payload hint moved to the top-right corner and is one size smaller (U99)**: "N bytes to send" is rendered at
  12 px (via `QLabel#payloadHint`) at the right edge of the options row, where it reads as an aside instead of
  competing with the controls.
- **The text decorations (Append \r\n / Escapes) moved into the action column (U99)**: measured in English they
  pushed the minimum window width up by about 100 px while they shared the options row, so they now form the third
  line of the action column - the fallback recorded in the plan. They still disappear in HEX mode.
- The send group's floor drops from 170 to 140 px now that one row is gone, and the English label "Parse escapes"
  is shortened to "Escapes" (the tooltip keeps the full explanation).

## [v0.12.0] - 2026-10-01

### Changed

- **The send area is grouped instead of being one flat stack (U98)**: the first line now reads "input first, text
  decorations second" - format and checksum, then a clear gap, then Append CRLF and Parse escapes. Send and History
  are no longer stretched to the height of the input box: Send stays the default button and History is a quieter
  secondary one, both the same width, with a thin rule separating the input from the actions.
- **Repeat send is a toggle, not a checkbox (U98)**: it starts and stops a process, so it now reads "Repeat send"
  and switches to "Stop repeat" while running, instead of a checkbox standing in for an action.
- **Repeat and file sending share one action row (U98)**: two short rows became one, which pays for a taller input
  box - its minimum went from 60 to 90 px and the send group's floor from 190 to 170 px.

### Added

- The **sent counter moved into the status bar**, next to the RX/TX byte counts, so the send area is left with
  three parts only: options, input, actions.

### Removed

- **The auto-reply switch and its Rules button left the send area (U98)**: they are receive-side settings, so they
  now live in Settings as "Auto-reply" (checkable) and "Auto-reply rules...". In HEX mode Append CRLF and Parse
  escapes are hidden rather than shown greyed out, because they only mean something for ASCII text.

## [v0.11.0] - 2026-10-01

### Changed

- **The receive controls are one row, not two (U96)**: split mode, the timestamp switch, both display switches and the
  log actions now share a single line, which hands the pane back roughly 34 px of height. Clear still sits alone at
  the far right so it can never be hit while reaching for a switch.
- **The timestamp is a switch with a single format (U96)**: the four-option dropdown ("None", `HH:MM:SS`,
  `HH:MM:SS.mmm`, `yyyy-MM-dd HH:MM:SS.mmm`) is gone. Tick the box and every receive line starts with
  `[04:02:10.456]`; the choice is remembered in the config (`timestamp_on`, on by default) - previously it was not
  saved at all and reset on every start.
- **One log folder for everything (U97)**: the settings entry is now "Log saving settings..." with a *Save location*
  group on top and an *Auto-save* group below it, because the folder is shared by the one-click Save log, the start
  folder of Save as... and auto-save. Save as... now opens in the configured folder instead of the default one.

### Removed

- **The duplicate Auto-save switch in the receive row (U97)**: auto-save has a single owner now, the settings dialog,
  so the two places can no longer disagree. The unused `log.autosave` strings went with it, and the dialog note now
  explains the shared folder and how the two file names differ (`serial_...` for auto-save, `serial_RX_...` for a
  manual snapshot).

## [v0.10.0] - 2026-10-01

### Changed

- **The send-history popup got the P0 pass**: the list is drawn in a monospace font so hex strings line up and can be
  compared at a glance; a line above it says how many entries there are ("4 entries · newest first"); the hint reads
  "Double-click or Enter to recall · Delete removes the entry · Esc closes"; "Delete this entry" is now a quieter,
  secondary button, while "Clear the history" sits apart from the other actions and needs a second click to confirm;
  and the dialog remembers the size you dragged it to (`history_dlg_size`).

### Added

- **Send-history P1 pass**: every row carries secondary metadata on the right - format (HEX/ASCII), payload size in
  bytes and a relative age ("3 min ago"); a filter box above the list narrows rows as you type, case-insensitively,
  and the count line switches to "2 of 4 match" while a filter is active. Selected rows now use the project accent
  colours and hold >=4.5:1 text contrast in both themes.

### Fixed

- **Dialogs were not themed**: `QDialog` had no background rule, so over a dark palette the send-history window could
  keep a light background. Dark and light QSS now both style `QDialog`, matching the main window.

## [v0.9.1] - 2026-10-01

### Fixed

- **One button in the history popup showed a raw key**: its delete button referenced a translation key that did
  not exist, so it read "tx.history.del" instead of "Delete this entry / 删除此条", and the empty-state label had
  the same problem. Both now use the keys that already existed, and a sweep over every translation call in the
  codebase (230 call sites, 251 keys) confirms no other string can fall back to its key.

## [v0.9.0] - 2026-10-01

### Changed

- **The receive controls are grouped instead of being one flat line (U95)**: the first row now carries the stream
  settings (Split, Timestamp) on the left and the two display switches (Echo sent data, Auto-scroll) on the right,
  with the flexible space sitting *between* the groups rather than as a hole inside one of them; the second row
  carries the log actions (Save log, Save as..., Auto-save) on the left and keeps Clear alone at the far right, so
  the destructive action can no longer be hit while reaching for a switch. At full screen the rows no longer leave a
  large empty area on the right-hand side.
- **The split hint no longer repeats the dropdown (U89)**: the field beside Split used to show a plain-text copy of
  the selected mode ("Auto (by baud)"), which read like stray wording and looked clickable. That field now appears
  only for Manual and By-header mode, where it actually holds a value.

## [v0.8.0] - 2026-10-01

### Changed

- **Tighter control rows (U92)**: the receive and send control rows stood 44-47 px tall for widgets that only
  need 26-29 px - Qt's default 9 px top/bottom padding on the row layouts made up the difference. Every control row
  is now 29-33 px, which hands the log about 25-50 px of extra height (285 px at the default window size, 645 px
  maximised) and lets the send pane start lower.
- **The HEX hint lists all three accepted spellings (U93)**: the send box now shows
  "e.g. 01 03 00 00 | 0x01,0x03 | 01-03-00-00" instead of a single example, so the 0x-prefixed and the
  comma/dash-separated forms are actually discoverable.

### Fixed

- **The frame-header box no longer pretends "fw:" is a value (U94)**: it starts empty (it used to be pre-filled with
  "fw:", which read like a required format and silently enabled header-based splitting), and its hint follows the
  send format - "e.g. AA 55 or 0xAA,0x55" in HEX mode, "e.g. $GPGGA" in text mode. The tooltip now explains that
  the header is a byte sequence which starts a new line and accepts space, 0x, comma and dash separators.

## [v0.7.1] - 2026-10-01

### Fixed

- **Restoring the defaults no longer aborts half-way (U91)**: v0.7.0 removed the history label from the window but
  left one line referencing it in the translation routine, so switching language - and therefore "restore defaults",
  which switches to the system language first - raised an error before it could clear the send history. The leftover
  reference is gone: restore defaults now clears the history (list, button state and the saved config), and switching
  between Chinese and English works again.

## [v0.7.0] - 2026-10-01

### Added

- **The send history is a popup now (U87)**: it no longer takes a row of its own - a compact "History (12)" button
  sits beside Send and opens a non-modal list of recently sent commands. Double-click (or Enter) recalls one into the
  send box, Delete removes the highlighted entry, and explicit Use / Delete / Clear all / Close buttons are provided.
  Ctrl+Up and Ctrl+Down walk the history straight from the input box (Ctrl on purpose - the box is multi-line, so the
  bare arrow keys must keep moving the caret); stepping past the newest entry restores what was typed before.
- **The quick-send panel folds away (U88)**: a button in its header, Ctrl+B, or the new "Show quick-send panel" entry
  in the Settings menu folds/unfolds it, and folding hands the log about 357 px of width. The state is remembered.
- **Format-specific send hints (U86)**: the send box shows "e.g. 01 03 00 00" in HEX mode and "e.g. AT+VERSION?" in
  text mode, switching with the format and with the language; the full format rules stay in the tooltip.

### Changed

- **The port list shows names (U83)**: the dropdown lists `COM5` instead of `COM5 [USB Serial Port (COM5)]`, with the
  full description in the tooltip of the control and of every entry, so the port name is never truncated.
- **One control for the wire format (U84)**: the `8N1 - None - ASCII` summary is now the button that opens the
  port-settings dialog, replacing a separate label plus button. The minimum window width drops by about 40 px
  (roughly 1016 -> 981 px in Chinese) with every label left complete.

### Fixed

- Rows can no longer be squeezed by a divider drag, and row widths are measured from the layout itself, so the
  numbers follow the current font, DPI scale and language (U81 follow-up).

## [v0.6.17] - 2026-10-01

### Fixed

- **The size floor is now enforced per pane, not once for the window (U81 follow-up)**: the previous check derived a
  single window minimum from whichever row happened to be widest, so a divider drag could still squeeze the rows of
  the pane on the other side (the quick-send column could be dragged wide and the receive rows paid for it). Each
  pane now carries its own hard minimum, computed from its widest control row, so no divider position can compress a
  row.
- **Row measurements use the layout's own minimum**: adding up the widget widths by hand missed a few pixels per
  combo box, which left rows marginally too narrow; the layouts now report their minimum size directly, and they are
  re-activated before measuring so the numbers follow the current font and translation (Chinese floor 1016-1043 px,
  English 1092-1119 px here).
- Verified across Chinese/English x three starting window sizes: at the computed minimum, with the quick-send column
  dragged wide, with the receive pane squashed, and maximised - no row overflow and no widget squeezed below its
  content in any combination.

## [v0.6.16] - 2026-10-01

### Fixed

- **Restoring the defaults restores the data-first layout too (U82)**: "restore defaults" used to write fixed splitter
  numbers, so on a maximised window the proportions were scaled up instead of being re-measured - the log pane ended
  up far smaller than it needed to be. It now re-applies the data-first rule at the current window size: at 1920x1040
  the receive pane takes 79% of the height (a 617 px tall log view) and the left column 81% of the width, with the
  quick-send column back at its minimum width.
- **The restore message no longer crowds the status bar**: it reads "Defaults restored (the previous config was
  backed up)" and the full backup path moved into the status bar tooltip, so a long Windows path cannot push the
  RX/TX counters around at small window widths.

## [v0.6.15] - 2026-10-01

### Fixed

- **The window minimum is now measured, not guessed (U81)**: the previous 1060 px floor was measured with one
  font at one scale factor, so a different Windows DPI setting or a longer translation could still squeeze the
  control rows and make them overlap. The minimum is now derived at start-up (and after a language switch) from
  the widest control row at the *current* font and translation, plus the window chrome - 1067 px for Chinese and
  1125 px for English here - and the window refuses to shrink below it.
- Verified with a stricter audit than before: besides "does the row fit", every visible label, button, checkbox and
  combo box must receive at least its content width and height. Checked at the computed minimum and at 1100 / 1200 /
  1366 / 1024 / 900 px wide (the last three requests are clamped): no overflow, no clipped widget.

## [v0.6.14] - 2026-10-01

### Changed

- **Smaller boxes where they were oversized (U80)**: the per-row delay box in the quick-send panel is now sized to its
  content (76 -> 50 px, right-aligned, tight padding) and the timestamp-format selector in the receive row no longer
  stretches to fit its longest entry (235 -> 171 px; the dropdown still lists every format in full) - which also hands
  roughly 64 px back to the narrowest control row.
- **The sequence number is a corner badge (U80)**: in sequence mode the order of a ticked row is drawn as a small
  number (9 px) pinned to the top-right corner of its checkbox instead of an 11 px bold label sitting in the row, so
  it no longer looks like a heavyweight element or pushes the row wider.

## [v0.6.13] - 2026-10-01

### Changed

- **The data area gets the room by default (U79)**: the send pane and the quick-send column now start at their
  minimum sizes (190 px tall / 332 px wide) and every spare pixel goes to the receive pane, which lands at roughly
  68% of the vertical space and 69% of the width at the default window size (measured: 404/594 px and 807/1160 px,
  with a 280 px tall log view). Drag a divider and your proportions are stored and honoured from then on; if the
  stored numbers are exactly the old defaults (i.e. the divider was never dragged), they are upgraded to the new
  data-first proportions on start.

## [v0.6.12] - 2026-10-01

### Fixed

- **Controls overlapped once the window was narrowed (U78)**: a row-by-row audit (minimum width required vs width
  available, at several window sizes) showed the connection row needed 1124 px and the merged receive control row
  1121 px while the window minimum was only 980 px - so shrinking the window overlapped and clipped controls.
  - The receive controls are two rows again (parameters 618 px, actions 503 px), which is what the space actually
    needs;
  - the connection row was trimmed (port 220 -> 170 px, baud 124 -> 112 px, the parameter summary is capped at
    120 px and elides), bringing its worst case to 1059 px;
  - the minimum window size is now 1060x600, derived from that measurement, so no row can overlap at the smallest
    allowed size. Verified at 1060 / 1100 / 1280 / 1600 px wide: every row fits.

## [v0.6.11] - 2026-10-01

### Added

- **The send history is manageable now (U77)**: right-click an entry in the history dropdown to delete just that one,
  or to clear the whole list - and while the dropdown is open, Delete removes the highlighted entry. Changes apply
  immediately and are stored with the rest of the history, so a mistyped command no longer has to stay there forever.
  The history tooltip documents both gestures.

## [v0.6.10] - 2026-10-01

### Added

- **"Restore defaults" in the Settings menu (U76)**: a confirmation dialog spells out exactly what will be reset
  (theme, language, auto-save, auto-reconnect, receive options, quick-send list, send history and auto-reply rules).
  Once confirmed, the current `config.json` is backed up to `config.backup_<date>_<time>.json` in the data folder
  before the defaults are applied, and the live window is put back to defaults immediately - no restart needed.

### Fixed

- **Switching the language could crash (regression from the Port settings work)**: the retranslate path referred to
  `_port_set_btn` while the widget is named `port_set_btn`, so any language switch - and with it the new restore
  action - raised an AttributeError. Caught by the reset test, fixed, and both paths are verified now.

## [v0.6.9] - 2026-10-01

### Added

- **Auto-save settings dialog (U75)**: the receive toolbar's Auto-save switch now has a companion dialog
  (Settings -> Auto-save settings) to enable it, set the per-file size limit (default 2 MB), the maximum duration
  (default 30 minutes) and the folder the segments land in (defaults to the app data folder, e.g.
  `%APPDATA%\SerialDesk\logs`). Every change applies immediately and is remembered; the toolbar switch and the
  dialog share one state, and the dialog note explains exactly what happens - every received line (including TX
  echo) is written live, and a new file starts once a limit is reached, named like `serial_20261001_0200.txt`.

### Changed

- **Auto-scroll is on by default and now remembered (U75)**: the receive pane follows incoming data unless you turn
  it off, and that choice survives a restart.

## [v0.6.8] - 2026-10-01

### Changed

- **The send area was rebuilt (U74)**: the input used to be squeezed into a 134 px column beside a control column that
  ate ~83% of the width, with its height hard-capped at 90 px - a toy box inside a large empty panel. Now:
  - format, checksum, append-CRLF and escape parsing share one row *above* the input;
  - the input owns the rest (630 px wide at the default size, and it grows with the splitter: 235 -> 354 px in
    testing) with the primary **Send** button beside it at the same height;
  - the repeat controls sit *below* the input and carry a live payload readout ("4 bytes to send", "6 bytes to send"
    with CRC16-Modbus, "invalid input" when the text does not parse);
  - the box has a placeholder that explains the HEX syntax, and the file / auto-reply row no longer hosts Send.

## [v0.6.7] - 2026-10-01

### Fixed

- **The Port settings dialog looked broken while a port was open (U73)**: data bits, parity, stop bits and flow
  control are applied when the port opens, so they are intentionally disabled while it is connected - but nothing
  said so, and only the encoding dropdown (which only affects decoding) appeared to work. The dialog now carries a
  hint that changes with the state: "Port is open: data bits / parity / stop bits / flow control can only change
  after closing it. Encoding and the signal lines stay available." / "These settings apply when the port opens; the
  signal lines can be driven at any time." The lock state is refreshed when the dialog opens and whenever the port
  is opened or closed.

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
