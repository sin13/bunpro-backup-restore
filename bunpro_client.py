from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


@dataclass
class Credentials:
    email: str
    password: str


class BunproClient:
    def __init__(self, email: str, password: str) -> None:
        self.session = requests.Session()
        self.credentials = Credentials(email=email, password=password)
        self.logged_in = False
        self.base_url = "https://bunpro.jp"
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        self.base_path = Path("data")
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.kanji_backup_file_path = self.base_path / "kanji_data.json"

    def ensure_login(self) -> None:
        if self.logged_in is False:
            self.logger.info("Logging in...")
            success, error_msg = self.login()
            if success is False:
                raise ConnectionError(error_msg)
            self.logger.info("Login Succeeded.")

    def login(self) -> tuple[bool, str]:
        login_page_url = "https://bunpro.jp/users/sign_in"

        try:
            response = self.session.get(login_page_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            authenticity_token = soup.find("input", {"name": "authenticity_token"})[
                "value"
            ]

            login_data = {
                "utf8": "✓",
                "authenticity_token": authenticity_token,
                "user[email]": self.credentials.email,
                "user[password]": self.credentials.password,
                "user[remember_me]": "1",
                "commit": "Log in",
            }

            login_response = self.session.post(login_page_url, data=login_data)

            error_soup = BeautifulSoup(login_response.text, "html.parser")

            errors_div = error_soup.find("div", {"class": "errors"})
            if errors_div:
                alert_div = errors_div.find("div", {"class": "alert"})
                if alert_div and "Invalid Email or password." in alert_div.text:
                    return (
                        False,
                        "Invalid email/password. Please check your Bunpro credentials.",
                    )

            if login_response.status_code != requests.codes.ok:
                return (
                    False,
                    f"Login failed with status code: {login_response.status_code}",
                )

        except requests.RequestException as e:
            return False, f"Connection error: {e!s}"
        except Exception as e:
            return False, f"Unexpected error during login: {e!s}"
        else:
            self.logged_in = True
            return True, ""

    def save_data_to_disk(self, data: dict | list, path: Path) -> None:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_data_from_disk(self, path: Path) -> dict | list:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def backup_grammar(self, deck_url: str) -> None:
        self.ensure_login()
        self.logger.info("Starting backup for %s", deck_url)

        stats_url = self.base_url + deck_url
        stats_response = self.session.get(stats_url)
        stats_response.raise_for_status()

        soup = BeautifulSoup(stats_response.text, "html.parser")
        sections = soup.find_all("div", class_="deck-info-card")

        data = []
        for section in tqdm(sections):
            a_tag = section.find("a", href=True)
            url = a_tag["href"] if a_tag else None

            srs_span = section.find("span", string=lambda s: s and "SRS" in s)
            srs_text = srs_span.get_text(strip=True) if srs_span else None

            soup = BeautifulSoup(
                self.session.get(self.base_url + url).text,
                "html.parser",
            )
            script_tag = soup.find(
                "script",
                id="__NEXT_DATA__",
                type="application/json",
            )
            script_data = json.loads(script_tag.string)
            reviewable_id = int(script_data["props"]["pageProps"]["reviewable"]["id"])

            query = parse_qs(urlparse(url).query)
            deck_id = int(query.get("deck_id", [None])[0])

            data.append(
                {
                    "url": url,
                    "srs": srs_text,
                    "reviewable_id": reviewable_id,
                    "deck_id": deck_id,
                },
            )

        deck_backup_file_path = (
            self.base_path / f"deck_{deck_url.split('/')[-1].lower()}"
        ).with_suffix(".json")
        self.save_data_to_disk(data, deck_backup_file_path)

    def backup_kanji(self) -> None:
        self.ensure_login()

        kanji_url = self.base_url + "/api/frontend/user/add_known_kanji"
        token = self.session.cookies.get("frontend_api_token")

        response = self.session.post(
            kanji_url,
            json={"kanjis": []},
            headers={"authorization": f"Token token={token}"},
        )
        response.raise_for_status()

        self.save_data_to_disk(response.json(), self.kanji_backup_file_path)

    def backup(self, deck_urls: list[str]) -> None:
        for deck_url in deck_urls:
            self.backup_grammar(deck_url)
        self.backup_kanji()

    def restore_grammar(self, file_path: Path) -> None:
        self.ensure_login()
        self.logger.info("Starting restore for %s", file_path.name)

        token = self.session.cookies.get("frontend_api_token")

        data = self.load_data_from_disk(file_path)

        for point in tqdm(data):
            if point["srs"]:
                response = self.session.patch(
                    self.base_url + "/api/frontend/reviews/add_to_reviews",
                    json={
                        "reviewable_id": point["reviewable_id"],
                        "reviewable_type": "GrammarPoint",
                        "deck_id": point["deck_id"],
                    },
                    headers={"authorization": f"Token token={token}"},
                )
                id_ = response.json()["data"]["id"]
                self.session.patch(
                    self.base_url
                    + f"/api/frontend/reviews/{id_}/update_via_action_type",
                    json={
                        "action_type": "set_streak",
                        "new_streak": int(point["srs"].split()[1]),
                    },
                    headers={"authorization": f"Token token={token}"},
                )

    def restore_kanji(self) -> None:
        self.ensure_login()
        token = self.session.cookies.get("frontend_api_token")

        kanji_url = self.base_url + "/api/frontend/user/add_known_kanji"
        data = self.load_data_from_disk(self.kanji_backup_file_path)

        response = self.session.post(
            kanji_url,
            json={"kanjis": list(data["known_kanji"].keys())},
            headers={"authorization": f"Token token={token}"},
        )
        response.raise_for_status()

    def restore(self) -> None:
        for path in self.base_path.glob("deck_*"):
            self.restore_grammar(path)
        self.restore_kanji()
