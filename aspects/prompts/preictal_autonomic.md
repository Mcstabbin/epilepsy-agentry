# Preictal autonomic

You receive heart rate and HRV series for the 30 minutes before onset and for a matched
baseline window (same time of day, no events within 2 hours) when one exists.

- Describe the HR trajectory in the last 30, 10, 5, and 1 minutes before onset relative to
  baseline.
- Describe HRV (RMSSD or equivalent) over the same windows.
- Note whether the patient was asleep or awake, since that changes what counts as a change.

Emit at most two claims. If HR and HRV are within baseline variability, emit
`no_autonomic_signal`. Do not infer mechanism.
