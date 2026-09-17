# Onset lateralization

Working in bipolar longitudinal montage, identify the earliest sustained rhythmic change.

- Find the first 2+ second run where one chain (left temporal, left parasagittal, right
  temporal, right parasagittal, midline) departs from background. Note the time.
- Note whether the same rhythm appears in the contralateral homologous chain, and how many
  seconds later.
- Describe the spread: stays focal, spreads ipsilaterally, generalizes, or is generalized
  from the first visible change.

Use `scope` to narrow the window around the suspected onset until you can name a time to
within ~2 seconds. Emit separate claims for `onset_region`, `onset_time`, and
`spread_pattern`. If onset is obscured by artifact or the change is generalized from the
start, say so with low confidence rather than guessing a side.
