import io
import os
from configparser import ConfigParser
from newreleases import consts


class Config(object):
    """NewReleases configuration.

    Args:
        config (str): Path to the configuration `ini` file. If the file
            is not provided, default configuration file
            `~/.newreleases/newreleases.ini` will be used.
        profile (str): Selected profile from the `ini` file. Default:
            `default`.

    Attributes:
        config (str): Absolute path to the configuration `ini` file.
        profile (str): Selected profile.
        url (str): URL to the newreleases.io api.
        api_key (str): User auth token.
    """

    def __init__(self, config=None, profile="default"):
        self.config = os.path.abspath(
            config or os.path.expanduser(consts.DEFAULT_CONFIG_PATH)
        )
        self.profile = profile
        if not os.path.isfile(self.config):
            data = {}
        else:
            cp = ConfigParser()
            cp.read(self.config)
            data = cp[self.profile] if cp.has_section(self.profile) else {}

        self.url = consts.NEWRELEASES_API_URL
        self.api_key = data.get("api_key", None)

    @property
    def client(self):
        """Return a configured newreleases client.

        Returns:
            newreleases.client.Client: Configured newreleases client.
        """
        from newreleases.client import Client

        return Client(self)

    def configure(self, api_key):
        """Configure and save configuration to config file.

        Args:
            api_key (str): API key.
        """
        self.api_key = api_key
        self.save()

    def save(self):
        # Create config dir if it doesn't exist
        config_dir = os.path.dirname(self.config)
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        cp = ConfigParser()
        # Read existing configuration if exists
        if os.path.isfile(self.config):
            cp.read(self.config)

        # Create profile if it doesn't exist
        if self.profile not in cp.sections():
            cp.add_section(self.profile)

        # Write the current configuration to the profile
        cp[self.profile]["api_key"] = self.api_key

        # Save configuration
        with io.open(self.config, "w") as f:
            cp.write(f)

    def __str__(self):
        return f"Config({self.config})"

    __repr__ = __str__
