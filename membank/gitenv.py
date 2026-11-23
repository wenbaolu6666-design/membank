"""Environment for local git calls, stripping host-injected GIT_CONFIG_* entries."""
import os


def clean_env():
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_CONFIG_")}
