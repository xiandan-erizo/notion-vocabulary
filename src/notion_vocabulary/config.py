"""Configuration helpers for the Notion Vocabulary project."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuration values required for connecting to MySQL.

    Attributes
    ----------
    host:
        Hostname where the MySQL server is running.
    port:
        Port on which the server is listening.
    user:
        Username used for authenticating with the database.
    password:
        Password used for authenticating with the database.
    database:
        Name of the schema that stores the vocabulary tables.
    use_ssl:
        Flag that indicates whether SSL should be enabled for the
        connection. Defaults to ``False``.
    """

    host: str
    port: int
    user: str
    password: str
    database: str
    use_ssl: bool = False

    def as_connector_kwargs(self) -> dict[str, object]:
        """Return a dictionary that is compatible with mysql.connector.

        The ``mysql.connector.connect`` function expects a dictionary with
        specific keys. Centralising this logic prevents duplication across
        the code base and keeps the configuration object as the single
        source of truth for connection details.
        """

        kwargs: dict[str, object] = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
        }
        if self.use_ssl:
            kwargs["ssl_disabled"] = False
        return kwargs
