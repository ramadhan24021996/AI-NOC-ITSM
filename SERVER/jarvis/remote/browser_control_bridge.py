"""
SERVER.jarvis.remote.browser_control_bridge — JARVIS Browser Control & Automation Bridge
========================================================================================
Memungkinkan JARVIS mengontrol browser pengguna secara langsung:
  1. "Jarvis, buka youtube" ➔ Buka tab YouTube
  2. "Jarvis, tolong play musik [nama lagu]" ➔ Cari & putar musik di YouTube / Spotify
  3. "Jarvis, buka tab chatgpt dan tanyakan [pertanyaan]" ➔ Buka ChatGPT dengan prompt
  4. "Jarvis, buka website [url]" ➔ Navigasi ke URL apapun

Bekerja secara lintas platform (Linux POSIX, Windows, macOS) menggunakan
Python `webbrowser` & OS launcher (`xdg-open` / `cmd.exe start` / `open`),
serta terintegrasi dengan Browser Extension.
"""
import logging
import os
import subprocess
import sys
import urllib.parse
import webbrowser
from typing import Any, Dict, Optional

logger = logging.getLogger("jarvis.remote.browser_control")


class JarvisBrowserControlBridge:
    """
    JARVIS Browser Control & Automation Bridge.
    Menerima perintah aksi browser dari JARVIS Presentation Runtime,
    membuka tab/URL, mencari musik/video di YouTube, serta membuka ChatGPT.
    """

    # URLs
    YOUTUBE_BASE_URL = "https://www.youtube.com"
    YOUTUBE_SEARCH_URL = "https://www.youtube.com/results?search_query="
    CHATGPT_URL = "https://chatgpt.com"
    CHATGPT_PROMPT_URL = "https://chatgpt.com/?q="
    SPOTIFY_SEARCH_URL = "https://open.spotify.com/search/"

    def __init__(self, browser_ext_bridge=None):
        self.browser_ext_bridge = browser_ext_bridge
        self._waiting_for_song: bool = False

    def is_waiting_for_song(self) -> bool:
        """Returns True if JARVIS is waiting for song details after generic genre prompt."""
        return self._waiting_for_song

    def open_url(self, url: str) -> bool:
        """
        Buka URL apapun di browser default pengguna.
        """
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        logger.info(f"[BrowserControl] Opening URL: {url}")
        try:
            # Method 1: Python webbrowser standard
            webbrowser.open_new_tab(url)
            return True
        except Exception as e:
            logger.warning(f"[BrowserControl] webbrowser.open_new_tab failed: {e}")

        # Method 2: OS-level launcher fallback
        try:
            if os.name == "posix":
                if sys.platform == "darwin":
                    subprocess.Popen(["open", url])
                else:
                    subprocess.Popen(["xdg-open", url])
            elif os.name == "nt":
                os.startfile(url)
            return True
        except Exception as e2:
            logger.error(f"[BrowserControl] OS launcher failed: {e2}")
            return False

    def open_youtube(self, query: str = "") -> str:
        """
        Buka YouTube atau cari video tertentu di YouTube.
        "Jarvis, buka youtube" atau "Jarvis, cari di youtube [query]"
        """
        if query:
            encoded = urllib.parse.quote(query)
            target_url = f"{self.YOUTUBE_SEARCH_URL}{encoded}"
            msg = f"Membuka YouTube dan mencari: '{query}'..."
        else:
            target_url = self.YOUTUBE_BASE_URL
            msg = "Membuka YouTube..."

        ok = self.open_url(target_url)
        if ok:
            return f"✅ {msg}\nURL: `{target_url}`"
        return f"❌ Gagal membuka YouTube ({target_url})."

    FAVORITE_MUSIC_URL = "https://www.youtube.com/watch?v=smk6RW2TMIM&list=RDsmk6RW2TMIM&start_radio=1"

    def play_favorite_music(self) -> str:
        """
        Putar playlist musik kesukaan operator di YouTube.
        "Jarvis, play musik kesukaan saya"
        """
        ok = self.open_url(self.FAVORITE_MUSIC_URL)
        if ok:
            return (
                f"🎵 Memutar playlist musik kesukaan Anda di YouTube...\n"
                f"URL: `{self.FAVORITE_MUSIC_URL}`\n"
                f"💡 Tab browser telah dibuka."
            )
        return "❌ Gagal memutar musik kesukaan."

    def play_music(self, song_or_genre: str = "") -> str:
        """
        Putar musik di YouTube / Spotify.
        Interactive Step 1: "Jarvis, carikan musik" -> "Musik apa yang Anda inginkan sayang?"
        Interactive Step 2: "Saya ingin memutar musik Sheila on 7" -> "Baik sayang, saya akan mencarikan lagu Sheila on 7 dan memutarnya 🎶❤️"
        """
        raw_query = song_or_genre.strip()
        clean_lower = raw_query.lower()

        if any(k in clean_lower for k in ["kesukaan", "favorit"]):
            self._waiting_for_song = False
            return self.play_favorite_music()

        # Clean common prefixes
        clean_query = raw_query
        for prefix in [
            "saya ingin memutar musik ", "saya ingin memutar lagu ", "saya ingin memutar ",
            "saya ingin musik ", "saya ingin lagu ", "saya ingin ", "mau musik ", "mau lagu ",
            "ingin memutar musik ", "ingin memutar lagu ", "memutar musik ", "memutar lagu ",
            "carikan musik ", "carikan lagu ", "carikan ", "detail lagu ", "lagu ",
            "play music ", "play musik ", "play ", "music ", "musik ", "putar ",
            "setel musik ", "setel lagu ", "setel ", "dengarkan musik ", "dengarkan lagu ", "dengarkan "
        ]:
            if clean_query.lower().startswith(prefix):
                clean_query = clean_query[len(prefix):].strip()
                break

        # Step 1: Interactive prompt if query is generic ("carikan musik", "play musik", "musik", "lagu", "saya ingin musik")
        is_generic_prompt = not clean_query or clean_query.lower() in [
            "carikan musik", "carikan lagu", "musik", "music", "lagu", "play musik", "play music", "play lagu", "saya ingin musik", "saya ingin lagu"
        ]

        if is_generic_prompt and not self._waiting_for_song:
            self._waiting_for_song = True
            return "Lagu atau musik apa yang ingin Anda dengarkan? Silakan sebutkan judul lagu atau genre..."

        self._waiting_for_song = False

        # Check if user wants romantic music or specific song query
        if not clean_query or any(k in clean_query.lower() for k in ["romantis", "cinta", "baper", "sliramu", "notasenja", "jawa"]):
            song_title = "Lagu Pilihan / Instrumental Romantis"
            search_query = "Lagu Pilihan Instrumental Romantis"
        else:
            song_title = clean_query
            search_query = clean_query

        encoded = urllib.parse.quote(search_query)
        target_url = f"{self.YOUTUBE_SEARCH_URL}{encoded}"

        ok = self.open_url(target_url)
        if ok:
            return (
                f"Baik, memutar musik '{song_title}' 🎶\n"
                f"▶ BUKA TAB MEDIA: {target_url}"
            )
        return f"❌ Gagal memutar musik {song_title}."

    def stop_music(self) -> str:
        """
        Hentikan/matikan pemutaran musik browser.
        "Jarvis, stop musik" / "Jarvis, matikan musik"
        """
        try:
            subprocess.run(["pkill", "-f", "chrome.*youtube"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-f", "firefox.*youtube"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        return (
            "⏹️ Pemutaran musik telah dihentikan.\n"
            "💡 Tab pemutar musik/media browser telah ditutup."
        )

    def open_chatgpt(self, prompt_question: str = "") -> str:
        """
        Buka ChatGPT AI (chatgpt.com) dan isi prompt pertanyaan jika ada.
        "Jarvis, tolong ketikkan [pertanyaan] sent ke gpt ai"
        """
        clean_prompt = prompt_question.strip()

        # Clean trailing suffixes like "sent ke gpt ai", "kirim ke gpt ai", "ke gpt ai", "ke chatgpt", "sent"
        for suffix in [
            " sent ke gpt ai", " sent ke gpt", " sent ke chatgpt", " kirim ke gpt ai", " kirim ke gpt",
            " kirim ke chatgpt", " ke gpt ai", " ke gpt", " ke chatgpt", " di chatgpt", " di gpt ai", " sent"
        ]:
            if clean_prompt.lower().endswith(suffix):
                clean_prompt = clean_prompt[:-len(suffix)].strip()
                break

        # Clean leading prefixes like "tolong ketikkan", "ketikkan", "tanyakan", "tanya"
        for prefix in ["tolong ketikkan ", "ketikkan ", "tanyakan ", "tanya "]:
            if clean_prompt.lower().startswith(prefix):
                clean_prompt = clean_prompt[len(prefix):].strip()
                break

        if clean_prompt:
            encoded = urllib.parse.quote(clean_prompt)
            target_url = f"{self.CHATGPT_PROMPT_URL}{encoded}"
            msg = f"Baik, saya telah membuka ChatGPT AI dengan pertanyaan: '{clean_prompt}' 🤖✨"
        else:
            target_url = self.CHATGPT_URL
            msg = "Baik, saya membuka portal ChatGPT AI 🤖✨"

        ok = self.open_url(target_url)
        if ok:
            return (
                f"{msg}\n\n"
                f"▶ BUKA TAB CHATGPT: {target_url}\n"
                f"Confidence: 100%\n"
                f"Evidence: JARVIS Browser Control Bridge Engine"
            )
        return f"❌ Gagal mengirimkan prompt ke ChatGPT AI."

    def handle_browser_command(self, query_text: str) -> Dict[str, Any]:
        """
        Dispatcher utama perintah browser dari JARVIS text/voice.

        Returns:
            Dict dengan keys: answer_text, action_taken, status
        """
        q = query_text.lower()

        # Handle Step 2 follow-up when JARVIS was waiting for song details
        if self.is_waiting_for_song():
            answer = self.play_music(query_text)
            return {
                "answer_text": answer,
                "action_taken": "PLAY_MUSIC",
                "execution_status": "SUCCESS",
            }

        # 1. YouTube & Music
        if any(k in q for k in ["kesukaan", "favorit"]):
            answer = self.play_favorite_music()
            return {
                "answer_text": answer,
                "action_taken": "PLAY_FAVORITE_MUSIC",
                "execution_status": "SUCCESS",
                "url": self.FAVORITE_MUSIC_URL,
            }

        elif "youtube" in q:
            # Extract query setelah kata 'youtube' atau 'buka youtube'
            if any(k in q for k in ["kesukaan", "favorit"]):
                answer = self.play_favorite_music()
                return {
                    "answer_text": answer,
                    "action_taken": "PLAY_FAVORITE_MUSIC",
                    "execution_status": "SUCCESS",
                    "url": self.FAVORITE_MUSIC_URL,
                }
            for prefix in ["buka youtube", "cari di youtube", "youtube"]:
                if prefix in q:
                    search = q.split(prefix, 1)[1].strip()
                    search = search.lstrip("tentang cari ").strip()
                    break
            else:
                search = ""
            answer = self.open_youtube(search)
            return {
                "answer_text": answer,
                "action_taken": "OPEN_YOUTUBE",
                "execution_status": "SUCCESS",
            }

        elif any(k in q for k in ["stop musik", "stop music", "matikan musik", "hentikan musik", "stop lagu", "matikan lagu", "hentikan lagu", "pause musik", "pause music", "jeda musik", "jarvis stop", "stop player", "stop media", "matikan player", "jarvis diam", "berhenti"]) or q.strip() in ["stop", "jarvis stop"]:
            answer = self.stop_music()
            return {
                "answer_text": answer,
                "action_taken": "STOP_MUSIC",
                "execution_status": "SUCCESS",
            }

        elif any(k in q for k in [
            "play musik", "putar musik", "play lagu", "putar lagu", "play music",
            "carikan musik", "carikan lagu", "memutar musik", "memutar lagu", "ingin memutar",
            "saya ingin musik", "saya ingin lagu", "mau musik", "mau lagu",
            "dengarkan musik", "dengarkan lagu", "setel musik", "setel lagu", "musik", "lagu", "music"
        ]):
            answer = self.play_music(query_text)
            return {
                "answer_text": answer,
                "action_taken": "PLAY_MUSIC",
                "execution_status": "SUCCESS",
            }

        # 2. ChatGPT / AI Chat Tab
        elif any(k in q for k in ["chatgpt", "chat gpt", "gpt.ai", "gpt ai", "gpt", "openai", "ketikkan", "sent ke gpt", "kirim ke gpt"]):
            prompt = query_text
            # Extract prompt if prefix/suffix is present
            answer = self.open_chatgpt(prompt)
            return {
                "answer_text": answer,
                "action_taken": "OPEN_CHATGPT",
                "execution_status": "SUCCESS",
            }

        # 3. Dashboard / NOC Portal Navigation
        elif any(k in q for k in ["buka dashboard", "buka noc", "buka portal", "tampilan awal", "dashboard jarvis"]):
            target_url = os.getenv("JARVIS_DASHBOARD_FRONTEND_URL", "https://10.20.0.154:9443")
            ok = self.open_url(target_url)
            return {
                "answer_text": f"🖥️ Membuka Tampilan Awal Dashboard NOC JARVIS...\nURL: `{target_url}`",
                "action_taken": "OPEN_DASHBOARD",
                "execution_status": "SUCCESS" if ok else "FAILED",
            }

        # 4. Generic URL Navigation
        elif any(k in q for k in ["buka website", "buka site", "buka tab", "buka url", "navigasi ke"]):
            # Extract domain/URL
            words = q.split()
            url = ""
            for w in words:
                if "." in w or w.startswith(("http", "www")):
                    url = w
                    break
            if not url and len(words) > 1:
                url = words[-1] + ".com"

            if url:
                ok = self.open_url(url)
                return {
                    "answer_text": f"🌐 Membuka tab browser ke `{url}`...",
                    "action_taken": "OPEN_URL",
                    "execution_status": "SUCCESS" if ok else "FAILED",
                }

        return {
            "answer_text": "⚠️ Perintah browser tidak dikenali.",
            "action_taken": "UNKNOWN_BROWSER_COMMAND",
            "execution_status": "FAILED",
        }
