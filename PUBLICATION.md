# Publish Pi 5 Wake & Sleep

The public source repository is **codefendant/pi5-rtc-wake**. Version 0.6.0-rc.1 was tested by the maintainer on their Pi and published with a matching public image. Version 0.7.0-rc.1 adds opt-in phone messages and schema 7 while retaining the existing Calendar/UPS behavior. Real phone delivery requires a separate check; the earlier Pi report does not validate this new feature.

Version [0.7.0-rc.1](https://github.com/codefendant/pi5-rtc-wake/releases/tag/v0.7.0-rc.1) is published. [Run 38035745972](https://github.com/codefendant/pi5-rtc-wake/actions/runs/38035745972) passed all checks, including anonymous arm64 download and production imports. The pushed/pulled digest is `sha256:ee68f1cb446e1b47b31d666d3cead9c006e0a160b672e44225cae559d3cb102c`. See VALIDATION.md for the exact commit and remaining physical checks.

Version [0.7.0-rc.2](https://github.com/codefendant/pi5-rtc-wake/releases/tag/v0.7.0-rc.2) is published as a guidance repair for the confirmed Protection mode installation issue. [Run 38038717809](https://github.com/codefendant/pi5-rtc-wake/actions/runs/38038717809) passed every verification/publication gate. The pushed and anonymously downloaded image digest is `sha256:fc9146c93c1d9e70cf6dcc3777771c8be2b40fbb4d456354d4d93d4d1d572cdf`. The tag points to `25d335098154ae8760b3caaafa84e541a2f30b2e`; the existing 0.7.0-rc.1 tag was read back unchanged.

## Publish a preview

1. Commit the intended preview to `main` with the exact first line **`[release] 0.7.0-rc.2`** (use the actual version for later previews). Alternatively, use **Actions → Verify and build Pi Wake & Sleep → Run workflow**, choose `main`, and enable **publish**. Ordinary main commits and pull requests run checks without publishing.
2. Require backend, DOM, JavaScript, ABI, and real browser checks to pass. GitHub Actions then builds and pushes the arm64 image using the repository's own token. No personal token is needed.
3. **If the anonymous check reports a private image:** open GitHub **Packages → pi5-rtc-wake-pi5-rtc-wake-aarch64 → Package settings**, and change visibility to **Public**. A public repository alone is not proof of public image access. The initial 0.6.0-rc.1 check passed anonymously; no extra visibility change was needed from this workspace.
4. If a visibility change was needed, re-run the failed jobs. The public-image job pulls with an empty Docker configuration, checks arm64, and imports the actual production modules. The release job runs only after that succeeds and automatically creates **v0.7.0-rc.2** at the verified commit, marked **pre-release**, using RELEASE_NOTES.md. Existing tags at other commits are rejected; an existing matching preview is verified without duplicate publication.
5. Confirm anonymous source/release access and the Add to Home Assistant link on HAOS. Check that a fresh install downloads the prebuilt image and that updating the same installed app preserves settings. Record the workflow URL, commit, image digest, and actual installation result in VALIDATION.md.

The image is `ghcr.io/codefendant/pi5-rtc-wake-pi5-rtc-wake-aarch64:0.7.0-rc.2`. GitHub's release source ZIP is sufficient; end users install through Home Assistant screens. The standalone **Verify public installation image** workflow can be run again when access needs checking.

Do not move published tags or overwrite a version with different app code. New app changes need a new version in both config.yaml and server.py and corresponding release notes. Keep the app folder/slug `pi5_rtc_wake`. Do not publish caches, credentials, private helper files, or personal screenshots.

## Stable release

The maintainer authorized public preview publication after testing on their Pi 5. Removing the preview label still requires the novice installation/update session and applicable physical checks in ACCEPTANCE.md. UPS output-return control and an explicit NUT shutdown handoff are not implemented.
