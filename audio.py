import pygame
import math
import array

class AudioManager:
    def __init__(self):
        self.enabled = False
        self.music_enabled = True
        self.sfx_enabled = True
        self.master_volume = 0.7
        self.music_volume = 0.5
        self.sfx_volume = 0.8
        self.sounds = {}
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.enabled = True
        except Exception as e:
            print(f"[Audio] Mixer init failed: {e} -> placeholder sessiz mod")
            self.enabled = False

    def _make_tone(self, freq, duration_ms, vol=0.3, waveform="sine"):
        if not self.enabled:
            return None
        try:
            sample_rate = 44100
            n_samples = int(sample_rate * duration_ms / 1000)
            buf = array.array('h')
            for i in range(n_samples):
                t = i / sample_rate
                if waveform == "sine":
                    v = math.sin(2 * math.pi * freq * t)
                elif waveform == "square":
                    v = 1 if math.sin(2*math.pi*freq*t) > 0 else -1
                elif waveform == "saw":
                    v = 2 * (t*freq - math.floor(0.5 + t*freq))
                else:
                    v = math.sin(2*math.pi*freq*t)
                # fade in/out
                fade = 1.0
                if i < 200:
                    fade = i/200
                elif i > n_samples-400:
                    fade = (n_samples - i)/400
                v = int(v * vol * 32767 * fade)
                buf.append(v)
                buf.append(v)  # stereo
            # array('h') -> bytes via tobytes (daha güvenilir)
            try:
                raw = buf.tobytes()
            except:
                raw = bytes(buf)
            snd = pygame.mixer.Sound(buffer=raw)
            return snd
        except Exception as e:
            print(f"[Audio] tone fail {freq}: {e}")
            return None

    def _make_melody(self, notes, vol=0.28, waveform="sine", gap_ms=18):
        """notes = list of (freq, duration_ms) — İzmir Marşı gibi melodi üretir."""
        if not self.enabled:
            return None
        try:
            sample_rate = 44100
            buf = array.array('h')
            for freq, dur in notes:
                if freq == 0:  # sus
                    n = int(sample_rate * dur / 1000)
                    for _ in range(n):
                        buf.append(0); buf.append(0)
                    continue
                n_samples = int(sample_rate * dur / 1000)
                for i in range(n_samples):
                    t = i / sample_rate
                    if waveform == "sine":
                        v = math.sin(2 * math.pi * freq * t)
                    elif waveform == "square":
                        v = 1 if math.sin(2*math.pi*freq*t) > 0 else -1
                    else:
                        v = math.sin(2*math.pi*freq*t)
                    # melodi için yumuşak fade
                    fade = 1.0
                    if i < 80:
                        fade = i/80
                    elif i > n_samples-120:
                        fade = (n_samples - i)/120
                    # hafif vibrato marş hissi
                    vib = 1 + 0.015*math.sin(2*math.pi*5*t)
                    v = int(v * vib * vol * 32767 * fade)
                    buf.append(v); buf.append(v)
                # nota arası boşluk
                if gap_ms > 0:
                    gn = int(sample_rate * gap_ms / 1000)
                    for _ in range(gn):
                        buf.append(0); buf.append(0)
            try:
                raw = buf.tobytes()
            except:
                raw = bytes(buf)
            return pygame.mixer.Sound(buffer=raw)
        except Exception as e:
            print(f"[Audio] melody fail: {e}")
            return None

    def load_or_generate(self):
        if not self.enabled:
            return
        try:
            # coin — bright chime
            self.sounds["coin"] = self._make_tone(880, 120, 0.35)
            self.sounds["coin5"] = self._make_tone(1200, 160, 0.35)
            # movement
            self.sounds["jump"] = self._make_tone(440, 140, 0.30, "square")
            self.sounds["land"] = self._make_tone(180, 110, 0.22, "saw")
            self.sounds["roll"] = self._make_tone(190, 180, 0.24, "saw")
            # ui
            self.sounds["click"] = self._make_tone(600, 60, 0.20)
            self.sounds["hover"] = self._make_tone(900, 40, 0.12)
            self.sounds["purchase"] = self._make_tone(740, 220, 0.30)
            # game
            self.sounds["death"] = self._make_tone(150, 600, 0.35, "saw")
            self.sounds["levelup"] = self._make_tone(660, 200, 0.30)
            self.sounds["unlock"] = self._make_tone(740, 300, 0.30)
            # İzmir Marşı — marş melodisi (M tuşu ile çalar)
            # Nota frekansları (C4~261, D4~294, E4~330, F4~349, G4~392, A4~440, B4~494, C5~523)
            # "İzmir'in dağlarında çiçekler açar" ana motif yaklaşıklaması
            izmir_notes = [
                (392, 320),(392, 320),(440, 320),(494, 320),(523, 480),(494, 320),(440, 320), # İzmir'in dağlarında
                (392, 480),(330, 320),(392, 320),(440, 320),(494, 640),                         # çiçekler açar
                (523, 320),(523, 320),(523, 320),(494, 320),(440, 320),(392, 480),              # Altın güneş orda
                (440, 320),(392, 320),(330, 320),(294, 320),(330, 640),                         # sırmalar saçar
                (392, 320),(440, 320),(494, 320),(523, 320),(659, 480),(523, 320),(494, 320),   # Bozulmuş düşmanlar
                (440, 480),(392, 320),(440, 320),(494, 320),(440, 640),                         # yel gibi kaçar
                (0, 220),                                                                         # nefes
                (392, 320),(392, 320),(440, 320),(494, 320),(523, 480),(494, 320),(440, 320),
                (392, 480),(330, 320),(392, 320),(440, 320),(494, 640),
            ]
            # square + sine karışımı marş tınısı — güçlü
            self.sounds["izmir_marsi"] = self._make_melody(izmir_notes, vol=0.32, waveform="square", gap_ms=14)
            if self.sounds["izmir_marsi"] is None:
                self.sounds["izmir_marsi"] = self._make_tone(440, 400, 0.3, "square")
            # ensure all expected keys exist — missing -> silent no crash
            for k in ("coin","coin5","jump","land","roll","click","hover","death","levelup","unlock","purchase","izmir_marsi"):
                if self.sounds.get(k) is None:
                    self.sounds[k] = self._make_tone(440, 10, 0.01) if self.enabled else None
        except Exception as e:
            print(f"[Audio] generate error: {e}")

    def play(self, name, volume=1.0):
        if not self.enabled or not self.sfx_enabled:
            return
        # alias: purchase -> coin if not found
        key = name if name in self.sounds else ("coin" if "coin" in name else None)
        if key is None:
            key = name
        snd = self.sounds.get(key)
        if snd is None:
            # graceful fallback — no crash
            return
        try:
            snd.set_volume(self.master_volume * self.sfx_volume * volume)
            snd.play()
        except Exception:
            pass

    def play_izmir_marsi(self, loop=False):
        """İzmir Marşı'nı çal — loop True ise tekrarlı."""
        if not self.enabled:
            return
        snd = self.sounds.get("izmir_marsi")
        if snd is None:
            return
        try:
            # müzik volümü + master
            snd.set_volume(self.master_volume * self.music_volume * 0.95)
            snd.play(loops=-1 if loop else 0)
        except Exception:
            pass
    def stop_izmir_marsi(self):
        if not self.enabled:
            return
        snd = self.sounds.get("izmir_marsi")
        if snd:
            try: snd.stop()
            except: pass

    def pause_all(self):
        if not self.enabled:
            return
        try:
            pygame.mixer.pause()
        except: pass
    def unpause_all(self):
        if not self.enabled:
            return
        try:
            pygame.mixer.unpause()
        except: pass

    def set_master(self, v):
        self.master_volume = max(0, min(1, v))
    def set_music(self, v):
        self.music_volume = max(0, min(1, v))
    def set_sfx(self, v):
        self.sfx_volume = max(0, min(1, v))

audio = AudioManager()
