# iPhone 16 thumb-typing layout exploration — results

Corpus: 179,825 chars (Alice in Wonderland + this repo's corpus passage + mobile-style phrases x20). Model: KALQ same-side/alternating thumb equations, Shannon ID with directional key pitch; miss risk = 2 mm-sigma Gaussian vs key Voronoi cell. See ios/README.md.

| layout | key (mm) | 2-thumb WPM | 1-thumb WPM | mm/tap | alt % | miss %/tap | long-press % |
|---|---|---|---|---|---|---|---|
| Colemak Ortho (current) | 5.5x7.1 | 39.0 | 42.1 | 15.99 | 52.5 | 10.72 | 0.58 |
| QWERTY ortho (reference) | 5.5x7.1 | 39.0 (-0.0%) | 42.3 (+0.5%) | 17.83 | 52.3 | 10.72 | 0.58 |
| Colemak Thumb (micro-iterated) | 5.5x7.1 | 39.0 (+0.0%) | 42.1 (+0.0%) | 15.99 | 52.5 | 10.72 | 0.58 |
| Opt-10 hybrid (same grid as Colemak) | 5.5x7.1 | 40.4 (+3.6%) | 44.2 (+4.8%) | 15.54 | 59.7 | 10.72 | 0.58 |
| Thumbline-8 two-thumb | 7.1x7.1 | 40.3 (+3.5%) | 44.2 (+4.9%) | 15.64 | 55.5 | 5.84 | 1.11 |
| Thumbline-8 one-thumb | 7.1x7.1 | 38.4 (-1.3%) | 45.1 (+7.0%) | 15.60 | 45.2 | 5.84 | 1.11 |
| Thumbline-8 hybrid | 7.1x7.1 | 40.2 (+3.2%) | 44.5 (+5.5%) | 16.29 | 55.4 | 5.84 | 1.11 |

### Colemak Ortho (current)
```
  q w f p g j l u y ^
  a r s t d h n e i o
  z x c v b k m , ' -
  [1] [⌫] [#] [ ] [⏎]
```

### QWERTY ortho (reference)
```
  q w e r t y u i o p
  a s d f g h j k l ^
  z x c v b n m , ' -
  [1] [⌫] [#] [ ] [⏎]
```

### Colemak Thumb (micro-iterated)
```
  q w f p g j l u y ^
  a r s t d h n e i o
  z x c v b k m , ' -
  [1] [⌫] [#] [ ] [⏎]
```

### Opt-10 hybrid (same grid as Colemak)
```
  z k m c l e g q y ^
  p w s n r i a u b x
  j v f d h o t , ' -
  [1] [⌫] [#] [ ] [⏎]
```

### Thumbline-8 two-thumb
```
  g o u y l r c k
  f i e a h m v b
  p d t s w n , '
  [^] [1] [⌫] [ ] [#] [⏎]
```

### Thumbline-8 one-thumb
```
  b m l n i c w v
  f p o r e a g k
  y u d h t s , '
  [^] [1] [⌫] [ ] [#] [⏎]
```

### Thumbline-8 hybrid
```
  b d e i r c w p
  v g o a n f m k
  y u s t l h , '
  [^] [1] [⌫] [ ] [#] [⏎]
```

## Swipe family (3x3 tap+swipe, MessagEase style)

| layout | 2-thumb WPM | 1-thumb WPM | swipe % | tap-miss % | dir-err % |
|---|---|---|---|---|---|
| MessagEase classic | 35.2 | 42.3 | 26.7 | 2.55 | 0.45 |
| Thumb-Key EN | 35.2 | 41.7 | 26.7 | 2.55 | 0.58 |
| Swipe-9 (corpus-tuned) | 35.5 | 42.5 | 26.7 | 2.55 | 0.46 |

Swipe-overhead sensitivity (corpus-tuned board): 80 ms → 43.7 1T wpm, 110 ms → 42.5 1T wpm, 140 ms → 41.3 1T wpm
