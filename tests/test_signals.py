from django_rclone import signals


class TestSignals:
    def test_all_signals_exist(self):
        expected = [
            "pre_db_backup",
            "post_db_backup",
            "pre_db_restore",
            "post_db_restore",
            "pre_media_backup",
            "post_media_backup",
            "pre_media_restore",
            "post_media_restore",
        ]
        for name in expected:
            signal = getattr(signals, name)
            assert signal is not None

    def test_signal_can_connect_and_send(self):
        received: list[dict] = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        signals.pre_db_backup.connect(handler, dispatch_uid="test_signal")
        try:
            signals.pre_db_backup.send(sender=self.__class__, database="default")
            assert len(received) == 1
            assert received[0]["database"] == "default"
        finally:
            signals.pre_db_backup.disconnect(dispatch_uid="test_signal")
