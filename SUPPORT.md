# Help and preview feedback

Start with the [installation guide](INSTALL.md) or [update guide](UPDATE.md). Updates use the same installed app; deleting the app is a fresh installation.

## Report a problem

[Open a bug report](https://github.com/codefendant/pi5-rtc-wake/issues/new?template=bug_report.yml). Tell us what you selected, what happened, and what you expected. Screenshots help when a button or message is confusing.

Find diagnostic text at **Settings → Apps → Pi 5 Wake & Sleep → Open Web UI → Maintenance and connection repair → Details for support**. Copy that text into the report. For Home Assistant versions, use **Settings → About**. You can leave a version blank if you cannot find it.

Reports are public. Remove passwords, tokens, private addresses, and personal readings from anything you attach. Do not send a Home Assistant backup.

## Suggest an improvement

[Request a feature](https://github.com/codefendant/pi5-rtc-wake/issues/new?template=feature_request.yml). Describe the task you want to complete and why it matters. Installation and everyday usability feedback are especially useful during this preview.

## Help test the preview

Try the installation guide on a supported Pi 5 with Home Assistant OS. Report any step that needed an explanation, any message that did not tell you what to do next, and whether the first sleep and wake cycle returned automatically. For an ordinary update, check that your settings, Calendar dates, and personal cards remain present.

The preview supports the Pi 5's built-in RTC. External RTC modules, PoE outlet control, and complete UPS output-off/return control are outside this release. [UPS_RECOVERY.md](UPS_RECOVERY.md) explains the existing conditional recovery behavior.
