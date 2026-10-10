# Publish Pi 5 Wake & Sleep

The public source repository is **codefendant/pi5-rtc-wake**. The app Python files and web assets match the Pi-tested 0.6.0-rc.1 ZIP. Its manifest adds the public repository and image address; the image adds the MIT license without changing dependencies or startup.

## Publish a preview

1. Commit the intended preview to `main` with the exact first line **`[release] 0.6.0-rc.1`** (use the actual version for later previews). Alternatively, use **Actions → Verify and build Pi Wake & Sleep → Run workflow**, choose `main`, and enable **publish**. Ordinary main commits and pull requests run checks without publishing.
2. Require backend, DOM, JavaScript, ABI, and real browser checks to pass. GitHub Actions then builds and pushes the arm64 image using the repository's own token. No personal token is needed.
3. **First publication only:** GitHub makes a new package private by default. Open your GitHub **Packages → pi5-rtc-wake-pi5-rtc-wake-aarch64 → Package settings**, and change its visibility to **Public**. A public repository alone is insufficient. The initial anonymous image check is expected to fail until this is done.
4. Re-run the failed jobs in that publishing workflow. The public-image job pulls with an empty Docker configuration, checks arm64, and imports the actual production modules. The release job runs only after that succeeds and automatically creates **v0.6.0-rc.1** at the verified commit, marked **pre-release**, using RELEASE_NOTES.md. Existing tags at other commits are rejected; an existing matching preview is verified without duplicate publication.
5. Confirm anonymous source/release access and the Add to Home Assistant link on HAOS. Check that a fresh install downloads the prebuilt image and that updating the same installed app preserves settings. Record the workflow URL, commit, image digest, and actual installation result in VALIDATION.md.

The image is `ghcr.io/codefendant/pi5-rtc-wake-pi5-rtc-wake-aarch64:0.6.0-rc.1`. GitHub's release source ZIP is sufficient; end users install through Home Assistant screens. The standalone **Verify public installation image** workflow can be run again when access needs checking.

Do not move published tags or overwrite a version with different app code. New app changes need a new version in both config.yaml and server.py and corresponding release notes. Keep the app folder/slug `pi5_rtc_wake`. Do not publish caches, credentials, private helper files, or personal screenshots.

## Stable release

The maintainer authorized public preview publication after testing on their Pi 5. Removing the preview label still requires the novice installation/update session and applicable physical checks in ACCEPTANCE.md. UPS output-return control and an explicit NUT shutdown handoff are not implemented.
