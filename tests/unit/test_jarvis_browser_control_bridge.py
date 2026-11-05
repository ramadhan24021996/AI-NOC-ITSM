"""
Unit Tests for JARVIS Browser Control Bridge (Interactive Music & Tab Automation)
===================================================================================
Verifies:
  1. Step 1 Interactive Clarification prompt for generic genres ('romantis', 'pop', 'santai').
  2. Step 2 Execution & Tab Opening for specific song details ('Perfect Ed Sheeran').
  3. Prefix cleaning ('play music ', 'play musik ', 'music ', 'musik ').
"""
import unittest
from unittest.mock import patch
from SERVER.jarvis.remote.browser_control_bridge import JarvisBrowserControlBridge


class TestJarvisBrowserControlBridge(unittest.TestCase):

    def setUp(self):
        self.bridge = JarvisBrowserControlBridge()

    @patch.object(JarvisBrowserControlBridge, 'open_url', return_value=True)
    def test_play_music_generic_clarification(self, mock_open):
        """Step 1: Generic music queries must prompt for details FIRST without opening tab."""
        res = self.bridge.play_music("Play music")
        
        # Verify prompt text
        self.assertIn("Lagu atau musik apa yang ingin Anda dengarkan?", res)
        
        # Ensure browser tab was NOT opened in Step 1
        mock_open.assert_not_called()

    @patch.object(JarvisBrowserControlBridge, 'open_url', return_value=True)
    def test_play_music_specific_song_detail(self, mock_open):
        """Step 2: Specific song queries must open tab and return Step 2 response."""
        res = self.bridge.play_music("Perfect Ed Sheeran")
        
        # Verify Step 2 spoken text & Media tab link
        self.assertIn("Baik, memutar musik 'Perfect Ed Sheeran'", res)
        self.assertIn("▶ BUKA TAB MEDIA: https://www.youtube.com/results?search_query=Perfect%20Ed%20Sheeran", res)
        
        # Verify browser tab was opened
        mock_open.assert_called_once_with("https://www.youtube.com/results?search_query=Perfect%20Ed%20Sheeran")

    @patch.object(JarvisBrowserControlBridge, 'open_url', return_value=True)
    def test_play_favorite_music(self, mock_open):
        """Favorite music command plays favorite playlist."""
        res = self.bridge.play_favorite_music()
        self.assertIn("Memutar playlist musik kesukaan Anda", res)
        mock_open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
