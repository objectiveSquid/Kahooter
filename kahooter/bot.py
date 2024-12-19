from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
)
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver import Chrome

from typing import Callable
import threading
import enum


class SendNameStatus(enum.Enum):
    success = 0
    already_exists = 1
    other_error = 2


class Bot(threading.Thread):
    def __init__(
        self,
        index: int,
        lobby_id: int,
        username: str,
        driver: Chrome,
        vote_function: Callable[[int], int],
        request_new_name_function: Callable[[], str],
    ) -> None:
        super().__init__(name=f"Bot-{index}")

        self.index = index
        self.lobby_id = lobby_id
        self.username = username
        self.driver = driver
        self.vote_function = vote_function
        self.request_new_name_function = request_new_name_function

        self.preparing = False
        self.voting = False

    def prepare(self) -> bool:
        self.preparing = True

        self.open_url()
        self.join_lobby()
        while True:
            match self.send_name():
                case SendNameStatus.already_exists:
                    self.username = self.request_new_name_function()
                case SendNameStatus.other_error:
                    self.preparing = False
                    return False
                case SendNameStatus.success:
                    break

        self.preparing = False
        return True

    def vote_loop(self) -> None:
        self.voting = True

        while not self.check_game_over() and self.voting:
            self.vote()
            self.wait_for_new_round()

        self.voting = False

    def run(self) -> None:
        self.vote_loop()

    def open_url(self) -> None:
        self.driver.get("https://kahoot.it")

    def join_lobby(self) -> None:
        self.waiter(5).until(
            EC.presence_of_element_located((By.ID, "game-input"))
        ).send_keys(str(self.lobby_id))
        self.driver.find_element(
            By.CSS_SELECTOR, 'button[data-functional-selector="join-game-pin"]'
        ).click()

    def send_name(self) -> SendNameStatus:
        self.waiter(3).until(
            EC.presence_of_element_located((By.ID, "nickname"))
        ).send_keys(self.username)
        try:
            self.driver.find_element(
                By.CSS_SELECTOR,
                'button[data-functional-selector="join-button-username"]',
            ).click()
        except ElementClickInterceptedException:
            return SendNameStatus.other_error

        try:
            self.waiter(2).until(EC.url_contains("instructions"))
        except TimeoutException:
            return SendNameStatus.already_exists
        return SendNameStatus.success

    def vote(self) -> None:
        while not self.check_game_over():
            try:
                answer_buttons = self.waiter(0.5).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "button[data-functional-selector^='answer-']")
                    )
                )
                break
            except TimeoutException:
                continue
        if self.check_game_over():
            return

        vote_index = self.vote_function(len(answer_buttons))
        for answer_button in answer_buttons:
            if (
                answer_button.get_attribute("data-functional-selector")
                == f"answer-{vote_index}"
            ):
                answer_button.click()
                break

    def wait_for_new_round(self) -> None:
        while not self.check_game_over() and "gameblock" not in self.driver.current_url:
            self.driver.implicitly_wait(0.5)

    def check_game_over(self) -> bool:
        return (
            "gameover" in self.driver.current_url
            or "ranking" in self.driver.current_url
        )

    def waiter(self, seconds: float) -> WebDriverWait:
        return WebDriverWait(self.driver, seconds)
