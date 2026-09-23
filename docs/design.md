# Design

How the dashboard looks and why. The values live in `frontend/src/styles/tokens.css`; this file is the
reasoning, so a later change is an argument rather than a guess.

## Direction

A race engineer's screen, not a product landing page. Dense, data first, colour reserved for state.
Dark only for now. A light theme, when it happens, redefines the same token names and nothing else.

Three earlier passes were rejected, and the reasons are the design:

- **Nothing leads.** A wall of equal-weight numbers in three grey rails. Every screen now has one
  thing that is obviously the headline and a clear second tier beneath it.
- **No containers.** Hairline dividers on a flat black ground were not enough separation. Every
  section is now a real card: its own surface, a 1px border, an 8px radius and a header strip, with
  the border and fill both lifting on hover.
- **Too grey, too small.** Secondary text was `#8a8a93` at 15px with 10px labels. Base is now 16px,
  the secondary ramp is `#c7c7d2` / `#9295a3`, and 11px is reserved for uppercase micro-labels and
  axis numerals that always sit next to a large value.

## Colour

The greys and the red are Formula 1's own, taken off formula1.com. The timing colours are the sport's
broadcast language. Both choices are the point: they are real to the subject instead of being a
generic dark theme with a red accent bolted on.

### Timing owns purple, green and yellow

Purple session best, green personal best, yellow slower than your own best. A driver reads these
faster than any label, and they are not ours to reinterpret.

Broadcast purple is `#b14fdb`, which measures 3.85:1 against `--f1-surface-2` and fails AA for the
small text it actually carries, a lap time in a table. The token is lightened to `#bc63e5` (4.65:1),
close enough to read as the same colour.

### Delta loss is yellow, not red

Green for gained time, yellow for lost. Red is for the car being in trouble, and a driver a
half-tenth down is not in trouble. This also lets delta and timing share hues so the two systems
reinforce each other rather than compete: green is good in both, yellow is caution in both.

### Red is scarce, and it cannot carry small text

`--f1-accent` (`#e10600`) measures **3.25:1** at worst against the surfaces it sits on. That is legal
for marks, fills, rules and large text (24px+, or 19px bold) and **illegal for anything at body
size**. A red label, a red unit, a red table cell are all wrong. When something red has to be read
small, use `--f1-critical` (`#ff4747`, 4.8:1).

Keeping it scarce is the other half. Once red is on every panel it stops meaning anything.

### Contrast floor

AA for normal text, 4.5:1, measured against all three surfaces and taking the worst.

| Token | Worst ratio | Verdict |
|---|---|---|
| `--f1-text-1` | 16.1:1 | pass |
| `--f1-text-2` | 9.6:1 | pass |
| `--f1-text-3` | 5.4:1 | pass |
| every state colour | 4.6:1+ | pass |
| `--f1-accent` | 3.25:1 | marks and large text only |
| `--f1-text-disabled` | 3.1:1 | disabled controls only |
| `--f1-border-control` | 3.36:1 | clears the 3:1 non-text floor |

`--f1-border` and `--f1-border-soft` sit below 3:1 deliberately. They are decorative separators and
never carry meaning alone. Anything that is the boundary of a control uses `--f1-border-control`.

Re-run the numbers if a colour changes. The script is four lines of WCAG relative luminance; do not
eyeball it.

## Type

**Saira carries words. Iosevka carries figures.** Never at the same size directly adjacent — a 44px
lap time beside a 44px circuit name is what made an earlier pass look like one badly-rendered font
rather than a pair. Size or weight always separates them.

The pairing works because Saira is squarish and wide where Iosevka is narrow. An earlier attempt used
Barlow Semi Condensed, and two narrow faces read as a single inconsistent one. Saira at weight 800 is
also the closest available match to F1's own chunky uppercase headings.

Both are self-hosted. The app runs on localhost and must work with no internet; a Google Fonts link
falls back to Consolas offline.

Every live number, table column and axis uses `tabular-nums lining-nums`. Figures must not dance.

## Charts

### The compare rule

When two laps are on screen, **the stroke says which lap and the area fill says which channel.**

A previous version coloured strokes by channel (speed white, throttle green, brake red) while the lap
pickers coloured by lap, so two encodings fought over the same mark and nobody could tell which trace
was theirs. Lap A is solid white at 2.4px; lap B is `#2dd4bf` **dashed** `7 5` at 2px. Dashed so
identity survives greyscale, a projector and colour blindness — never colour alone.

The same two colours are carried by the chip pickers, a permanent legend above the traces, the row
label, and a second dim value under every figure in the crosshair readout. The delta row belongs to
neither lap, so it is coloured by sign instead.

### Rules that hold everywhere

- One y-scale per chart. Never a dual axis.
- Colour follows the entity, not its rank. Changing the lap filter must not repaint the survivors.
- A legend is always present for two or more series.
- Chart text takes theme tokens, so it reads in either theme.

## State thresholds

Stored as unitless numbers in the token file so CSS and TypeScript cannot drift. All measured from
the recordings, not from folklore.

- **Tyre temperature tracks the carcass, not the surface.** Across three races the carcass stays
  inside 69-97 C while the surface swings 43-152 C *within a single lap*. Colouring the surface makes
  the widget strobe. Bands: 78 / 84 / 96 / 100 C. The surface is shown as a second, uncoloured number.
