Second sample shift for the carry-forward demo: Sat 7 Nov 2026, 07:00 -> 19:00 (day shift).
Handover moment: Sat 7 Nov 2026, 19:00, day shift -> night shift.
Uses ../assets.json. Same file formats as the night pack. No expert answer key for this shift.

What happens:
- FRZ-12 keeps alerting at similar values (-62.6 .. -62.0 C, no worse than last night's -61.9 C).
  The day engineer found a faulty display probe (WO-1195). A "known sensor fault" dismissal
  made at the 07:00 handover should carry forward quietly.
- CH-2-P3 vibration keeps climbing: 8.3 -> 8.6 -> 8.9 mm/s (alarm 9.0). The note says "seems stable"
  and there is still no ticket. A dismissal made at 07:00 must re-escalate (8.9 > 8.1).
- CR-B2 cleanroom pressure drops below its 10 Pa alarm limit. Nobody mentions it, no ticket.
- INC-2 incubator door gasket torn (note only), no ticket.
- HPLC-07 fixed, BAL-03 calibrated, WFI deviation DEV-2207 opened (due Sun 03:09).
