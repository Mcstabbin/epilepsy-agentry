# Make this useful to the person

The first useful outcome is a clearer follow-up appointment: the person can show what
happened, what was recorded, what the team concluded, and which questions remain. This
project has not demonstrated improved seizure control or validated seizure prediction.

## Before building more agents

Work with your friend's permission and let them choose what they want help with. Examples
include remembering events, describing recovery, organizing records, or discussing side
effects with the team. A useful product should make that job easier without asking them
to manage a large collection of sensors.

Keep their discharge instructions and care team's seizure action plan accessible. The
Epilepsy Foundation provides [action-plan resources](https://www.epilepsy.com/preparedness-safety/action-plans)
for recording an individualized response plan with the healthcare team. The software
should store or link the team's instructions, not generate rescue doses or new treatment
instructions.

## Gather a small, useful first dataset

1. Request the final EEG interpretation and marked event times alongside the full EEG
   export. Use the [records request](records-request.md); availability and formats depend
   on the hospital. Annotations and the clinical interpretation serve different roles.
2. Keep the discharge medication list and hospital medication-administration timeline
   separate from remembered medication use. Record the source and uncertainty of each.
3. Ask the care team what information they want in a diary. A seizure diary can capture
   events, symptoms, medicines, and side effects for discussion with the team.
   See the [Epilepsy Foundation diary guide](https://www.epilepsy.com/manage/tracking/seizure-diaries).
4. Bring the report and a short list of questions to follow-up. Ask which observations
   are clinically relevant and which measurements would help at the next visit.

## Product priorities

The next patient-facing feature should be a short event diary with an explicit
"unknown" option: approximate time and duration, what the person or witness observed,
recovery, and any concern they want to discuss. Recording an event must not require the
person to diagnose it. Let them distinguish "no event noticed" from "no entry today."

Add optional sleep notes, medication taken as prescribed, reported side effects, and
the person's own goal. Keep event observations separate from inferred patterns. Never
suggest altering medication or reproducing the hospital's seizure-provoking conditions.

Build a follow-up packet that joins the diary, hospital event times, clinician-reviewed
labels, and source evidence. Start with the six hospital events as individual review
items; don't assume the number of events makes a predictor reliable. Hospital conditions
and everyday life can differ, so the packet must retain that context.

## What to measure

For the software: how long it takes to record an event, missing entries, incorrectly
matched events, time needed to prepare an appointment, and whether each finding has
inspectable evidence. Ask the person and their team whether the packet was useful.

For health outcomes: let the person and team choose meaningful measures, such as reported
event burden, recovery, side effects, or quality of life. The project can display those
observations over time. It cannot attribute improvement to itself or a treatment from a
small, uncontrolled before-and-after comparison.

## Available now

`ea demo` demonstrates the review packet with generated data. `ea review` creates a local
packet from a canonical recording's annotations. A diary, medication importer, clinical
review interface, and automatic comparison with the final report are roadmap items, not
implemented features.
