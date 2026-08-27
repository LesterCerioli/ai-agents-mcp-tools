# Single source of truth for the CLI's own version.
#
# Bump this whenever commands.py (or any module bundled into the PyInstaller
# binary) changes in a way that should be shipped to already-installed CLIs.
# The server reads this same file (it ships with every deploy) to answer
# GET /cli/version, so the binary built from a given commit and the API
# deployed from that same commit always agree on what "latest" means.
CLI_VERSION = "0.4.0"
