# Records to request from the EMU

Ask before discharge, in writing, and get the name of a specific person in the EEG lab
(not just medical records). The lab is who can pull the continuous file.

```
Request for complete EEG monitoring records — [name], MRN [____], admitted [date]

Please provide the following from my epilepsy monitoring unit admission:

1. Full continuous EEG for the entire stay, in EDF+ format (not clipped event
   files only), including all EEG, ECG, and any respiratory or EMG channels.
2. The annotation/event file as a separate export (technologist markers,
   push-button events, seizure onset/offset marks, medication times).
3. The technologist log and nursing notes covering the monitoring period.
4. The medication taper and rescue-dose schedule with administration timestamps.
5. Video for at least 60 minutes before and after each marked event, with the
   video-to-EEG time synchronization method documented.
6. Technical parameters: sampling rate, reference electrode and montage,
   filter settings, electrode map (10-20 plus any additional leads).
7. The final epileptologist report and any interim reads when complete.
8. If Persyst or a similar review system is used, the native export as well.

I am requesting this under my right of access to my own health records. Please
confirm the delivery format and expected turnaround.
```

Also ask which acquisition system they run (Natus, Nihon Kohden, Cadwell, ...). Each has
its own export quirks.

## Once it arrives

```
ea inspect  recording.edf
ea transcode recording.edf data/rec001.zarr
ea features data/rec001.zarr data/rec001_l1.parquet
ea candidates data/rec001.zarr data/rec001_l1.parquet
```

Keep everything under `data/`. It is gitignored.
