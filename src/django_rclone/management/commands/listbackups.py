from __future__ import annotations

from django.core.management.base import BaseCommand, CommandParser

from django_rclone.filenames import database_from_backup_name, validate_db_filename_template
from django_rclone.rclone import Rclone
from django_rclone.settings import get_setting


class Command(BaseCommand):
    help = "List database and media backups on the rclone remote."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-d",
            "--database",
            default="",
            help="Filter by database alias.",
        )
        parser.add_argument(
            "--media",
            action="store_true",
            help="List media backup contents instead of database backups.",
        )

    def handle(self, *args: object, **options: object) -> None:
        database = str(options["database"])
        media = bool(options["media"])

        rclone = Rclone()

        if media:
            self._list_media(rclone)
        else:
            self._list_db(rclone, database)

    def _list_db(self, rclone: Rclone, database: str) -> None:
        backup_dir = str(get_setting("DB_BACKUP_DIR"))
        template = str(get_setting("DB_FILENAME_TEMPLATE"))
        validate_db_filename_template(template)
        files = rclone.lsjson(backup_dir)
        files = [f for f in files if not f.get("IsDir", False)]

        if database:
            files = [f for f in files if database_from_backup_name(str(f["Name"]), template) == database]

        files.sort(key=lambda f: f["ModTime"], reverse=True)

        if not files:
            self.stdout.write("No database backups found.")
            return

        self.stdout.write(f"{'Name':<50} {'Size':>12} {'Modified':<25}")
        self.stdout.write("-" * 87)
        for f in files:
            size = self._format_size(f.get("Size", 0))
            self.stdout.write(f"{f['Name']:<50} {size:>12} {f['ModTime']:<25}")

    def _list_media(self, rclone: Rclone) -> None:
        media_dir = str(get_setting("MEDIA_BACKUP_DIR"))
        files = rclone.lsjson(media_dir, recursive=True)
        files = [f for f in files if not f.get("IsDir", False)]

        files.sort(key=lambda f: f["Path"])

        if not files:
            self.stdout.write("No media backups found.")
            return

        total_size = sum(f.get("Size", 0) for f in files)
        self.stdout.write(f"Media files: {len(files)}, Total size: {self._format_size(total_size)}")
        self.stdout.write("")
        self.stdout.write(f"{'Path':<60} {'Size':>12}")
        self.stdout.write("-" * 72)
        for f in files:
            size = self._format_size(f.get("Size", 0))
            self.stdout.write(f"{f['Path']:<60} {size:>12}")

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
            size /= 1024  # type: ignore[assignment]
        return f"{size:.1f} PB"
