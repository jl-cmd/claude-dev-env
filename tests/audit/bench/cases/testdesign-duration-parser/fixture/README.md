# durations

`durations.parse.parse_duration(text)` returns whole seconds.

- Units: `h`, `m`, `s`, in that order, each at most once: `1h30m`, `45s`, `2h5s`.
- A bare integer such as `90` means seconds.
- Empty text, a negative number, an unknown unit, or units out of order raise `ValueError`.
