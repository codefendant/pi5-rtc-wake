# Publish 0.6.0-rc.1

This package is prepared for **codefendant/pi5-rtc-wake**. Preparation is local; this document is not evidence that the repository, release, or image is public.

The application Python files and web assets are unchanged from the Pi-tested 0.6.0-rc.1 ZIP. The app manifest adds only the public repository URL and prebuilt-image address. The image adds a copy of the MIT license; its dependencies and startup command are unchanged. Documentation and CI changes prepare public distribution. Keep the version marked as a public preview.

## Publication checklist

1. Create the **public** GitHub repository `codefendant/pi5-rtc-wake`, with a `main` branch and an initial README. Commit this package's contents at its root, including the `.github` workflows. Keep `pi5_rtc_wake` as the app folder and slug. Do not upload parent directories, local credentials, screenshots, caches, or private helper files.
2. In **Actions → Verify and build Pi Wake & Sleep → Run workflow**, choose `main`, enable **publish**, and run. Backend, DOM, ABI, and browser checks must pass before the arm64 image is built and pushed. Record the commit and completed workflow URL. Ordinary pushes and pull requests do not publish images.
3. Open the owner's GitHub **Packages → pi5-rtc-wake-pi5-rtc-wake-aarch64 → Package settings**. Change the package visibility to **Public**. A public repository alone does not make the first image public. The version is `0.6.0-rc.1` and the full image is `ghcr.io/codefendant/pi5-rtc-wake-pi5-rtc-wake-aarch64:0.6.0-rc.1`.
4. In **Actions → Verify public installation image → Run workflow**, choose `main`. Require a passing anonymous pull, arm64 check, and production Python imports. Record the image digest. This does not replace a real Home Assistant installation test.
5. In **Releases → Draft a new release**, create tag **v0.6.0-rc.1** at the exact verified commit. Use title **Pi 5 Wake & Sleep 0.6.0-rc.1 — public preview**, paste RELEASE_NOTES.md, select **Set as a pre-release**, and publish. GitHub's source ZIP is sufficient; end users install through Home Assistant. A tag push also runs the verified build workflow.
6. Verify anonymous repository/release access and the Add to Home Assistant link on HAOS. Confirm the store shows the correct version and a fresh install downloads the prebuilt image. Update VALIDATION.md with the actual results, then share the installation link.

Do not move published tags or overwrite a version with different application code. New app changes require a new version in both config.yaml and server.py. CI uses the repository's existing `GITHUB_TOKEN`; end users do not create tokens or run commands.

## Stable release

Public preview publication is authorized following the maintainer's Pi 5 result. Removing the preview label still requires the novice installation/update session and applicable physical checks in ACCEPTANCE.md. Do not describe UPS output-return recovery or an explicit NUT shutdown handoff as implemented.
