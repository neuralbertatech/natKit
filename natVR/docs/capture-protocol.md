# EMG capture protocol

Date: 2026-06-11

This is the session protocol for collecting gesture-labeled forearm EMG data
for the natVR hand-presence pipeline.

## Goal

Make sessions comparable across days by holding the setup, cue timing, and
operator checklist constant.

## Electrode map

Initial 2-channel baseline:

1. `flexor_a`: flexor digitorum superficialis / wrist-flexor mass on the
   anterior forearm.
2. `extensor_a`: extensor digitorum / wrist-extensor mass on the posterior
   forearm.
3. Reference: bony landmark near elbow or wrist, away from the active muscle
   belly.

Expected photo references per session:

- forearm relaxed, palm up
- forearm relaxed, palm down
- close shot of each channel placement with cable routing visible

Those photo filenames should be recorded in the session metadata sidecar via
`--electrode-photo-ref` or `--metadata-json`.

## Skin prep

1. Wash and dry the forearm.
2. Shave if hair blocks adhesive contact.
3. Lightly abrade the skin with prep gel if needed.
4. Wipe away residue and let the skin dry before electrode placement.
5. Route cables so they do not tug during gestures.

## Gesture definitions

Use the same motion vocabulary every session.

- `rest`: hand relaxed, no deliberate contraction
- `fist`: close all digits into a firm fist
- `open`: spread and extend the hand
- `pinch`: thumb to index pinch
- `point`: index extended, other fingers flexed
- `thumbs_up`: thumb extended upward, other fingers flexed

Hold the target gesture steadily for the full cue window. Do not ramp in and
out dramatically inside the hold period.

## Session checklist

Before recording:

- verify the correct arm and channel map
- confirm batteries, Wi-Fi, and Kafka stack are up
- confirm the live viewer shows plausible rest noise and contraction bursts
- capture placement photos
- write subject/session notes while setup details are fresh

During recording:

- use the cue-driven capture command
- stay seated or keep posture constant for the full run
- avoid talking or touching cables during cue periods
- repeat the run if an electrode lifts or the subject misses cues

After recording:

- verify the `.parquet`, `.meta.json`, and `.cues.json` files exist
- spot-check that cue prompts align with observed contractions
- record any deviations, sweat, cable movement, or fatigue in session notes

## Suggested command

```sh
natvr-emg-capture \
  --device-id emg01 \
  --session-id 2026-06-11-demo-01 \
  --subject zach \
  --arm right \
  --gestures rest,fist,open,pinch,point,thumbs_up \
  --repetitions 3 \
  --hold-s 3 \
  --rest-s 2 \
  --lead-in-s 3 \
  --tail-rest-s 2 \
  --electrode-photo-ref photos/2026-06-11-demo-01-placement-front.jpg \
  --notes "baseline self-session"
```

## Notes

- Re-apply electrodes between sessions on different days.
- Keep the cue vocabulary stable until the first classifier baseline is in
  place.
- When channel count expands beyond 2, update the placement map and keep the
  channel labels stable in metadata.
