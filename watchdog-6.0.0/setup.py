import importlib.util
import sys
import os
import os.path
from platform import machine
from setuptools import setup, find_packages
from setuptools.extension import Extension
from setuptools.command.build_ext import build_ext

SRC_DIR = "src"
WATCHDOG_PKG_DIR = os.path.join(SRC_DIR, "watchdog")

# Load the module version
spec = importlib.util.spec_from_file_location(
    "version", os.path.join(WATCHDOG_PKG_DIR, "version.py")
)
version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version)

# Ignored Apple devices on which compiling watchdog_fsevents.c would fail.
# The FORCE_MACOS_MACHINE envar, when set to 1, will force the compilation.
_apple_devices = ("appletv", "iphone", "ipod", "ipad", "watch")
ext_modules = []

extras_require = {
    "watchmedo": ["PyYAML>=3.10"],
}

with open("README.rst", encoding="utf-8") as f:
    readme = f.read()

with open("changelog.rst", encoding="utf-8") as f:
    changelog = f.read()

setup(
    name="watchdog",
    version=version.VERSION_STRING,
    description="Filesystem events monitoring",
    long_description=readme + "\n\n" + changelog,
    long_description_content_type="text/x-rst",
    author="Mickaël Schoentgen",
    author_email="contact@tiger-222.fr",
    license="Apache-2.0",
    url="https://github.com/gorakhargosh/watchdog",
    keywords=" ".join(
        [
            "python",
            "filesystem",
            "monitoring",
            "monitor",
            "FSEvents",
            "kqueue",
            "inotify",
            "ReadDirectoryChangesW",
            "polling",
            "DirectorySnapshot",
        ]
    ),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX :: BSD",
        "Operating System :: Microsoft :: Windows :: Windows Vista",
        "Operating System :: Microsoft :: Windows :: Windows 7",
        "Operating System :: Microsoft :: Windows :: Windows 8",
        "Operating System :: Microsoft :: Windows :: Windows 8.1",
        "Operating System :: Microsoft :: Windows :: Windows 10",
        "Operating System :: Microsoft :: Windows :: Windows 11",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Programming Language :: C",
        "Topic :: Software Development :: Libraries",
        "Topic :: System :: Monitoring",
        "Topic :: System :: Filesystems",
        "Topic :: Utilities",
    ],
    package_dir={"": SRC_DIR},
    packages=find_packages(SRC_DIR),
    include_package_data=True,
    extras_require=extras_require,
    cmdclass={
        "build_ext": build_ext,
    },
    ext_modules=ext_modules,
    entry_points={
        "console_scripts": [
            "watchmedo = watchdog.watchmedo:main [watchmedo]",
        ]
    },
    python_requires=">=3.9",
    zip_safe=False,
)
