from typing import Literal
import cachetools
import subprocess
import platform
import requests
import zipfile
import os.path
import shutil
import struct
import sys
import os
import re


# adapted from https://pypi.org/project/knw-Chromedriver-manager
def get_chrome_version() -> str:
    version = None

    if os.name == "nt":  # windows
        cmd = (
            r'reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version'
        )
        output = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.STDOUT
        ).decode()
        version = re.search(r"(\d+\.\d+\.\d+\.\d+)", output).group(0)
    else:  # unix
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/opt/google/chrome/google-chrome",
        ]

        for path in paths:
            if not os.path.exists(path):
                continue

            process = subprocess.Popen(
                [path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            output, error = process.communicate()

            try:
                output = output.decode("utf-8")
            except UnicodeDecodeError:
                output = output.decode("cp437")

            try:
                version = re.search(r"(\d+\.\d+\.\d+\.\d+)", output).group(0)  # type: ignore
            except AttributeError:
                continue

            break

    if version == None:
        raise Exception("Chrome is not installed.")
    return version


def create_portable_chrome_directory() -> tuple[str, bool]:
    if os.path.isdir(".portable_chrome"):
        return os.path.abspath(".portable_chrome"), False
    os.mkdir(".portable_chrome")
    return os.path.abspath(".portable_chrome"), True


@cachetools.cached({})
def get_chromedriver_link(version: str) -> str:
    version_without_patch = ".".join(version.split(".")[:-1])

    try:
        downloads = requests.get(
            "https://googlechromelabs.github.io/chrome-for-testing/latest-patch-versions-per-build-with-downloads.json"
        ).json()["builds"][version_without_patch]["downloads"]["chromedriver"]
        for item in downloads:
            if item["platform"] == get_platform():
                return item["url"]
    except (requests.RequestException, KeyError):
        pass

    raise Exception("Unable to get chromedriver link.")


def get_platform() -> Literal["win32", "win64", "mac-arm64", "mac-x64", "linux64"]:
    bits = struct.calcsize("P") * 8
    is_arm = platform.machine()

    match sys.platform:
        case "win32":
            if bits == 32:
                return "win32"
            else:
                return "win64"
        case "darwin":
            if is_arm:
                return "mac-arm64"
            else:
                return "mac-x64"
        case "linux":
            return "linux64"
        case _:
            raise Exception("Unsupported platform.")


def get_chromedriver_size(version: str) -> int:
    chromedriver_link = get_chromedriver_link(version)

    return int(requests.head(chromedriver_link).headers["Content-Length"])


def adapt_executable_name(name: str) -> str:
    if os.name == "nt":
        return f"{name}.exe"
    return name


def get_executable_path(directory: str, version: str) -> str:
    return os.path.join(directory, adapt_executable_name(version))


def should_download(directory: str, version: str | None = None) -> bool:
    if version == None:
        version = get_chrome_version()

    return get_chromedriver_size(version) != os.path.getsize(
        get_executable_path(directory, version)
    )


def install(directory: str, re_download: bool) -> tuple[str, str]:
    version = get_chrome_version()
    chromedriver_link = get_chromedriver_link(version)
    if chromedriver_link == None:
        raise Exception("Unable to get chromedriver link.")

    zip_path = os.path.join(directory, f"{version}.zip")
    relative_zip_executable_path = os.path.join(
        f"chromedriver-{get_platform()}", adapt_executable_name("chromedriver")
    )
    after_unzip_executable_path = os.path.join(directory, relative_zip_executable_path)
    executable_path = os.path.join(directory, adapt_executable_name(version))

    if not should_download(directory, version) and not re_download:
        return version, executable_path

    os.makedirs(directory, exist_ok=True)
    with open(zip_path, "wb") as chromedriver_fd:
        for chunk in requests.get(chromedriver_link, stream=True).iter_content(
            1024 * 1024
        ):  # download in 1 mb chunks
            chromedriver_fd.write(chunk)

    with zipfile.ZipFile(zip_path, "r") as zip_reference:
        zip_reference.extract(relative_zip_executable_path, path=directory)
    os.remove(zip_path)

    shutil.move(after_unzip_executable_path, executable_path)
    os.rmdir(os.path.dirname(after_unzip_executable_path))
    if os.name == "posix":
        os.chmod(executable_path, os.stat(executable_path).st_mode | 0o111)

    return version, executable_path
