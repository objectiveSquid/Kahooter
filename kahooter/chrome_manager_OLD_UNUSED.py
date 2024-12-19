from typing import TypedDict, Literal, Final, Any
import threading
import platform
import requests
import zipfile
import logging
import struct
import shutil
import json
import copy
import sys
import re
import os


class ProgressDict(TypedDict):
    download: list[int]
    extract: list[bool]


DEFAULT_PROGRESS_JSON: Final[ProgressDict] = {
    "download": [0, 0, 0],
    "extract": [False, False, False],
}


def check_progress_dict(progress_dict: dict[Any, Any]) -> bool:
    try:
        if (
            not isinstance(progress_dict["download"], list)
            or len(progress_dict["download"]) != 3
            or not all(
                isinstance(item, int) and item in [0, 1, 2]
                for item in progress_dict["download"]
            )
        ):
            raise TypeError()
        if (
            not isinstance(progress_dict["extract"], list)
            or not all([isinstance(item, bool) for item in progress_dict["extract"]])
            or len(progress_dict["extract"]) != 3
        ):
            raise TypeError()
    except (TypeError, KeyError):
        return False

    return True


def load_progress(path: str) -> ProgressDict:
    if not os.path.isfile(path):
        return copy.copy(DEFAULT_PROGRESS_JSON)

    with open(path, "r") as progress_fd:
        progress = json.load(progress_fd)

    if not check_progress_dict(progress):
        logging.warning("There was an error loading the progress file.")
        return copy.copy(DEFAULT_PROGRESS_JSON)

    return progress


def write_progress(path: str, progress: ProgressDict) -> None:
    with open(path, "w") as progress_fd:
        json.dump(progress, progress_fd, indent=4)


def create_portable_chrome_directory() -> tuple[str, bool]:
    if os.path.isdir(".portable_chrome"):
        return os.path.abspath(".portable_chrome"), False
    os.mkdir(".portable_chrome")
    return os.path.abspath(".portable_chrome"), True


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


def get_newest_version() -> str:
    return get_latest_download_links()[0]


def get_latest_download_links(
    target_version: str | None = None,
) -> tuple[str, str, str, str]:
    def find_download_link(platform_links: list[dict[str, str]]) -> str:
        for platform in platform_links:
            if platform["platform"] == get_platform():
                return platform["url"]
        raise Exception("Unable to find download link for current platform.")

    json_response = requests.get(
        "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
    ).json()

    if target_version:
        for version in json_response["versions"]:
            try:
                if version["version"] == target_version or re.match(
                    target_version.replace(".", "\\.")
                    .replace("*", "[0-9.]*")
                    .replace("?", "[0-9]*"),
                    version["version"],
                ):
                    return (
                        version["version"],
                        find_download_link(version["downloads"]["chrome"]),
                        find_download_link(version["downloads"]["chromedriver"]),
                        find_download_link(
                            version["downloads"]["chrome-headless-shell"]
                        ),
                    )
            except KeyError:
                raise Exception("Unable to find target version.")

    versions_index = 0
    while True:
        try:
            latest_version = sorted(
                json_response["versions"],
                key=lambda version: version["version"],
                reverse=True,
            )[versions_index]
        except IndexError:
            raise Exception("Unable to find latest version.")
        latest_downloads = latest_version["downloads"]

        try:
            return (
                latest_version["version"],
                find_download_link(latest_downloads["chrome"]),
                find_download_link(latest_downloads["chromedriver"]),
                find_download_link(latest_downloads["chrome-headless-shell"]),
            )
        except KeyError:
            versions_index += 1
            continue


def adapt_executable_name(name: str) -> str:
    if os.name == "nt":
        return name + ".exe"
    return name


def supports_partial_download(url: str) -> bool:
    response = requests.head(url)
    headers = response.headers
    accept_ranges = headers.get("Accept-Ranges", "none").lower()
    allow_header = headers.get("Allow", "").lower()

    return response.status_code == 200 and (
        accept_ranges == "bytes"
        or "range" in headers.get("Access-Control-Allow-Headers", "").lower()
        or "partial" in allow_header
    )


