# Everything Is Down: Seeing Through the Earth

**The world is *down*, not around!** When we think about where the rest of the world is,
we think of places on a map. But relative to you, right now, nearly all of it is beneath
your feet, somewhere you could point to directly, through thousands of miles of earth.
A family of single-file web apps draws the far side of the planet: live, correctly
oriented, locked to the world. Straight down is your exact antipode; the horizon is your
own position, in every direction at once.

(If "everything is down" sounds too strong: of course, a lot of stuff on your continent is
more "next to you" than "under you". But curvature kicks in more quickly than you think.
Stand in New York and look directly at Los Angeles (the actual straight line to the city,
not the direction you'd drive) and you're looking at a spot on the ground only about
17 feet away from you. The line dips half the arc you span: NYC to LA is 35.4° around the
globe, so the sight line drops 17.7° below your horizontal.)

**`index.html`** is the hub: pick your device (phone / laptop / monitor / none) and it
routes you to the right app. The apps:

| path | app | device |
|---|---|---|
| `ar/` | **Antipode AR**: far-side coastlines over the live camera feed; no build step, no frameworks, no network use after load | phone |
| `window-imu/` | **Earth Window (IMU)**: tilt the device like a pane of glass; sensors only, no camera | phone / tablet |
| `window/` | **Earth Window (head-tracked)**: webcam head tracking turns the screen into a literal window with parallax | laptop |
| `fly/` | **Fly Through**: free-flying 3D Earth, WASD + mouse | monitor |
| `circle/` | **The Circle at Your Feet**: if the ground were a glass circle of radius r, how much of the far side could you see? Cross-section + far-side map; radius = your height ⇒ half the planet | anything |
| `aim/` | **Arm Aim**: where to point your arm to aim at any city through the Earth | other |
| `extras/` | earlier experiments (first sketch, fly v1, orbit globes, day/night) | - |

## Run it on a phone

Sensors and camera require HTTPS, so serve the folder over TLS on your LAN:

```sh
./serve.sh
```

then open `https://<this-mac's-ip>:8443` on the phone (same Wi-Fi) and accept the
self-signed-certificate warning. In the AR app, tap **Start** and grant motion, location
and camera permission. Works in iOS Safari and Android Chrome. (Hosted over real HTTPS,
e.g. GitHub Pages, no certificate warning appears.)

On a desktop browser (no motion sensors) the AR app falls back to drag-to-look /
scroll-to-zoom, which is handy for trying other locations via the manual lat/lon input.

## Controls (⚙)

- **Field of view**: the calibration knob; if the overlay's angular scale feels wrong, this is it. Default 60° vertical.
- **Camera opacity**: 0 gives a black background, often more legible.
- **Heading trim**: rotates the whole map about the vertical, for compass error.
- **Flip signs α/β/γ**: escape hatches for device-specific orientation sign bugs.
- **Location**: manual lat/lon (also for exploring other places), or re-query GPS.
- **Camera**: lens picker; the ultra-wide (0.5×) lens roughly doubles the visible Θ.
- **Freeze** (❄): holds the last orientation so you can study the frame.
- **Run self-test**: the acceptance checks, runnable on the device itself.

## How it works

The far surface is ~12,742 km away, so walking around changes nothing: only
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

- `tools/build_data.py <ne_110m_land.geojson> <outdir>`: regenerates the encoded
  coastline string (and re-verifies the projection against the spec's acceptance
  table). Source data: https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson
- `node test/core-test.mjs`: runs the AR app's own self-test suite plus a deep
  round-trip of the inline data against the Python reference decode.
- `node test/dom-smoke.mjs`: loads the full app under a stub DOM, presses Start,
  feeds synthetic GPS + orientation events, and checks what got drawn.
