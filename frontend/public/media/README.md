# ADL stimulus placeholders

`placeholder-<task_id>.png` / `.wav` — one pair per ADL task, referenced by
`adlStepProtocol()` in `src/AdlExperiment/tasks.ts` via `adlStimulusImage()` /
`adlStimulusAudio()`.

⚠️ **These are not the study's stimuli.** Each image says PLACEHOLDER and "not a real
stimulus — replace before any study run"; each clip is a robotic `flite` synthesis
prefixed with the word "Placeholder". That is deliberate: a stand-in that looked or
sounded finished is how a pilot session gets recorded against the wrong stimulus and
nobody notices until the labels are being analysed.

⚠️ **The filenames are part of the safety property.** The url lands in each marker's
`image_url` / `audio_url` attributes, so `placeholder-` in the path makes a session
recorded against stand-ins detectable **from the recorded data alone**, rather than a
judgement call afterwards. If you swap in real assets, change the paths too — do not
leave real stimuli sitting behind a `placeholder-` name.

## Served from here on purpose

These are static frontend assets, not media-store uploads. A media-store id is
per-install, so a protocol referencing one would not travel between deployments; a
`/media/...` path is stable in dev (Vite `public/`) and in prod (nginx `location /`).

## Behaviour these drive, confirmed in the code rather than assumed

- **The image is shown for the whole hold**, not just at cue onset:
  `ExperimentRunner.svelte` renders it under `{#if activeCue?.image_url}`, so it is on
  screen for as long as that cue is the active one.
- **The clip replays on every repeat.** The audio effect is keyed on `cue.cue_id`, and
  `compileStepProtocol` increments `cueId` per emitted event, so a second occurrence of
  the same task is a different id and sounds again. It does not play once per class.

## Regenerating

`/tmp/gen_placeholders.py` in the session that made these; the task list is copied from
`AdlExperiment/tasks.ts`. Requirements: `python3` + Pillow, `flite`, and `fc-match`.

⚠️ Resolve the font through `fc-match`, never a hardcoded path. PIL's silent fallback is
`ImageFont.load_default()` — a **bitmap** face that ignores the size argument — and the
first run of this set produced ten images whose 72pt heading rendered at roughly 8pt.
They looked like a broken renderer, not a placeholder.

The two `example-*` files predate this set and are unrelated demo assets.
