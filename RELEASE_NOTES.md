# Pi 5 Wake & Sleep 0.10.0-rc.3 — First sleep & wake guidance

The first wake test now explains what will happen before the user starts it: the Pi and Home Assistant shut down after a 30-second countdown, Home Assistant and automations are unavailable for roughly ten minutes plus startup time, and the RTC is set to start the Pi again. The setup card emphasizes the first sleep and wake cycle, and its confirmation repeats the downtime, continuous-power requirement, and manual-return guidance.

During the countdown, the setup card shows the armed wake time. After returning, it explains how to confirm whether the Pi woke automatically and continue onboarding. Scheduling and UPS recovery still turn off for the test and must be reviewed afterward.

The ten-minute alarm, countdown, cancellation, wake evidence, and shutdown policy are unchanged. Schema 11, Calendar dates, existing settings, phone choices, Assist permissions, device-waking settings, and personal cards are retained. No new physical wake test is required just for this update.

Update the same app to 0.10.0-rc.3, Stop → Start, then use **Web UI → Maintenance and connection repair → Update / reconnect dashboard**. Restart Home Assistant if requested and refresh the browser. A first installation still finishes in **Devices & services → Discovered → Pi Wake & Sleep → Add → Submit → Finish**. Do not uninstall an existing app to update it.

This remains a public preview. Automated checks simulate Pi/UPS hardware; the new copy does not establish physical wake or UPS recovery on an untested supply path.
