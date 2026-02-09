from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from django_rclone.db.mongodb import MongoDumpConnector


class TestMongoDumpConnector:
    def test_extension(self):
        connector = MongoDumpConnector({"NAME": "mydb"})
        assert connector.extension == "archive"

    def test_host_port_defaults(self):
        connector = MongoDumpConnector({"NAME": "mydb", "HOST": "", "PORT": ""})
        assert connector._host_port() == "localhost:27017"

    def test_host_port_custom(self):
        connector = MongoDumpConnector({"NAME": "mydb", "HOST": "mongo.example.com", "PORT": "27018"})
        assert connector._host_port() == "mongo.example.com:27018"

    def test_auth_args_with_credentials(self):
        connector = MongoDumpConnector(
            {
                "NAME": "mydb",
                "HOST": "",
                "PORT": "",
                "USER": "admin",
                "PASSWORD": "secret",
                "AUTH_SOURCE": "admin",
            }
        )
        assert connector._auth_args() == [
            "--username",
            "admin",
            "--password",
            "secret",
            "--authenticationDatabase",
            "admin",
        ]

    def test_auth_args_empty(self):
        connector = MongoDumpConnector({"NAME": "mydb", "HOST": "", "PORT": "", "USER": "", "PASSWORD": ""})
        assert connector._auth_args() == []

    @patch("django_rclone.db.mongodb.subprocess.Popen")
    def test_create_dump(self, mock_popen: MagicMock):
        settings = {
            "NAME": "mydb",
            "HOST": "mongo.example.com",
            "PORT": "27018",
            "USER": "",
            "PASSWORD": "",
        }
        connector = MongoDumpConnector(settings)

        connector.dump()

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "mongodump"
        assert "--db" in cmd
        assert "mydb" in cmd
        assert "--archive" in cmd
        assert "--host" in cmd
        assert "mongo.example.com:27018" in cmd
        assert mock_popen.call_args[1]["stdout"] == subprocess.PIPE

    @patch("django_rclone.db.mongodb.subprocess.Popen")
    def test_restore_dump(self, mock_popen: MagicMock):
        connector = MongoDumpConnector({"NAME": "mydb", "HOST": "", "PORT": "", "USER": "", "PASSWORD": ""})
        stdin_mock = MagicMock()

        connector.restore(stdin=stdin_mock)

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "mongorestore"
        assert "--drop" in cmd
        assert "--archive" in cmd
        assert mock_popen.call_args[1]["stdin"] is stdin_mock
