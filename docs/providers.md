# Storage Providers

This guide covers provider-specific configuration for cloud storage backends that require special setup beyond standard rclone configuration.

## Cloudflare R2

[Cloudflare R2](https://developers.cloudflare.com/r2/) is an S3-compatible object storage service with zero egress fees, making it an excellent choice for Django backups.

### Important: `no_check_bucket` requirement

**Cloudflare R2 requires `no_check_bucket = true` in your rclone configuration.** Without this setting, uploads will fail with 403 Access Denied errors even when your API token has the correct permissions.

This is because R2's permission model doesn't allow bucket existence checks when using Object Read & Write permissions. Setting `no_check_bucket = true` tells rclone to skip the bucket check and proceed directly to uploading.

### Step 1: Create R2 API Token

1. Go to **Cloudflare Dashboard → R2 → Manage R2 API Tokens**
2. Click **Create API Token**
3. Configure the token:
   - **Permissions**: Object Read & Write (recommended) or Admin Read & Write
   - **Bucket**: Select specific bucket(s) or apply to all buckets
4. Copy the **Access Key ID** and **Secret Access Key**

**Permission options:**
- **Object Read & Write** - Sufficient for django-rclone operations (recommended)
- **Admin Read & Write** - Includes bucket management permissions (not needed for backups)

For better security, apply the token to specific buckets rather than all buckets.

### Step 2: Configure rclone remote

Find your Account ID in **Cloudflare Dashboard → R2 → Overview** (shown on the right sidebar).

Create the rclone remote with the required `no_check_bucket` setting:

```bash
rclone config create r2_backups s3 \
  provider=Cloudflare \
  access_key_id=YOUR_ACCESS_KEY_ID \
  secret_access_key=YOUR_SECRET_ACCESS_KEY \
  endpoint=https://ACCOUNT_ID.r2.cloudflarestorage.com \
  no_check_bucket=true
```

Replace:
- `YOUR_ACCESS_KEY_ID` with your R2 Access Key ID
- `YOUR_SECRET_ACCESS_KEY` with your R2 Secret Access Key
- `ACCOUNT_ID` with your Cloudflare Account ID

**Interactive configuration:**

Alternatively, use `rclone config` interactively:

```bash
rclone config
```

1. Choose **n) New remote**
2. Name: `r2_backups`
3. Storage type: `s3`
4. Provider: `Cloudflare`
5. Enter your access key ID and secret access key
6. When prompted for advanced config, choose **y) Yes**
7. Set `no_check_bucket = true`
8. Accept defaults for other settings

### Step 3: Configure Django settings

```python
DJANGO_RCLONE = {
    "REMOTE": "r2_backups:my-backup-bucket/django-backups",
}
```

Replace `my-backup-bucket` with your actual R2 bucket name.

### Verification

Test your configuration:

```bash
# List remote contents
rclone ls r2_backups:my-backup-bucket

# Run a test backup
python manage.py dbbackup

# Verify it appears in the remote
python manage.py listbackups
```

If you see 403 Access Denied errors, verify that `no_check_bucket = true` is set in your rclone config:

```bash
rclone config show r2_backups
```

You should see `no_check_bucket = true` in the output.

### Encryption and compression

You can layer encryption and compression on top of your R2 remote:

```bash
# Add compression
rclone config create r2_compressed compress remote=r2_backups:my-backup-bucket

# Add encryption (on top of compression)
rclone config create r2_secure crypt remote=r2_compressed: password=$(rclone obscure your-password)
```

Then use the layered remote:

```python
DJANGO_RCLONE = {
    "REMOTE": "r2_secure:django-backups",
}
```

## Other providers

Most rclone storage providers work with django-rclone without special configuration. Simply configure the remote with `rclone config` and reference it in `DJANGO_RCLONE["REMOTE"]`.

If you encounter provider-specific issues or have configuration notes to share, please [open an issue](https://github.com/kjnez/django-rclone/issues) or submit a pull request to add documentation.