- **There are two band sets, and the fitted compound picks between them.** Not the weather: a driver
  who stayed out on slicks in the rain is still on slicks, and that is the moment the grid most needs
  to be right. Intermediates measured per corner while racing through a storm at Spa run **46-72 C**,
  median 62, 90th percentile 70, against 69-97 for slicks. On the slick bands that whole race reads
  cold, so the widget would show four blue corners for 45 minutes and tell you nothing. Intermediate
  bands: 52 / 58 / 70 / 73 C.
- **Full wets get a third set, because they run hotter than intermediates.** An 11-lap stint on
  compound 8 through a storm at Interlagos ran **61-91 C**, median 72, 90th percentile 86. On the
  intermediate bands that reads hot for most of the stint. Full-wet bands: 64 / 68 / 82 / 86 C.
  Both wet sets were measured on medium traction control with a lot of feathered throttle, so a
  committed drive on full TC may push them up.
- **Brakes:** 21-1011 C observed, median ~600, p95 ~900. Bands 200 / 800 / 950.
- **Delta noise band:** 0.05 s. Inside it the delta reads neutral rather than flickering.
- **Braking:** pedal above 0.15.

## What we do not draw

- **No track map.** It needs world position from the Motion packet, which is recognised but not
  parsed. Dead reckoning from steering and speed was tried and fails badly: a bicycle model closed
  2.1 km of a 6.2 km lap and the shape did not resemble the circuit. Show an honest empty state
  instead of a fake map.
- **No corner or turn numbers.** The UDP stream has no corner field, and deriving them from braking
  describes the driver rather than the track. The same detector found 8, 6 and 7 corners across three
  race laps at Abu Dhabi, and 6, 7, 7, 7, 6 across five clean time trial laps at the Red Bull Ring; it
  was stable only at Monza and Jeddah, which is what made it look correct at first. No threshold fixes
  it. The distance strip shades where the brake was actually down **on the lap being displayed** —
  measured, per-lap, unlabelled. Real corners need track geometry, so they come back if and when
  Motion is parsed.

The rule behind both: never show a number we cannot stand behind. An honest empty state beats a
confident fabrication.

## Edge states

The states a first run actually starts in. Getting them wrong is how a telemetry tool feels broken on
day one, so they are designed, not left to fall out of the code.

### No data yet

The port is open and nothing has arrived. This is the *normal* first screen, not an error, so it says
what the app is doing ("Listening on 20777"), what it is waiting for, and the exact in-game values to
type. No red, no warning icon.

### Paused

Packets stopped: the game is in a menu, or the session ended. The last values stay on screen, dimmed
and desaturated, under a yellow "no packets for Ns" badge.

Zeroing them would be a lie, and hiding them throws away the one thing you want after the game drops
out mid-lap: what it was doing when it stopped.

### Numbers the game has not filled in yet

The first `Session` packet of a session reports **track 0 C and air 0 C**, and only the next one
carries real values. Rendering that honestly means not rendering it: a track temperature of 0 C is a
plausible-looking lie, and it is the first thing on screen.

Any field the game has not populated shows an em dash in the value's place, keeping its box and its
label, rather than a zero. The same rule covers a packet slot that has not arrived: fields are absent,
not zero, and the two must never look alike.

### Series and regulations

Widgets are gated on capability, never on packet format. Measured across four recordings:

| State | Format | `telemetry2` | 2026 regs | Aero zones | ERS store |
|---|---|---|---|---|---|
| F1 26 | 2026 | present | `True` | 4 | 0.51 MJ |
| F1 Modern | 2025 | absent | — | 0 | 3.26 MJ |
| F2 | 2026 | present | **`False`** | **4** | **0.00 MJ** |
| F2 | 2025 | absent | — | 0 | 0.00 MJ |

**The trap is the third row.** F2 in a 2026-format stream still lists four active aero zones in the
Session packet, and its ERS store reads 0.00 MJ because an F2 car has neither system. So:

- **Active aero gates on `telemetry2.regulations_2026_applicable`.** Never on the packet format, and
  never on the zone list being non-empty — both are true for F2.
- **ERS gates on the series** (`formula !== 2`).

Get either wrong and every F2 session paints two dead widgets.

## Density and motion

4px base scale. Fixed heights on anything live, so a changing value never reflows its neighbour. Cards
sit in a grid with a real gutter, not a 1px seam.

Live numbers get **no** transition. At 30 Hz a 150ms fade is mush and costs frames. Transitions are
for hover, panel state and route changes only, and all of them are disabled under
`prefers-reduced-motion`.

Per AGENTS.md, live values are written through refs and `requestAnimationFrame`, never by re-rendering
React per telemetry frame. The token file supports this: every live value sits in a fixed-size box
with its label outside, so the loop only ever writes a leaf text node.

## Consuming the tokens

`tokens.css` is plain CSS and is the only place values live. `theme.css` maps Tailwind 4's `@theme`
and shadcn/ui's contract variables (`--background`, `--card`, `--border`, `--ring`) onto `var(--f1-*)`
as aliases, so shadcn components inherit the look without component edits. uPlot reads the handful of
values it needs once at startup via `getComputedStyle`, never per frame.
