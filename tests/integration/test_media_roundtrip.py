from __future__ import annotations

import os

import pytest
from django.core.management import call_command
from django.test.utils import override_settings

from .conftest import requires_rclone


@requires_rclone
@pytest.mark.integration
def test_mediabackup_then_mediarestore(tmp_path):
    """Full media backup → delete → restore → verify cycle."""
    media_root = str(tmp_path / "media")
    rclone_remote = str(tmp_path / "rclone_remote")
    os.makedirs(media_root)

    # Create some media files
    subdir = os.path.join(media_root, "images")
    os.makedirs(subdir)
    with open(os.path.join(media_root, "readme.txt"), "w") as f:
        f.write("Hello, media!")
    with open(os.path.join(subdir, "photo.txt"), "w") as f:
        f.write("Not a real photo")

    django_rclone_settings = {"REMOTE": rclone_remote}
    with override_settings(
        MEDIA_ROOT=media_root,
        DJANGO_RCLONE=django_rclone_settings,
    ):
        call_command("mediabackup", verbosity=0)

        # Delete media files
        for root, dirs, files in os.walk(media_root, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))

        assert not os.listdir(media_root)

        call_command("mediarestore", verbosity=0)

        # Verify files restored
        assert os.path.isfile(os.path.join(media_root, "readme.txt"))
        assert os.path.isfile(os.path.join(subdir, "photo.txt"))
        with open(os.path.join(media_root, "readme.txt")) as f:
            assert f.read() == "Hello, media!"
        with open(os.path.join(subdir, "photo.txt")) as f:
            assert f.read() == "Not a real photo"
