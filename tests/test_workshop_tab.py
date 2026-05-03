import unittest

from PyQt6.QtCore import QUrl

from ui.tabs.workshop_tab import _is_allowed_top_level_url, _is_steam_client_url


class WorkshopTabTests(unittest.TestCase):
    def test_allows_steam_top_level_navigation(self):
        self.assertTrue(_is_allowed_top_level_url(QUrl("https://steamcommunity.com/app/108600/workshop/")))
        self.assertTrue(_is_allowed_top_level_url(QUrl("https://store.steampowered.com/login/")))
        self.assertTrue(_is_allowed_top_level_url(QUrl("https://help.steampowered.com/")))

    def test_blocks_external_top_level_navigation(self):
        self.assertFalse(_is_allowed_top_level_url(QUrl("https://example.com/")))
        self.assertFalse(_is_allowed_top_level_url(QUrl("steam://open/downloads")))

    def test_detects_steam_client_urls(self):
        self.assertTrue(_is_steam_client_url(QUrl("steam://open/downloads")))
        self.assertFalse(_is_steam_client_url(QUrl("https://steamcommunity.com/")))


if __name__ == "__main__":
    unittest.main()
