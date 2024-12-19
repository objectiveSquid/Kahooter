from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver import Chrome

import multiprocessing.pool
import logging
import random
import sys
import os

from chromedriver_manager import (
    should_download as should_download_chromedriver,
    get_executable_path as get_chromedriver_path,
    install as install_chromedriver,
)
from bot import Bot


class BotManager:
    def __init__(
        self,
        logger: logging.Logger,
        lobby_id: int,
        bot_count: int,
        headless: bool = False,
        do_not_optimize: bool = False,
        re_download: bool = False,
    ) -> None:
        self.logger = logger
        self.bot_count = bot_count
        self.lobby_id = lobby_id
        self.headless = headless
        self.do_not_optimize = do_not_optimize

        try:
            if should_download_chromedriver(".chromedriver") or re_download:
                self.logger.info("Downloading chromedriver.")
            self.chrome_version, self.chromedriver_path = install_chromedriver(
                ".chromedriver", re_download
            )
        except Exception as error:
            self.logger.critical(f"Failed to download chromedriver: {error}")
            return

        self.generated_usernames: list[str] = []
        self.bots: list[Bot] = []

    def run(self) -> None:
        self.logger.info(f"Creating {self.bot_count} bots.")
        with multiprocessing.pool.ThreadPool(self.bot_count) as pool:
            self.bots = pool.map(self.__create_bot, range(self.bot_count))
        self.bots.sort(key=lambda bot: bot.index)

        self.logger.info("Joining lobby with all bots.")
        with multiprocessing.pool.ThreadPool(len(self.bots)) as pool:
            prepare_results = pool.map(lambda bot: bot.prepare(), self.bots)
            if not any(prepare_results):
                self.logger.critical("All bots failed to join the lobby, exiting.")
                self.cleanup()
                return
            if not all(prepare_results):
                self.logger.error(
                    f"Not all bots were able to join the lobby, continuing with {prepare_results.count(True)}/{len(prepare_results)} bots."
                )

        self.logger.info("Now voting.")
        for bot in self.bots:
            bot.start()
            self.logger.debug(f"Bot {bot.name} ({bot.username}) started voting.")

        try:
            for bot in self.bots:
                bot.join()
                self.logger.debug(f"Bot {bot.name} ({bot.username}) finished voting.")
        except KeyboardInterrupt:
            self.logger.info("Stopping bots.")
        else:
            self.logger.info("Game finished, stopping bots.")

        self.cleanup()

    def cleanup(self) -> None:
        for bot in self.bots:
            self.logger.debug(f"Stopping {bot.name} ({bot.username}).")
            bot.driver.quit()

    def __generate_unused_username(self) -> str:
        while (
            username := "user" + str(random.randint(0, 9999)).rjust(4, "0")
        ) in self.generated_usernames:
            pass

        self.generated_usernames.append(username)
        return username

    def __create_driver(self) -> Chrome:
        self.logger.debug("Creating driver.")

        options = ChromeOptions()
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--no-first-run")
        options.add_argument("--log-level=3")
        options.add_argument("--silent")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-translate")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-features=BackgroundSync")
        options.add_argument("--dns-prefetch-disable")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-breakpad")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-default-apps")
        options.add_argument(
            "--disable-features=Translate,BackForwardCache,InterestCohortAPI,BackgroundSync"
        )
        options.add_argument("--disable-ipc-flooding-protection")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--enable-low-end-device-mode")
        options.add_argument("--disk-cache-size=0")
        options.add_argument("--media-cache-size=0")
        options.add_argument("--no-zygote")
        options.add_argument("--blink-settings=imagesEnabled=false")
        options.add_argument("--disable-web-resources")

        if sys.platform == "linux":
            if os.environ.get("XDG_SESSION_TYPE") == "wayland":
                options.add_argument("--ozone-platform=wayland")
            if os.environ.get("XDG_SESSION_TYPE") == "x11":
                options.add_argument("--ozone-platform=x11")

        if self.do_not_optimize:
            options = ChromeOptions()  # reset options

        if self.headless:
            options.add_argument("--headless=new")

        service = ChromeService(
            get_chromedriver_path(".chromedriver", self.chrome_version)
        )
        driver = Chrome(options=options, service=service)

        if self.headless:
            try:
                driver.execute_cdp_cmd(
                    "Network.setBlockedURLs",
                    {
                        "urls": [
                            "*.png",
                            "*.jpg",
                            "*.jpeg",
                            "*.webp",
                            "*.gif",
                            "*.bmp",
                            "*.tiff",
                            "*.svg",
                            "*.ico",
                            "*.woff",
                            "*.woff2",
                            "*.ttf",
                            "*.otf",
                            "*.mp3",
                            "*.mp4",
                            "*.css",
                        ]
                    },
                )
                driver.execute_cdp_cmd("Network.enable", {})
            except Exception as error:
                self.logger.warning(
                    f"Could not set blocked URLs on driver: {error}. Continuing with default settings."
                )

        return driver

    def __create_bot(self, index: int) -> Bot:
        self.logger.debug(f"Creating bot {index}.")
        return Bot(
            index,
            self.lobby_id,
            self.__generate_unused_username(),
            self.__create_driver(),
            lambda answers_count: random.randint(0, answers_count - 1),
            self.__generate_unused_username,
        )
