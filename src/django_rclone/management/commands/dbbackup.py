from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from uuid import uuid4

from django.conf import settings as django_settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from django_rclone.db.registry import get_connector
from django_rclone.exceptions import ConnectorError, RcloneError
from django_rclone.filenames import database_from_backup_name, validate_db_filename_template
from django_rclone.process_utils import begin_stderr_drain, finish_process
from django_rclone.rclone import Rclone
from django_rclone.settings import get_setting
from django_rclone.signals import post_db_backup, pre_db_backup


class Command(BaseCommand):
    help = "Backup database to rclone remote."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-d",
            "--database",
            default="default",
            help="Database alias to backup (default: 'default').",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Remove old backups beyond retention count after backup.",
        )

    def handle(self, *args: object, **options: object) -> None:
        database = str(options["database"])
        clean = bool(options["clean"])
        verbosity = int(options["verbosity"])  # type: ignore[arg-type]

        if database not in django_settings.DATABASES:
            raise CommandError(f"Database '{database}' is not configured.")

        connector = get_connector(database)
        rclone = Rclone()

        # Build filename
        now = datetime.now(tz=UTC)
        template = str(get_setting("DB_FILENAME_TEMPLATE"))
        validate_db_filename_template(template)
        date_format = str(get_setting("DB_DATE_FORMAT"))
        try:
            filename = template.format(
                database=database,
                datetime=now.strftime(date_format),
                ext=connector.extension,
            )
        except KeyError as exc:
            missing = exc.args[0]
            raise CommandError(f"DB_FILENAME_TEMPLATE references unknown placeholder: {missing}") from exc
        if "/" in filename or "\\" in filename:
            raise CommandError("DB_FILENAME_TEMPLATE must render a filename, not a path.")
        backup_dir = str(get_setting("DB_BACKUP_DIR"))
        remote_path = f"{backup_dir}/{filename}"
        temp_remote_path = f"{remote_path}.partial-{uuid4().hex}"

        pre_db_backup.send(sender=self.__class__, database=database)

        if verbosity >= 1:
            self.stdout.write(f"Backing up database '{database}' to {remote_path}")

        # Dump database and stream to a temporary remote object first.
        try:
            dump_proc = connector.dump()
        except ConnectorError as exc:
            self.stderr.write(f"Database dump failed: {exc}")
            raise SystemExit(1) from exc
        assert dump_proc.stdout is not None
        dump_stderr_drain = begin_stderr_drain(dump_proc)
        upload_error: RcloneError | None = None
        try:
            rclone.rcat(temp_remote_path, stdin=dump_proc.stdout)
        except RcloneError as exc:
            upload_error = exc
        finally:
            _, dump_stderr = finish_process(dump_proc, stderr_drain=dump_stderr_drain, close_stdout=True)

        if dump_proc.returncode != 0:
            stderr = dump_stderr.decode(errors="replace") if dump_stderr else ""
            self._safe_delete(rclone, temp_remote_path)
            self.stderr.write(f"Database dump failed: {stderr}")
            raise SystemExit(1)
        if upload_error is not None:
            self._safe_delete(rclone, temp_remote_path)
            self.stderr.write(f"Upload failed: {upload_error.stderr}")
            raise SystemExit(1)
        try:
            rclone.moveto(temp_remote_path, remote_path)
        except RcloneError as exc:
            self._safe_delete(rclone, temp_remote_path)
            self.stderr.write(f"Failed to finalize upload: {exc.stderr}")
            raise SystemExit(1) from exc

        post_db_backup.send(sender=self.__class__, database=database, path=remote_path)

        if verbosity >= 1:
            self.stdout.write(self.style.SUCCESS(f"Backup completed: {remote_path}"))

        if clean:
            self._cleanup(rclone, database, backup_dir, verbosity)

    def _cleanup(self, rclone: Rclone, database: str, backup_dir: str, verbosity: int) -> None:
        keep = int(get_setting("DB_CLEANUP_KEEP"))  # type: ignore[arg-type]
        template = str(get_setting("DB_FILENAME_TEMPLATE"))
        date_format = str(get_setting("DB_DATE_FORMAT"))
        files = rclone.lsjson(backup_dir)
        # Filter to files matching this database
        db_files = [
            f
            for f in files
            if not f.get("IsDir", False)
            and database_from_backup_name(str(f["Name"]), template, date_format=date_format) == database
        ]
        # Sort by modification time descending.
        db_files.sort(key=lambda f: self._parse_modtime(str(f["ModTime"])), reverse=True)

        to_delete = db_files[keep:]
        for f in to_delete:
            path = f"{backup_dir}/{f['Name']}"
            if verbosity >= 1:
                self.stdout.write(f"Removing old backup: {path}")
            rclone.delete(path)

    def _safe_delete(self, rclone: Rclone, path: str) -> None:
        with suppress(RcloneError):
            rclone.delete(path)

    @staticmethod
    def _parse_modtime(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=UTC)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
