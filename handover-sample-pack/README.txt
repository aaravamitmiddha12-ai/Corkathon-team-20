Sample shift-handover pack - BrightLeaf Biologics (fictional pharma site, Cork)
Handover moment: Sat 7 Nov 2026, 07:00, night shift -> day shift.

shift_notes_night.txt  free-text log written by the outgoing engineer
alerts.csv             14 machine alerts from 4 systems (BMS, EMS, WFI SCADA, access, IT)
tickets.csv            6 tickets / work orders / calibrations / changes
assets.json            what each asset is and how critical it is (the 'context' layer)
answer_key.csv         the correct ranked handover, so you can score your output

The traps (this is the point of the demo):
- The notes downplay things the data shows are getting worse ('seems ok', 'only a blip').
- Two real problems (WFI excursions, chiller vibration) have NO ticket at all.
- One 'blip' in the notes is actually three alerts in the data.
- Half the items are noise and should be pushed down, not deleted.

All names and data are invented.
