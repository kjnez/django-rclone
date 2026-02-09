from __future__ import annotations

from datetime import UTC, datetime

from django.conf import settings as django_settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from django_rclone.db.registry import get_connector
from django_rclone.exceptions import ConnectorError, RcloneError
from django_rclone.filenames import database_from_backup_name, validate_db_filename_template
from django_rclone.process_utils import begin_stderr_drain, close_process_stdout, finish_process
from django_rclone.rclone import Rclone
from django_rclone.settings import get_setting
from django_rclone.signals import post_db_restore, pre_db_restore


class Command(BaseCommand):
    help = "Restore database from rclone remote."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-d",
            "--database",
            default="",
            help="Database alias to restore. Required when multiple databases are configured.",
        )
        parser.add_argument(
            "-i",
            "--input-path",
            default="",
            help="Specific backup file path (relative to backup dir). If empty, uses the latest.",
        )
        parser.add_argument(
            "--noinput",
            action="store_false",
            dest="interactive",
            default=True,
            help="Do not prompt for confirmation before restoring.",
        )

    def handle(self, *args: object, **options: object) -> None:
        database = str(options["database"])
        input_path = str(options["input_path"])
        interactive = bool(options["interactive"])
        verbosity = int(options["verbosity"])  # type: ignore[arg-type]

        if not database:
            if len(django_settings.DATABASES) > 1:
                raise CommandError(
                    "Multiple databases are configured. Please specify which one to restore with --database."
                )
            database = next(iter(django_settings.DATABASES))
        elif database not in django_settings.DATABASES:
            raise CommandError(f"Database '{database}' is not configured.")

        connector = get_connector(database)
        rclone = Rclone()
        backup_dir = str(get_setting("DB_BACKUP_DIR"))
        template = str(get_setting("DB_FILENAME_TEMPLATE"))
        date_format = str(get_setting("DB_DATE_FORMAT"))
        validate_db_filename_template(template)

        if not input_path:
            input_path = self._find_latest(rclone, database, backup_dir, template, date_format)
        input_path = self._validate_input_path(input_path)
        backup_database = database_from_backup_name(input_path, template, date_format=date_format)
        if backup_database is not None and backup_database != database:
            raise CommandError(
                f"Backup '{input_path}' appears to belong to database '{backup_database}', not '{database}'."
            )

        remote_path = f"{backup_dir}/{input_path}"

        if interactive:
            answer = input(f"Restore database '{database}' from '{remote_path}'? [y/N] ").strip().lower()
            if answer not in {"y", "yes"}:
                self.stdout.write("Restore cancelled.")
                raise SystemExit(0)

        pre_db_restore.send(sender=self.__class__, database=database, path=remote_path)

        if verbosity >= 1:
            self.stdout.write(f"Restoring database '{database}' from {remote_path}")

        # Stream from rclone to restore process
        try:
            cat_proc = rclone.cat(remote_path)
        except RcloneError as exc:
            self.stderr.write(f"rclone cat failed: {exc.stderr}")
            raise SystemExit(1) from exc
        assert cat_proc.stdout is not None
        try:
            restore_proc = connector.restore(stdin=cat_proc.stdout)
        except ConnectorError as exc:
            close_process_stdout(cat_proc)
            _, cat_stderr = finish_process(cat_proc, stderr_drain=begin_stderr_drain(cat_proc))
            stderr = cat_stderr.decode(errors="replace") if cat_stderr else ""
            if stderr:
                self.stderr.write(f"rclone cat failed: {stderr}")
            self.stderr.write(f"Database restore failed: {exc}")
            raise SystemExit(1) from exc
        cat_stderr_drain = begin_stderr_drain(cat_proc)
        close_process_stdout(cat_proc)

        # Drain restore output while rclone streams dump data into restore stdin.
        _, restore_stderr = finish_process(restore_proc)
        _, cat_stderr = finish_process(cat_proc, stderr_drain=cat_stderr_drain)

        if cat_proc.returncode != 0:
            stderr = cat_stderr.decode(errors="replace") if cat_stderr else ""
            self.stderr.write(f"rclone cat failed: {stderr}")
            raise SystemExit(1)

        if restore_proc.returncode != 0:
            stderr = restore_stderr.decode(errors="replace") if restore_stderr else ""
            self.stderr.write(f"Database restore failed: {stderr}")
            raise SystemExit(1)

        post_db_restore.send(sender=self.__class__, database=database)

        if verbosity >= 1:
            self.stdout.write(self.style.SUCCESS(f"Restore completed from: {remote_path}"))

    def _find_latest(self, rclone: Rclone, database: str, backup_dir: str, template: str, date_format: str) -> str:
        files = rclone.lsjson(backup_dir)
        db_files = [
            f
            for f in files
            if not f.get("IsDir", False)
            and database_from_backup_name(str(f["Name"]), template, date_format=date_format) == database
        ]
        if not db_files:
            self.stderr.write(f"No backups found for database '{database}'")
            raise SystemExit(1)
        db_files.sort(key=lambda f: self._parse_modtime(str(f["ModTime"])), reverse=True)
        return db_files[0]["Name"]

    def _validate_input_path(self, input_path: str) -> str:
        if not input_path:
            raise CommandError("--input-path cannot be empty.")
        if "\\" in input_path or input_path.startswith("/"):
            raise CommandError("--input-path must be a relative POSIX-style path.")
        parts = [part for part in input_path.split("/") if part]
        if any(part in {".", ".."} for part in parts):
            raise CommandError("--input-path cannot contain '.' or '..' path segments.")
        if not parts:  # pragma: no cover - guarded by the empty check above
            raise CommandError("--input-path must point to a file under DB_BACKUP_DIR.")
        return "/".join(parts)

    @staticmethod
    def _parse_modtime(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=UTC)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
