import json
import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm


@dataclass
class Credentials:
    email: str
    password: str


class BunproClient:
    def __init__(self, email: str, password: str) -> None:
        self.session = requests.Session()
        self.credentials = Credentials(email=email, password=password)
        self.data_file = Path("deck_data.json")
        self.logged_in = False
        self.base_url = "https://bunpro.jp"
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    def ensure_login(self) -> None:
        if self.logged_in is False:
            success, error_msg = self.login()
            if success is False:
                raise ConnectionError(error_msg)

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

    def backup(self, deck_url: str) -> None:
        self.ensure_login()

        stats_url = self.base_url + deck_url

        stats_response = self.session.get(stats_url)
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

        # Save to disk
        with self.data_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def restore(self) -> None:
        self.ensure_login()

        token = self.session.cookies.get("frontend_api_token")

        with self.data_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

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


if __name__ == "__main__":
    """
    Example usage:

    - Create a .env file with:
        BUNPRO_EMAIL=your_email
        BUNPRO_PASSWORD=your_password

    - Run: python bunpro_client.py

    This will login, backup the deck located at '/decks/nn10ai/Bunpro-N5-Grammar'
    and save to deck_data.json in the current working directory.
    """

    import os

    load_dotenv()
    email = os.getenv("BUNPRO_EMAIL")
    password = os.getenv("BUNPRO_PASSWORD")

    if not (email and password):
        msg = "BUNPRO_EMAIL and BUNPRO_PASSWORD are required (set them in env or .env)."
        raise ValueError(msg)

    client = BunproClient(email=email, password=password)

    # Example: backup a deck
    demo_deck_path = "/decks/nn10ai/Bunpro-N5-Grammar"
    client.backup(demo_deck_path)
