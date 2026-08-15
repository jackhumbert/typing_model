# iOS thumb-typing layout explorer

An adaptation of this repo's carpalx-style typing model to **iPhone thumb
typing**, built to iterate on a Colemak Ortho board for the
[XKeyboard](https://apps.apple.com/app/xkeyboard-custom-keyboard/id1440245063)
custom-keyboard app (`.xkeyboard` files, iPhone 16 portrait).

The desktop model in `index.html` scores QMK keymaps with per-key base effort
(distance from homerow), penalties, and stroke-path terms over a corpus. On a
phone there is no homerow and no finger assignment — one or two thumbs do
everything — so the machinery is re-derived from the mobile text-entry
literature instead:

## Model

**Movement (speed) model.** Times between key presses come from the two-thumb
tapping study behind KALQ — Oulasvirta et al., *Improving Two-Thumb Text Entry
on Touchscreen Devices*, CHI 2013:

* **Same-side / one-thumb taps** (their Eq. 3-4, quadratic in Fitts ID,
  Shannon form `ID = log2(D/W + 1)`):
  `MT_left = 319.5 − 89.0·ID + 36.7·ID²`,
  `MT_right = 237.3 − 7.6·ID + 13.8·ID²` (dominant hand ~30 ms faster).
  The one-thumb simulation uses the dominant-hand curve for every transition.
* **Alternating taps** (their Eq. 5-6): bivariate in ID and `t_elapsed` (time
  since that thumb's previous press — the idle thumb *hovers* toward its next
  target). Short waits make alternation cheaper than a same-side tap; waits
  beyond ~600 ms are penalized quadratically. This is what makes
  hand-alternation valuable for two thumbs but worthless for one.
* `W` is the directional key pitch (ellipse projection of the key's exclusive
  cell along the approach direction). ID clamps follow the paper's fitted
  range. Same-key repeats cost 160 ms; long-press candidates add 350 ms.

**Precision model.** The user priority here is precision, not raw speed, and
this keyboard has **no autocorrect** — a missed tap is a real error:

* Taps scatter as a bivariate Gaussian around the key centre (Azenkot & Zhai,
  *Touch Behavior with Different Postures on Soft Smartphone Keyboards*,
  MobileHCI 2012; Bi, Li & Zhai's FFitts law). With σ = 2.0 mm, the reported
  **miss %** is the chance a tap lands outside the key's exclusive cell.
* Key size is the dominant lever. Parhi, Karlson & Bederson (MobileHCI 2006)
  put the serial-tapping threshold at ≥ 7.6-7.7 mm targets. An iPhone 16
  screen is 65.1 mm wide: a 10-column grid gives 6.5 mm pitch — under the
  threshold — while 8 columns gives 8.1 mm. Hence the 8-column family below.
* Travel is the secondary lever: shorter average movements mean lower IDs,
  and at a fixed typing pace that spare capacity becomes accuracy
  (speed-accuracy tradeoff). `mm/tap` and mean ID are reported for this.

**Corpus.** `corpus/` blends Alice in Wonderland (Project Gutenberg #11), the
prose passage already used as this repo's corpus, and a set of mobile-register
phrases (upweighted 20×) — lowercased, reduced to `a-z ' , . -` and space.
Space is ~19% of all taps, which is why its bottom-row position and the keys
around it matter so much.

**Two-thumb simulation details.** Keys left of the screen midline belong to
the left thumb, right of it to the right thumb; space may be taken by either
thumb (the simulator picks the cheaper one per tap, mirroring skilled
behaviour). Sides, wait times, and hover origins are tracked exactly over the
whole corpus stream. The annealer uses a vectorized trigram approximation for
speed, but every reported number — and the final hill-climb polish — comes
from the exact stream simulation (`thumbmodel.simulate`).

## Findings (see `results.md` for the current numbers)

1. **Colemak Ortho is already excellent for two-thumb typing.** Its
   left-consonant/right-vowel split yields ~52% side alternation, near the
   ceiling the model can exploit; a validated hill-climb finds **no letter
   swap** that improves the balanced objective by even 0.4%. (This matches
   why KALQ-style optimizers rediscover vowel-clustering-on-one-side — it is
   the same design idea Colemak already encodes.)
2. **One-thumb typing is where assignment optimization pays** (+6-7% in the
   model): one thumb wants frequent letters in one compact cluster around
   space, not split across the board.
3. **Precision is geometry-first**: dropping from 10 to 8 columns nearly
   halves modeled miss risk (6.5 → 8.1 mm pitch), at the cost of moving the
   four rarest letters (q z x j — together ~0.45% of characters) onto
   long-press candidates of mnemonic hosts: **q on u, z on s, x on c,
   j on g**.
4. Punctuation check: in this corpus, comma is ~2.7× more frequent than
   period, so the uploaded board's `,`-tap / `.`-long-press choice is kept.

## Files

* `thumbmodel.py` — geometry, movement models, corpus, exact simulator,
  trigram scorer
* `layouts_def.py` — layout/slot definitions (10-col and 8-col families)
* `optimize.py` — simulated annealing + validated greedy swaps
* `xkbgen.py` — emits installable `.xkeyboard` archives (fresh UUIDs
  throughout; numbers/symbols layers carried over from the original board)
* `explore.py` — end-to-end driver (`python3 explore.py [--quick]`)
* `layouts/` — the uploaded baseline plus generated `.xkeyboard` variants
* `results.md`, `layouts.json` — scored comparison and machine-readable dump

## Caveats

* KALQ's coefficients were fitted on a tablet grip; on a phone the absolute
  WPMs should be read as expert-ceiling estimates, and comparisons between
  layouts are what matter.
* At a steady ~300 ms/char pace, each thumb in strict alternation waits
  ~600 ms between its own presses — exactly where the paper reports the wait
  penalty kicking in. The model therefore scores two-thumb typing
  conservatively (even slightly under one-thumb) and flattens the two-thumb
  landscape; the corresponding design pressure it *does* transmit is KALQ's
  own: cheap same-side runs on the dominant side, alternation to reach the
  other. At faster paces alternation wins outright.
* The model has no reachability asymmetry (a one-handed grip makes the
  far-top corner genuinely harder than Fitts distance implies) and no
  language model / autocorrect (deliberately — this board has none).
* σ = 2.0 mm tap scatter is a mid-range literature value; miss % scales with
  it but rankings do not change.

## References

* Oulasvirta, Reichel, Li, Zhang, Bachynskyi, Vertanen, Kristensson.
  *Improving Two-Thumb Text Entry on Touchscreen Devices.* CHI 2013.
* MacKenzie & Zhang. *The Design and Evaluation of a High-Performance Soft
  Keyboard.* CHI 1999 (OPTI). / Zhai, Hunter & Smith. *The Metropolis
  Keyboard.* UIST 2000 — Fitts-digraph energy over a corpus.
* Parhi, Karlson & Bederson. *Target Size Study for One-Handed Thumb Use on
  Small Touchscreen Devices.* MobileHCI 2006.
* Azenkot & Zhai. *Touch Behavior with Different Postures on Soft Smartphone
  Keyboards.* MobileHCI 2012.
* Bi, Li & Zhai. *FFitts Law: Modeling Finger Touch with Fitts' Law.*
  CHI 2013.
* Carpalx (M. Krzywinski) — the triad effort framework this repo's desktop
  model adapts.
