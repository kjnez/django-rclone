from __future__ import annotations

from django.conf import settings as django_settings
from django.core.management.base import BaseCommand

from django_rclone.rclone import Rclone
from django_rclone.settings import get_setting
from django_rclone.signals import post_media_restore, pre_media_restore


class Command(BaseCommand):
    help = "Restore media files from rclone remote using rclone sync."

    def handle(self, *args: object, **options: object) -> None:
        verbosity = int(options["verbosity"])  # type: ignore[arg-type]

        media_root = django_settings.MEDIA_ROOT
        if not media_root:
            self.stderr.write("MEDIA_ROOT is not configured.")
            raise SystemExit(1)

        rclone = Rclone()
        media_dir = str(get_setting("MEDIA_BACKUP_DIR"))
        remote_src = rclone._remote_path(media_dir)

        pre_media_restore.send(sender=self.__class__)

        if verbosity >= 1:
            self.stdout.write(f"Syncing media from {remote_src} to {media_root}")

        rclone.sync(remote_src, str(media_root))

        post_media_restore.send(sender=self.__class__)

        if verbosity >= 1:
            self.stdout.write(self.style.SUCCESS("Media restore completed."))
