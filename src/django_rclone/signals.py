from django.dispatch import Signal

pre_db_backup = Signal()
post_db_backup = Signal()
pre_db_restore = Signal()
post_db_restore = Signal()
pre_media_backup = Signal()
post_media_backup = Signal()
pre_media_restore = Signal()
post_media_restore = Signal()
