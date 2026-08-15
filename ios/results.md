# iPhone 16 thumb-typing layout exploration — results

Corpus: 179,825 chars (Alice in Wonderland + this repo's corpus passage + mobile-style phrases x20). Model: KALQ same-side/alternating thumb equations, Shannon ID with directional key pitch; miss risk = 2 mm-sigma Gaussian vs key Voronoi cell. See ios/README.md.

| layout | key (mm) | 2-thumb WPM | 1-thumb WPM | mm/tap | alt % | miss %/tap | long-press % |
|---|---|---|---|---|---|---|---|
| Colemak Ortho (current) | 5.5x7.1 | 39.0 | 42.1 | 15.99 | 52.5 | 10.72 | 0.58 |
| QWERTY ortho (reference) | 5.5x7.1 | 39.0 (-0.0%) | 42.3 (+0.5%) | 17.83 | 52.3 | 10.72 | 0.58 |
| Colemak Thumb (micro-iterated) | 5.5x7.1 | 39.0 (+0.0%) | 42.1 (+0.0%) | 15.99 | 52.5 | 10.72 | 0.58 |
| Opt-10 hybrid (same grid as Colemak) | 5.5x7.1 | 38.4 (-1.6%) | 44.7 (+6.1%) | 14.67 | 35.1 | 10.72 | 0.58 |
| Thumbline-8 two-thumb | 7.1x7.1 | 38.2 (-1.9%) | 44.4 (+5.3%) | 15.48 | 39.5 | 5.84 | 1.11 |
| Thumbline-8 one-thumb | 7.1x7.1 | 37.7 (-3.2%) | 45.0 (+6.8%) | 15.75 | 36.9 | 5.84 | 1.11 |
| Thumbline-8 hybrid | 7.1x7.1 | 38.0 (-2.4%) | 45.0 (+6.8%) | 15.04 | 39.0 | 5.84 | 1.11 |

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
  z c g w r d i n k ^
  q f u o l a e h b x
  j p v y m s t , ' -
  [1] [⌫] [#] [ ] [⏎]
```

### Thumbline-8 two-thumb
```
  p w s c l v r y
  m b o u h e n d
  f g i k t a , '
  [^] [1] [⌫] [ ] [#] [⏎]
```

### Thumbline-8 one-thumb
```
  b m u n r c v w
  f y i o e h k p
  l g d a t s , '
  [^] [1] [⌫] [ ] [#] [⏎]
```

### Thumbline-8 hybrid
```
  f w u n y l c k
  p g o i a h r v
  b m d s t e , '
  [^] [1] [⌫] [ ] [#] [⏎]
```
