# flake8: noqa
"""Sphinx configuration file for an LSST stack package.

This configuration only affects single-package Sphinx documentation builds.
For more information, see:
https://developer.lsst.io/stack/building-single-package-docs.html
"""

from documenteer.conf.pipelinespkg import *

project = "ts_nightreport"
html_theme_options["logotext"] = project  # type: ignore
html_title = project
html_short_title = project
