window.HANDOVER_DATA = {
  "site": "BrightLeaf Biologics (Cork site)",
  "handover": {
    "shift_id": "night",
    "time": "2026-11-07T07:00:00",
    "eyebrow": "NIGHT → DAY · SAT 7 NOV · 07:00",
    "incoming_shift": "Day shift",
    "incoming_engineer": "S. O'Brien",
    "outgoing_engineer": "D. Murphy",
    "outgoing_review_completed": false,
    "responded": 0
  },
  "heading": "Good morning. Your handover is ready.",
  "summary": {
    "lead": "5 things need you.",
    "clash": "2 of them the notes got wrong."
  },
  "counts": {
    "top": 5,
    "clash": 2,
    "not_urgent": 8,
    "carried_over": 0,
    "alerts": 14,
    "tickets": 6,
    "note_lines": 10
  },
  "items": [
    {
      "rank": 1,
      "asset_id": "FRZ-12",
      "title": "FRZ-12: 4 temperature alarms, notes said OK",
      "why": "Notes at 21:05 and 23:15 said it was fine, but 3 more alarms came after. 4 readings from -64.8 °C to -61.9 °C, all above the -70 °C alarm limit. No open ticket, although the note said it would be dealt with later.",
      "bullets": [
        "Notes at 21:05 and 23:15 said it was fine, but 3 more alarms came after.",
        "4 readings from -64.8 °C to -61.9 °C, all above the -70 °C alarm limit.",
        "No open ticket, although the note said it would be dealt with later."
      ],
      "action": "Check FRZ-12 on site now, then raise a ticket.",
      "evidence": "4 high alerts, -64.8 to -61.9 °C, limit -70.0 °C · latest not acknowledged",
      "clash": true,
      "tags": [
        {
          "key": "clash",
          "label": "Notes say OK, data disagrees"
        },
        {
          "key": "no_open_ticket",
          "label": "No ticket"
        },
        {
          "key": "trend_worsening",
          "label": "Getting worse"
        },
        {
          "key": "unacknowledged_latest",
          "label": "Not acknowledged"
        },
        {
          "key": "repeated",
          "label": "4 alerts"
        }
      ],
      "due_by": null,
      "due_label": "",
      "overdue": false,
      "dismissed_earlier_now_worse": false
    },
    {
      "rank": 2,
      "asset_id": "WFI-LOOP-1",
      "title": "WFI-LOOP-1: 3 conductivity alarms, notes said OK",
      "why": "Note at 03:10 said it was fine, but 2 more alarms came after. 3 separate excursions above the 1.3 µS/cm limit: 1.6, 1.5, 1.4 µS/cm. Site rule: every excursion must be logged as a deviation within 24 h.",
      "bullets": [
        "Note at 03:10 said it was fine, but 2 more alarms came after.",
        "3 separate excursions above the 1.3 µS/cm limit: 1.6, 1.5, 1.4 µS/cm.",
        "Site rule: every excursion must be logged as a deviation within 24 h."
      ],
      "action": "Check WFI-LOOP-1 on site now, then raise a ticket and log a deviation, as the site rule requires.",
      "evidence": "3 high alerts, 1.6 to 1.4 µS/cm, limit 1.3 µS/cm · latest not acknowledged",
      "clash": true,
      "tags": [
        {
          "key": "clash",
          "label": "Notes say OK, data disagrees"
        },
        {
          "key": "no_open_ticket",
          "label": "No ticket"
        },
        {
          "key": "unacknowledged_latest",
          "label": "Not acknowledged"
        },
        {
          "key": "repeated",
          "label": "3 alerts"
        }
      ],
      "due_by": "2026-11-08T03:09:00",
      "due_label": "Due by Sun 03:09 · 20 h left",
      "overdue": false,
      "dismissed_earlier_now_worse": false
    },
    {
      "rank": 3,
      "asset_id": "CH-2-P3",
      "title": "CH-2-P3 vibration rising toward 9 mm/s alarm",
      "why": "3 readings from 6.8 mm/s to 8.1 mm/s; the alarm is at 9 mm/s. No open ticket, although the note said it would be dealt with later. Latest alert at 05:58 is not acknowledged.",
      "bullets": [
        "3 readings from 6.8 mm/s to 8.1 mm/s; the alarm is at 9 mm/s.",
        "No open ticket, although the note said it would be dealt with later.",
        "Latest alert at 05:58 is not acknowledged."
      ],
      "action": "Raise a ticket for CH-2-P3 and get it inspected before it reaches the alarm limit.",
      "evidence": "3 medium alerts, 6.8 to 8.1 mm/s, limit 9.0 mm/s · latest not acknowledged",
      "clash": false,
      "tags": [
        {
          "key": "no_open_ticket",
          "label": "No ticket"
        },
        {
          "key": "trend_worsening",
          "label": "Getting worse"
        },
        {
          "key": "near_limit",
          "label": "Close to alarm limit"
        },
        {
          "key": "unacknowledged_latest",
          "label": "Not acknowledged"
        },
        {
          "key": "repeated",
          "label": "3 alerts"
        }
      ],
      "due_by": null,
      "due_label": "",
      "overdue": false,
      "dismissed_earlier_now_worse": false,
      "projected_limit_time": "2026-11-07T09:41:21",
      "projected_limit_time_recent_pace": "2026-11-07T07:49:49",
      "projected_limit_label": "Trips ~07:50–09:40"
    },
    {
      "rank": 4,
      "asset_id": "HPLC-07",
      "title": "HPLC-07: INC-4471 due Sat 09:00",
      "why": "INC-4471 (P2, Vendor (Agilex)) is due Sat 09:00. Only qualified instrument for batch release assay.",
      "bullets": [
        "INC-4471 (P2, Vendor (Agilex)) is due Sat 09:00.",
        "Only qualified instrument for batch release assay."
      ],
      "action": "Confirm with Vendor (Agilex) that INC-4471 will be done before Sat 09:00.",
      "evidence": "INC-4471 due 09:00 today",
      "clash": false,
      "tags": [
        {
          "key": "due_soon",
          "label": "Due soon"
        }
      ],
      "due_by": "2026-11-07T09:00:00",
      "due_label": "Due by Sat 09:00 · 2 h left",
      "overdue": false,
      "dismissed_earlier_now_worse": false
    },
    {
      "rank": 5,
      "asset_id": "BAL-03",
      "title": "BAL-03 calibration due Sat 17:00",
      "why": "Site rule: it can't be used after its calibration is due. CAL-0932 (P3, Metrology) is due Sat 17:00.",
      "bullets": [
        "Site rule: it can't be used after its calibration is due.",
        "CAL-0932 (P3, Metrology) is due Sat 17:00."
      ],
      "action": "Confirm with Metrology that CAL-0932 will be done before Sat 17:00, or tag BAL-03 out of use.",
      "evidence": "CAL-0932 due 17:00 today",
      "clash": false,
      "tags": [
        {
          "key": "due_soon",
          "label": "Due soon"
        }
      ],
      "due_by": "2026-11-07T17:00:00",
      "due_label": "Due by Sat 17:00 · 10 h left",
      "overdue": false,
      "dismissed_earlier_now_worse": false
    }
  ],
  "carried_over": [],
  "timeline": {
    "start": "19:00",
    "end": "07:00",
    "minutes": 720,
    "summary": "The night from 19:00 to 07:00: 14 alerts and 10 note lines. 5 alerts came after a note saying things were fine, on FRZ-12 and WFI-LOOP-1.",
    "rows": [
      {
        "id": "FRZ-12",
        "description": "-80 °C freezer · GMP",
        "trend": {
          "higher_is_worse": true,
          "unit": "°C",
          "limit": -70.0,
          "points": [
            {
              "minutes": 123.2,
              "value": -64.8,
              "label": "-64.8 °C"
            },
            {
              "minutes": 254.67,
              "value": -63.1,
              "label": "-63.1"
            },
            {
              "minutes": 461.15,
              "value": -62.5,
              "label": "-62.5"
            },
            {
              "minutes": 679.73,
              "value": -61.9,
              "label": "-61.9 / -70.0"
            }
          ]
        }
      },
      {
        "id": "WFI-LOOP-1",
        "description": "Water for Injection distribution loop",
        "trend": null
      },
      {
        "id": "CH-2-P3",
        "description": "Chiller pump",
        "trend": {
          "higher_is_worse": true,
          "unit": "mm/s",
          "limit": 9.0,
          "points": [
            {
              "minutes": 387.92,
              "value": 6.8,
              "label": "6.8 mm/s"
            },
            {
              "minutes": 571.03,
              "value": 7.4,
              "label": "7.4"
            },
            {
              "minutes": 658.0,
              "value": 8.1,
              "label": "8.1 / 9.0"
            }
          ]
        }
      },
      {
        "id": "HPLC-07",
        "description": "HPLC",
        "trend": null
      },
      {
        "id": "BAL-03",
        "description": "Analytical balance",
        "trend": null
      },
      {
        "id": "Other",
        "description": "Everything else",
        "trend": null
      }
    ]
  },
  "events": [
    {
      "kind": "note",
      "time": "19:20",
      "minutes": 20.0,
      "asset_id": "AHU-4",
      "row": "Other",
      "system": "Shift notes",
      "text": "walked round, all quiet. HVAC AHU-4 filter dP a bit high, within limits, just noting.",
      "key_words": "within limits",
      "reassuring": true,
      "clash": false
    },
    {
      "kind": "alert",
      "time": "19:22",
      "minutes": 22.0,
      "asset_id": "AHU-4",
      "row": "Other",
      "system": "BMS",
      "severity": "info",
      "text": "Filter differential pressure 210 Pa (alarm 250 Pa)",
      "value": 210.0,
      "clash": false
    },
    {
      "kind": "alert",
      "time": "21:03",
      "minutes": 123.2,
      "asset_id": "FRZ-12",
      "row": "FRZ-12",
      "system": "EMS",
      "severity": "high",
      "text": "Temperature -64.8C above alarm limit -70C",
      "value": -64.8,
      "clash": false
    },
    {
      "kind": "note",
      "time": "21:05",
      "minutes": 125.0,
      "asset_id": "FRZ-12",
      "row": "FRZ-12",
      "system": "Shift notes",
      "text": "FRZ-12 (-80 freezer, QC retained samples) temp alarm. Reset it, temp came back down. Seems ok.",
      "key_words": "seems ok",
      "reassuring": true,
      "clash": true
    },
    {
      "kind": "alert",
      "time": "22:38",
      "minutes": 218.0,
      "asset_id": "PRN-QC-02",
      "row": "Other",
      "system": "IT",
      "severity": "low",
      "text": "Toner empty",
      "value": null,
      "clash": false
    },
    {
      "kind": "note",
      "time": "22:40",
      "minutes": 220.0,
      "asset_id": "PRN-QC-02",
      "row": "Other",
      "system": "Shift notes",
      "text": "printer in QC office out of toner again, left note for admin.",
      "key_words": "out of toner",
      "reassuring": false,
      "clash": false
    },
    {
      "kind": "alert",
      "time": "23:14",
      "minutes": 254.67,
      "asset_id": "FRZ-12",
      "row": "FRZ-12",
      "system": "EMS",
      "severity": "high",
      "text": "Temperature -63.1C above alarm limit -70C",
      "value": -63.1,
      "clash": true
    },
    {
      "kind": "note",
      "time": "23:15",
      "minutes": 255.0,
      "asset_id": "FRZ-12",
      "row": "FRZ-12",
      "system": "Shift notes",
      "text": "FRZ-12 alarmed again, reset again, door was shut properly. Prob sensor? Will mention to day shift.",
      "key_words": "prob sensor?",
      "reassuring": true,
      "clash": true
    },
    {
      "kind": "alert",
      "time": "01:27",
      "minutes": 387.92,
      "asset_id": "CH-2-P3",
      "row": "CH-2-P3",
      "system": "BMS",
      "severity": "medium",
      "text": "Pump vibration 6.8 mm/s (warn 6.0, alarm 9.0)",
      "value": 6.8,
      "clash": false
    },
    {
      "kind": "note",
      "time": "01:30",
      "minutes": 390.0,
      "asset_id": "CH-2-P3",
      "row": "CH-2-P3",
      "system": "Shift notes",
      "text": "chiller CH-2 pump 3 making a grinding noise on and off. Vibration looks a bit up. Will log it tmrw if it keeps going.",
      "key_words": "will log it tmrw",
      "reassuring": false,
      "clash": false
    },
    {
      "kind": "alert",
      "time": "02:41",
      "minutes": 461.15,
      "asset_id": "FRZ-12",
      "row": "FRZ-12",
      "system": "EMS",
      "severity": "high",
      "text": "Temperature -62.5C above alarm limit -70C",
      "value": -62.5,
      "clash": true
    },
    {
      "kind": "alert",
      "time": "03:09",
      "minutes": 489.78,
      "asset_id": "WFI-LOOP-1",
      "row": "WFI-LOOP-1",
      "system": "WFI-SCADA",
      "severity": "high",
      "text": "Conductivity 1.6 uS/cm exceeds limit 1.3 uS/cm (duration 6s)",
      "value": 1.6,
      "clash": false
    },
    {
      "kind": "note",
      "time": "03:10",
      "minutes": 490.0,
      "asset_id": "WFI-LOOP-1",
      "row": "WFI-LOOP-1",
      "system": "Shift notes",
      "text": "WFI loop conductivity blipped, came straight back in spec. Didn't raise anything as it was only a few secs.",
      "key_words": "only a few secs",
      "reassuring": true,
      "clash": true
    },
    {
      "kind": "alert",
      "time": "03:52",
      "minutes": 532.33,
      "asset_id": "WFI-LOOP-1",
      "row": "WFI-LOOP-1",
      "system": "WFI-SCADA",
      "severity": "high",
      "text": "Conductivity 1.5 uS/cm exceeds limit 1.3 uS/cm (duration 4s)",
      "value": 1.5,
      "clash": true
    },
    {
      "kind": "note",
      "time": "04:00",
      "minutes": 540.0,
      "asset_id": "HPLC-07",
      "row": "HPLC-07",
      "system": "Shift notes",
      "text": "HPLC-07 still down from yesterday, vendor engineer booked for this morning apparently. Lab said they need it for the batch 2611 release test.",
      "key_words": "vendor engineer booked",
      "reassuring": false,
      "clash": false
    },
    {
      "kind": "alert",
      "time": "04:31",
      "minutes": 571.03,
      "asset_id": "CH-2-P3",
      "row": "CH-2-P3",
      "system": "BMS",
      "severity": "medium",
      "text": "Pump vibration 7.4 mm/s (warn 6.0, alarm 9.0)",
      "value": 7.4,
      "clash": false
    },
    {
      "kind": "alert",
      "time": "04:58",
      "minutes": 598.55,
      "asset_id": "WFI-LOOP-1",
      "row": "WFI-LOOP-1",
      "system": "WFI-SCADA",
      "severity": "high",
      "text": "Conductivity 1.4 uS/cm exceeds limit 1.3 uS/cm (duration 5s)",
      "value": 1.4,
      "clash": true
    },
    {
      "kind": "note",
      "time": "05:20",
      "minutes": 620.0,
      "asset_id": "DOOR-LAB-B",
      "row": "Other",
      "system": "Shift notes",
      "text": "cleaners propped the lab B door open, alarm, closed it.",
      "key_words": "closed it",
      "reassuring": true,
      "clash": false
    },
    {
      "kind": "alert",
      "time": "05:21",
      "minutes": 621.17,
      "asset_id": "DOOR-LAB-B",
      "row": "Other",
      "system": "Access",
      "severity": "low",
      "text": "Door held open > 60s",
      "value": 60.0,
      "clash": false
    },
    {
      "kind": "alert",
      "time": "05:58",
      "minutes": 658.0,
      "asset_id": "CH-2-P3",
      "row": "CH-2-P3",
      "system": "BMS",
      "severity": "medium",
      "text": "Pump vibration 8.1 mm/s (warn 6.0, alarm 9.0)",
      "value": 8.1,
      "clash": false
    },
    {
      "kind": "note",
      "time": "06:10",
      "minutes": 670.0,
      "asset_id": "BAL-03",
      "row": "BAL-03",
      "system": "Shift notes",
      "text": "BAL-03 balance calibration sticker says due today.",
      "key_words": "due today",
      "reassuring": false,
      "clash": false
    },
    {
      "kind": "alert",
      "time": "06:19",
      "minutes": 679.73,
      "asset_id": "FRZ-12",
      "row": "FRZ-12",
      "system": "EMS",
      "severity": "high",
      "text": "Temperature -61.9C above alarm limit -70C",
      "value": -61.9,
      "clash": true
    },
    {
      "kind": "alert",
      "time": "06:30",
      "minutes": 690.0,
      "asset_id": "FRZ-07",
      "row": "Other",
      "system": "EMS",
      "severity": "info",
      "text": "Scheduled defrost cycle complete",
      "value": null,
      "clash": false
    },
    {
      "kind": "note",
      "time": "06:45",
      "minutes": 705.0,
      "asset_id": null,
      "row": "Other",
      "system": "Shift notes",
      "text": "handing over. Quiet enough night overall.",
      "key_words": "quiet enough",
      "reassuring": true,
      "clash": false
    }
  ],
  "recent_handovers": {
    "sample": true,
    "rows": [
      {
        "time": "Fri 19:00",
        "direction": "Day → Night",
        "acknowledged": 4,
        "total": 4
      },
      {
        "time": "Fri 07:00",
        "direction": "Night → Day",
        "acknowledged": 5,
        "total": 5
      },
      {
        "time": "Thu 19:00",
        "direction": "Day → Night",
        "acknowledged": 3,
        "total": 4
      }
    ]
  }
};
