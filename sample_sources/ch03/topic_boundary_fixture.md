Lantern Notes keeps a sync log for every device that edits the same notebook.

Each edit carries a device id and a timestamp so the sync daemon can order them correctly.

When two devices edit the same note while offline, the daemon has to merge both edits instead of silently picking one.

A naive merge that just keeps the newer timestamp throws away real work from the older edit, so the merge logic diffs both versions line by line.

Device clocks drift by a few seconds across a laptop and a phone, so edits inside a two second window are treated as concurrent rather than ordered.

The GPU in the note-tagging workstation throttles its clock speed when it runs hot for too long.

A long tagging session that reads hundreds of notes in a row keeps the GPU busy well past the point where a short chat session would have gone idle.

Once the temperature sensor crosses the vendor's thermal limit, the driver lowers the clock speed automatically to bring the card back down.

Token generation slows noticeably every time the throttle engages, and speed only recovers once the card cools a few degrees below the limit.

Raising the case fan curve earlier, before the card reaches the limit, keeps the clock speed steady through an entire long session instead of oscillating.
