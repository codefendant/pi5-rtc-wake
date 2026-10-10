#!/usr/bin/env python3
"""Maintainer step: fill in a real repository and generate its install link.

This edits local files only. It does not publish a repository or an image.
End users never run this tool.
"""

import argparse
from pathlib import Path
import re
from urllib.parse import quote


def prepare(directory, repository):
    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", repository)
    if not match or match[2] in (".", ".."):
        raise ValueError("Use the URL of your actual GitHub repository: https://github.com/owner/repository")
    owner, name = match[1], match[2]
    url = f"https://github.com/{owner}/{name}"
    image = f"ghcr.io/{owner.lower()}/{name.lower()}-pi5-rtc-wake-aarch64"
    root = Path(directory)
    config = root / "pi5_rtc_wake" / "config.yaml"
    text = config.read_text()
    text = re.sub(r"^(?:image|url):.*\n?", "", text, flags=re.M)
    config.write_text(text.rstrip() + f"\nurl: {url}\nimage: {image}\n")
    (root / "repository.yaml").write_text(f"name: Pi 5 Wake & Sleep\nurl: {url}\nmaintainer: {owner}\n")
    link = "https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=" + quote(url, safe="")
    (root / "INSTALL.md").write_text(
        "# Install Pi 5 Wake & Sleep\n\n"
        "Public preview. This link works after the repository and matching image are public. See ACCEPTANCE.md for stable-release checks.\n\n"
        f"[Add to Home Assistant]({link})\n\n"
        "1. Open the link and add the repository.\n"
        "2. Find **Pi 5 Wake & Sleep** in the app store and select **Install**.\n"
        "3. Turn off **Protection mode**, enable **Start on boot** and **Show in sidebar**, then select **Start**.\n"
        "4. Select **Open Web UI** and follow the checks, preparation, and wake test.\n"
        "5. Create dates and repeats in Home Assistant's Calendar, select that calendar, review the off periods, and enable scheduling.\n\n"
        "If an app or system update is required, use Home Assistant's update screens and return to setup afterward.\n")
    return url, image, link


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", help="Actual GitHub repository URL")
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        url, image, link = prepare(args.directory, args.repository)
    except ValueError as error:
        parser.error(str(error))
    print(f"Prepared local repository metadata for {url}\nImage: {image}\nInstall link: {link}\nNothing has been published.")
