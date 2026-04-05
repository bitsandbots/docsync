"""DocSync package setup."""

from setuptools import find_packages, setup

setup(
    name="docsync",
    version="0.1.0",
    description="Project documentation wiki and file backup tool",
    author="CoreConduit",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "click>=8.0",
        "pyyaml>=6.0",
        "jinja2>=3.0",
        "markdown-it-py>=3.0",
        "zstandard>=0.21",
    ],
    entry_points={
        "console_scripts": [
            "docsync=docsync.cli:main",
        ],
    },
)
