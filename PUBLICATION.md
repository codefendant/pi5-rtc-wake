# Publish Pi 5 Wake & Sleep

The public repository is **codefendant/pi5-rtc-wake**. **0.10.0 Public Preview** packages the tested 0.10.0-rc.6 behavior and the approved public introduction. The maintainer authorized formal preview publication after successful repeated fresh installations on their Pi 5. The app remains experimental; every release created by the workflow is marked pre-release.

[VALIDATION.md](VALIDATION.md) records exact source commits, image digests, automated checks, and separately identified hardware reports. Earlier publication records are retained there.

## Verified 0.10.0 publication

[Public preview v0.10.0](https://github.com/codefendant/pi5-rtc-wake/releases/tag/v0.10.0) was published at **2026-10-13T15:44:55Z** after [run 38424015106](https://github.com/codefendant/pi5-rtc-wake/actions/runs/38424015106) passed every gate. Tag `93a76b8d8ff49a0dce0eb14753e2c2268d9c03a7` has the identical verified candidate tree `985f0481609e9aabcc78e0ab0b6b438627bbf74b`. The pushed and anonymously pulled image digest is `sha256:f0c64ad22f4feaea812d0b3b9d8c9ef3d429da7b2e4a391db4ac37b472f3800e`; architecture/version/import checks passed. The earlier rc.6 tag is unchanged.

The [introduction page](https://pi-wake-sleep.humblejam3.chatgpt.site/) is deployed and public. Public bug/suggestion forms and a [ready-to-post announcement](ANNOUNCEMENT.md) are available. No community post or person-directed invitation is sent by this release process.

## Publish a preview

1. Prepare all four app/companion version fields, public documentation, release notes, and changelog. Keep the existing repository and app slug `pi5_rtc_wake` so ordinary updates retain settings.
2. Open a pull request. Require backend, DOM, JavaScript, RTC ABI, Chromium, actual Home Assistant Core, and arm64 candidate checks to pass. Review the exact candidate source and screenshots.
3. Merge to `main` with the exact first line **`[release] 0.10.0`**, using the actual version for later releases. Ordinary commits and pull requests run checks without publishing. Manual publication is also available from the main branch through **Actions → Verify and build Pi Wake & Sleep → Run workflow → publish**.
4. GitHub Actions repeats the gates, builds/pushes the arm64 image, anonymously downloads it with an empty Docker configuration, and checks architecture, version, and production imports. No personal token is needed.
5. Only after those checks pass, the workflow creates **v0.10.0**, non-draft and marked **pre-release**. A plain version is permitted for a formal preview; the pre-release flag is still required. Existing tags at another commit are rejected.
6. Verify release/tag/source identity, pushed and pulled image digests, and unchanged earlier tags. Record the results in an ordinary documentation commit; do not republish an unchanged version.
7. Verify the public landing-page audience and installation/documentation/feedback links. Record actual installation and same-app update reports separately from automated checks.

Public image: `ghcr.io/codefendant/pi5-rtc-wake-pi5-rtc-wake-aarch64:0.10.0`. If the anonymous pull reports a private package, set its visibility to Public in GitHub Packages and rerun the failed check. A public source repository does not by itself prove public image access.

Do not move published tags or overwrite a version with different app code. Keep credentials, personal screenshots, and private helper files out of publication. [SUPPORT.md](SUPPORT.md) supplies public feedback links.

## Stable release

Removing the preview/experimental designations remains separate work under [ACCEPTANCE.md](ACCEPTANCE.md), including an independent novice session and applicable physical checks. UPS output-return control and an explicit NUT shutdown handoff remain outside this release.
