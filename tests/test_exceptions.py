from django_rclone.exceptions import ConnectorError, ConnectorNotFound, DjangoRcloneError, RcloneError


class TestExceptions:
    def test_hierarchy(self):
        assert issubclass(RcloneError, DjangoRcloneError)
        assert issubclass(ConnectorError, DjangoRcloneError)
        assert issubclass(ConnectorNotFound, DjangoRcloneError)

    def test_rclone_error(self):
        err = RcloneError(["rclone", "cat", "remote:file"], 1, "not found")
        assert err.cmd == ["rclone", "cat", "remote:file"]
        assert err.returncode == 1
        assert err.stderr == "not found"
        assert "exit 1" in str(err)
        assert "rclone cat remote:file" in str(err)

    def test_connector_not_found(self):
        err = ConnectorNotFound("django.db.backends.mysql")
        assert err.engine == "django.db.backends.mysql"
        assert "mysql" in str(err)
