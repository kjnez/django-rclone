# Management Commands

django-rclone provides five management commands. All follow the same conventions as built-in Django commands, supporting `--verbosity`, `--no-color`, and other standard options.

## dbbackup

Dump a database and upload it to the rclone remote.

```bash
python manage.py dbbackup [options]
```

**How it works:** The command gets a connector for the database, runs the native dump tool (e.g., `pg_dump`), and pipes stdout directly into `rclone rcat` -- streaming the dump to the remote with no intermediate files. During finalization, django-rclone drains subprocess pipes via `communicate()` and background stderr readers so large stderr output cannot deadlock the pipeline.

### Options

| Option | Default | Description |
|---|---|---|
| `-d`, `--database` | `default` | Django database alias to back up |
| `--clean` | off | Delete old backups beyond the retention count after backup |

### Examples

```bash
# Back up the default database
python manage.py dbbackup

# Back up a specific database
python manage.py dbbackup --database analytics

# Back up and remove old backups (keeps 10 most recent by default)
python manage.py dbbackup --clean

# Silent mode
python manage.py dbbackup --verbosity 0
```

### Backup file naming

Files are named using `DB_FILENAME_TEMPLATE` and `DB_DATE_FORMAT`:

```
{database}-{datetime}.{ext}
```

For a PostgreSQL `default` database, this produces:

```
default-2024-01-15-120000.dump
```

### Retention cleanup

When `--clean` is passed, the command lists all backups for the database in `DB_BACKUP_DIR`, sorts by modification time, and deletes everything beyond the `DB_CLEANUP_KEEP` count (default: 10).

---

## dbrestore

Download a backup from the rclone remote and restore it into a database.

```bash
python manage.py dbrestore [options]
```

**How it works:** The command runs `rclone cat` to stream the backup file and pipes it into the native restore tool (e.g., `pg_restore`) -- again with no intermediate files. Process finalization uses the same deadlock-safe pipe draining strategy as `dbbackup`.

### Options

| Option | Default | Description |
|---|---|---|
| `-d`, `--database` | *(auto if only one DB)* | Django database alias to restore (required when multiple databases are configured) |
| `-i`, `--input-path` | *(latest)* | Backup filename to restore (relative to `DB_BACKUP_DIR`) |
| `--noinput` | off | Skip the interactive confirmation prompt |

### Examples

```bash
# Restore the most recent backup of the default database
python manage.py dbrestore

# Restore a specific backup file
python manage.py dbrestore --input-path default-2024-01-15-120000.dump

# Restore a different database
python manage.py dbrestore --database analytics

# Restore non-interactively (e.g. scripts/CI)
python manage.py dbrestore --noinput --input-path default-2024-01-15-120000.dump
```

### Automatic latest selection

When `--input-path` is not provided, the command lists all backups in `DB_BACKUP_DIR` matching the database alias, sorts by modification time, and picks the most recent one.

### Confirmation prompt

By default, `dbrestore` prompts for confirmation before restoring. Use `--noinput` to disable the prompt.

---

## mediabackup

Sync Django's `MEDIA_ROOT` to the rclone remote.

```bash
python manage.py mediabackup
```

**How it works:** Runs `rclone sync` from `MEDIA_ROOT` to `REMOTE/MEDIA_BACKUP_DIR/`. This is incremental by default -- only new or changed files are transferred on subsequent runs.

### Examples

```bash
python manage.py mediabackup
```

Requires `MEDIA_ROOT` to be set in your Django settings. The command exits with an error if it is empty.

### Why sync instead of tar?

django-dbbackup archives media into a tar file before uploading. django-rclone uses `rclone sync` instead, which provides:

- **Incremental transfers** -- only changed files are uploaded, saving bandwidth and time
- **No archive overhead** -- no need to tar/untar large media directories
- **Native rclone features** -- bandwidth limiting, parallel transfers, checksumming all work automatically

---

## mediarestore

Sync media files from the rclone remote back to `MEDIA_ROOT`.

```bash
python manage.py mediarestore
```

**How it works:** Runs `rclone sync` in the reverse direction, from `REMOTE/MEDIA_BACKUP_DIR/` to `MEDIA_ROOT`.

### Examples

```bash
python manage.py mediarestore
```

**Warning:** This syncs the remote state to local, which means local files not present on the remote will be deleted. This matches rclone's `sync` semantics. If you need to preserve local files, consider using `rclone copy` instead (not yet exposed as a command option).

---

## listbackups

List backups stored on the rclone remote.

```bash
python manage.py listbackups [options]
```

**How it works:** Runs `rclone lsjson` to get structured file listings and displays them as a formatted table.

### Options

| Option | Default | Description |
|---|---|---|
| `-d`, `--database` | *(all)* | Filter database backups by alias |
| `--media` | off | List media backup contents instead of database backups |

### Examples

```bash
# List all database backups
python manage.py listbackups

# List backups for a specific database
python manage.py listbackups --database default

# List media files on the remote
python manage.py listbackups --media
```

### Output format

Database backups:

```
Name                                               Size     Modified
---------------------------------------------------------------------------------------
default-2024-01-15-120000.dump                      1.2 MB   2024-01-15T12:00:00Z
default-2024-01-14-120000.dump                      1.1 MB   2024-01-14T12:00:00Z
```

Media files:

```
Media files: 42, Total size: 156.3 MB

Path                                                         Size
------------------------------------------------------------------------
uploads/photos/image001.jpg                                   2.4 MB
uploads/photos/image002.jpg                                   1.8 MB
```