class FileDownloader(threading.Thread):
    def __init__(
        self,
        url: str,
        zip_name: str,
        target_path: str,
        index: int,
        progress: ProgressDict,
        zip_directory_name: str,
        zip_rename_directory_name: str,
        executable_path: str,
    ) -> None:
        super().__init__(name=f"Filedownloader thread - {zip_name}")

        self.url = url
        self.zip_name = zip_name
        self.target_path = target_path
        self.index = index
        self.progress = progress
        self.zip_directory_name = zip_directory_name
        self.zip_rename_directory_name = zip_rename_directory_name
        self.executable_path = executable_path

        self.progress_path = os.path.join(self.target_path, "progress.json")
        self.zip_filepath = os.path.join(self.target_path, self.zip_name)

    def run(self) -> None:
        self.__download_zip_file()
        self.__extract_zip_files()
        self.__delete_zip_file()
        self.__rename_directories()
        self.__make_executable()

    def __download_zip_file(self) -> None:
        if self.progress["download"][self.index] == 2:
            logging.debug(f"Skipping downloading zip file ({self.zip_name}).")
            return
        elif self.progress["download"][self.index] == 1:
            logging.debug(f"Continuing downloading zip file ({self.zip_name}).")
        else:
            logging.debug(f"Downloading zip file ({self.zip_name}).")

        # prepare headers
        headers = None
        if self.progress["download"][self.index] == 1:
            headers = {"Range": f"bytes={os.stat(self.zip_filepath).st_size}-"}
        elif supports_partial_download(
            self.url
        ):  # if it supports partial downloads now it probably will in the future :3
            self.progress["download"][self.index] = 1
            write_progress(self.progress_path, self.progress)

        response = requests.get(self.url, headers=headers, stream=True)
        response.raw.decode_content = True
        response.raise_for_status()

        # stream file
        if self.progress["download"][self.index] == 0:
            mode = "wb"  # truncate file if partial downloads are not supported
        else:
            mode = "ab"
        with open(self.zip_filepath, mode) as zip_fd:
            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):  # download 1 mb at a time
                if chunk:
                    zip_fd.write(chunk)

            self.progress["download"][self.index] = 2
            write_progress(self.progress_path, self.progress)

    def __extract_zip_files(self) -> None:
        logging.debug(f"Extracting zip file {self.zip_name}.")

        if self.progress["extract"][self.index]:
            return

        with zipfile.ZipFile(self.zip_filepath, "r") as zip_ref:
            zip_infolist = zip_ref.infolist()

            for file_index, file in enumerate(zip_ref.namelist()):
                if os.path.exists(file):
                    if (
                        os.stat(os.path.join(self.target_path, file)).st_size
                        == zip_infolist[file_index].file_size
                    ):
                        continue
                    os.remove(os.path.join(self.target_path, file))
                zip_ref.extract(file, self.target_path)

            self.progress["extract"][self.index] = True
            write_progress(self.progress_path, self.progress)

    def __rename_directories(self) -> None:
        logging.debug(f"Renaming directory {self.zip_directory_name}.")

        try:
            os.rename(
                os.path.join(
                    self.target_path, f"{self.zip_directory_name}-{get_platform()}"
                ),
                os.path.join(self.target_path, self.zip_rename_directory_name),
            )
        except FileNotFoundError:
            pass

    def __make_executable(self) -> None:
        logging.debug(f"Making {self.executable_path} executable.")

        if os.name != "posix":
            return

        os.chmod(self.executable_path, os.stat(self.executable_path).st_mode | 0o111)

    def __delete_zip_file(self) -> None:
        logging.debug(f"Deleting zip file {self.zip_name}.")

        try:
            os.remove(self.zip_filepath)
        except FileNotFoundError:
            pass


class DownloadFiles:
    def __init__(
        self, desired_chrome_version: str | None = None, re_download: bool = False
    ) -> None:
        self.re_download = re_download

        self.platform = get_platform()
        self.portable_chrome_path, self.created_directory = (
            create_portable_chrome_directory()
        )
        (
            self.version,
            self.chrome_download_link,
            self.chromedriver_download_link,
            self.chrome_headless_download_link,
        ) = get_latest_download_links(desired_chrome_version)

        self.target_path = os.path.join(self.portable_chrome_path, self.version)
        self.chrome_path = os.path.join(
            self.target_path, "chrome", adapt_executable_name("chrome")
        )
        self.chromedriver_path = os.path.join(
            self.target_path, "chromedriver", adapt_executable_name("chromedriver")
        )
        self.chrome_headless_path = os.path.join(
            self.target_path,
            "chrome-headless",
            adapt_executable_name("chrome-headless-shell"),
        )
        self.progress_path = os.path.join(self.target_path, "progress.json")

        self.progress = load_progress(self.progress_path)

    def download_all(self) -> tuple[str, str, str, str, str]:
        return (
            self.version,
            self.target_path,
            self.chrome_path,
            self.chromedriver_path,
            self.chrome_headless_path,
        )

        if self.re_download:
            should_update = "fully"
        else:
            should_update = self.__should_update()

        if should_update == "fully":
            self.__prepare_directory(clear=True)
        elif should_update == "none":
            return (
                self.version,
                self.target_path,
                self.chrome_path,
                self.chromedriver_path,
                self.chrome_headless_path,
            )

        chrome_downloader = FileDownloader(
            self.chrome_download_link,
            "chrome.zip",
            self.target_path,
            0,
            self.progress,
            "chrome",
            "chrome",
            self.chrome_path,
        )
        chromedriver_downloader = FileDownloader(
            self.chromedriver_download_link,
            "chromedriver.zip",
            self.target_path,
            1,
            self.progress,
            "chromedriver",
            "chromedriver",
            self.chromedriver_path,
        )
        chrome_headless_downloader = FileDownloader(
            self.chrome_headless_download_link,
            "chrome-headless.zip",
            self.target_path,
            2,
            self.progress,
            "chrome-headless-shell",
            "chrome-headless",
            self.chrome_headless_path,
        )

        logging.debug("Starting download threads.")

        chrome_downloader.start()
        chromedriver_downloader.start()
        chrome_headless_downloader.start()

        chrome_downloader.join()
        chromedriver_downloader.join()
        chrome_headless_downloader.join()

        logging.debug("Download threads finished.")

        return (
            self.version,
            self.target_path,
            self.chrome_path,
            self.chromedriver_path,
            self.chrome_headless_path,
        )

    def __prepare_directory(self, *, clear: bool = False) -> None:
        if clear:
            shutil.rmtree(self.portable_chrome_path, ignore_errors=True)

        os.makedirs(self.target_path, exist_ok=True)

    def __should_update(self) -> Literal["fully", "partially", "none"]:
        if self.created_directory:
            return "fully"

        downloaded_versions = os.listdir(self.portable_chrome_path)

        if len(downloaded_versions) == 0:
            return "fully"

        if self.version in downloaded_versions:
            if os.path.isfile(self.progress_path):
                logging.info("Continuing to update to latest version.")
                return "partially"
            logging.info("Latest version already downloaded.")
            return "none"
        else:
            logging.info("Downloading latest version and deleting old versions.")
            return "fully"
