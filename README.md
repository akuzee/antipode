# Antipode

Point your phone at the ground and see the far side of the Earth drawn on the camera
image, as if the planet were transparent. Straight down is your exact antipode; tilting
toward the horizon reveals coastlines closer to home — the horizon itself is your own
position, in every direction at once.

Everything is one file: **`index.html`** (inline CSS + JS, inline coastline data,
no build step, no frameworks, no network use after load).

## Run it on a phone

Sensors and camera require HTTPS, so serve the folder over TLS on your LAN:

```sh
./serve.sh
```

then open `https://<this-mac's-ip>:8443` on the phone (same Wi-Fi) and accept the
self-signed-certificate warning. Tap **Start** and grant motion, location and camera
permission. Works in iOS Safari and Android Chrome.

On a desktop browser (no motion sensors) it falls back to drag-to-look / scroll-to-zoom,
which is handy for trying other locations via the manual lat/lon input.

## Controls (⚙)

- **Field of view** — the calibration knob; if the overlay's angular scale feels wrong, this is it. Default 60° vertical.
- **Camera opacity** — 0 gives a black background, often more legible.
- **Heading trim** — rotates the whole map about the vertical, for compass error.
- **Flip signs α/β/γ** — escape hatches for device-specific orientation sign bugs.
- **Location** — manual lat/lon (also for exploring other places), or re-query GPS.
- **Camera** — lens picker; the ultra-wide (0.5×) lens roughly doubles the visible Θ.
- **Freeze** (❄) — holds the last orientation so you can study the frame.
- **Run self-test** — the acceptance checks, runnable on the device itself.

## How it works

The far surface is ~12,742 km away, so walking around changes nothing — only
orientation matters, exactly like a star map. A far-side point at great-circle distance
Θ from your antipode is seen at nadir angle ν = Θ/2 (inscribed angle theorem), at
azimuth equal to the bearing from you to it. Per-vertex view directions are cached per
location; each frame only rotates them by the device orientation (W3C α/β/γ →
quaternion, slerp-smoothed with τ ≈ 0.15 s) and applies a pinhole projection.

Coastlines are Natural Earth 110m land polygons (public domain), Douglas-Peucker
simplified, quantized to 0.1°, delta/zigzag/base-41-varint encoded to ~9 KB of inline
text, and densified at load so no segment exceeds 0.25° (coarse segments near the
horizon would otherwise draw shortcuts across curved coastline).

Note the view is deliberately left-right mirrored relative to a wall map: you are
reading the far surface from the inside. Perth lies northeast of New York's antipode
but appears to the *west* on screen. That is correct.

## Development

- `tools/build_data.py <ne_110m_land.geojson> <outdir>` — regenerates the encoded
  coastline string (and re-verifies the projection against the spec's acceptance
  table). Source data: https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson
- `node test/core-test.mjs` — runs the app's own self-test suite plus a deep
  round-trip of the inline data against the Python reference decode.
- `node test/dom-smoke.mjs` — loads the full app under a stub DOM, presses Start,
  feeds synthetic GPS + orientation events, and checks what got drawn.
