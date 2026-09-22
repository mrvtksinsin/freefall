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
        # FAZ4: bolum muzik altyapisi (procedural, cache'li, crossfade)
        self._music_cache = {}
        self._current_music_key = None
        self._current_music_sound = None
        self._music_fade = 0.0  # 0..1
        self._music_fade_target = 0.0
        self._music_fade_dur = 0.8
        self._music_fade_time = 0.0
        self._tension = 0.0  # 0..1 monster yaklasma
        self._tension_target = 0.0
        # FAZ14: threat / rock crossfade (ikinci katman)
        self._threat_sound = None
        self._threat_key = None
        self._threat_fade = 0.0
        self._threat_cache = {}
        # ana menu rock icin ayri key tutmayiz, normal music kullanir
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
        """notes = list of (freq, duration_ms) — generic melody builder (kept for extensibility)."""
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
        if self.sounds:
            # daha önce üretildi — tekrar üretme (çoklu Game() kurulumunda hız)
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
            # FAZ5: combo / bonus / near-miss (kisa, dusuk maliyet)
            self.sounds["combo"] = self._make_tone(960, 110, 0.26)
            self.sounds["bonus"] = self._make_tone(1100, 150, 0.28)
            self.sounds["near_miss"] = self._make_tone(520, 130, 0.24, "saw")
            # FAZ6: combat - punch / sword
            self.sounds["punch"] = self._make_tone(180, 90, 0.32, "saw")
            self.sounds["sword_swing"] = self._make_tone(620, 140, 0.28, "sine")
            self.sounds["sword_hit"] = self._make_tone(880, 110, 0.30, "square")
            self.sounds["weapon_equip"] = self._make_tone(740, 180, 0.28)
            # ensure all expected keys exist — missing -> silent no crash
            for k in ("coin","coin5","jump","land","roll","click","hover","death","levelup","unlock","purchase","combo","bonus","near_miss","punch","sword_swing","sword_hit","weapon_equip"):
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

    # (FAZ14) legacy march kaldirildi — M artik genel MUSIC toggle

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
        try:
            self._apply_music_volume()
        except: pass
    def set_music(self, v):
        self.music_volume = max(0, min(1, v))
        # anlik muzik volumunu guncelle (normal + threat)
        try:
            self._apply_music_volume()
        except: pass
    def set_sfx(self, v):
        self.sfx_volume = max(0, min(1, v))

    # ---------- FAZ4: Bolum Muzik Altyapisi ----------
    # FAZ14: ana rock + dark/rock profiller — telifsiz procedural, karanlık/metallic
    _MUSIC_PROFILES = {
        "ambient_air": {"freq": 220, "wave": "sine",  "dur": 2200, "vol": 0.16},
        "earthy":      {"freq": 132, "wave": "saw",   "dur": 2400, "vol": 0.18},
        "dark_rock":   {"freq":  92, "wave": "saw",   "dur": 2600, "vol": 0.19},
        "magma":       {"freq":  78, "wave": "saw",   "dur": 2100, "vol": 0.22},
        "ice":         {"freq": 318, "wave": "sine",  "dur": 2300, "vol": 0.15},
        "deep":        {"freq":  62, "wave": "sine",  "dur": 2800, "vol": 0.18},
        "strata":      {"freq": 108, "wave": "saw",   "dur": 2500, "vol": 0.17},
        "sewer":       {"freq":  98, "wave": "saw",   "dur": 2400, "vol": 0.16},
        "cafe":        {"freq": 182, "wave": "sine",  "dur": 2200, "vol": 0.14},
        "office":      {"freq": 242, "wave": "sine",  "dur": 2000, "vol": 0.13},
        "backrooms":   {"freq": 198, "wave": "sine",  "dur": 2300, "vol": 0.14},
        "power":       {"freq": 148, "wave": "square","dur": 1900, "vol": 0.17},
        "museum":      {"freq": 172, "wave": "sine",  "dur": 2400, "vol": 0.13},
        "classroom":   {"freq": 192, "wave": "sine",  "dur": 2100, "vol": 0.14},
        "factory":     {"freq":  82, "wave": "saw",   "dur": 2000, "vol": 0.18},
        "polygon":     {"freq": 212, "wave": "square","dur": 2100, "vol": 0.15},
        "forest":      {"freq": 138, "wave": "sine",  "dur": 2400, "vol": 0.15},
        "palace":      {"freq": 262, "wave": "sine",  "dur": 2200, "vol": 0.14},
        "village":     {"freq": 162, "wave": "sine",  "dur": 2300, "vol": 0.14},
        "city":        {"freq": 118, "wave": "square","dur": 2100, "vol": 0.15},
        "tokyo":       {"freq": 282, "wave": "square","dur": 2000, "vol": 0.16},
        "france":      {"freq": 232, "wave": "sine",  "dur": 2200, "vol": 0.14},
        "final":       {"freq":  88, "wave": "saw",   "dur": 2600, "vol": 0.20},
        # FAZ14: ana menu ve threat icin dark rock
        "menu_rock":   {"freq":  86, "wave": "saw",   "dur": 2400, "vol": 0.18},
        "main_rock":   {"freq":  84, "wave": "saw",   "dur": 2500, "vol": 0.19},
        "threat_rock": {"freq":  58, "wave": "saw",   "dur": 1900, "vol": 0.23},
    }

    def _get_or_make_music(self, music_key):
        if not self.enabled:
            return None
        if music_key in self._music_cache and self._music_cache[music_key] is not None:
            return self._music_cache[music_key]
        prof = self._MUSIC_PROFILES.get(music_key, self._MUSIC_PROFILES["ambient_air"])
        # bazi ozel key'ler icin 2-tonlu loop (final daha zengin)
        if music_key == "final":
            # final: 88Hz + 176Hz iki katman yerine tek saw + harmonik his icin uzun dur
            snd = self._make_tone(prof["freq"], prof["dur"], prof["vol"], prof["wave"])
            # ikinci harmonik ekle (cache'li, basit mix yerine tek ton yeterli - performans)
        elif music_key == "tokyo":
            # tokyo neon: square, kisa ve keskin
            snd = self._make_tone(prof["freq"], prof["dur"], prof["vol"], prof["wave"])
        else:
            snd = self._make_tone(prof["freq"], prof["dur"], prof["vol"], prof["wave"])
        if snd is not None:
            self._music_cache[music_key] = snd
            # cache buyumesini sinirla (max 23)
            if len(self._music_cache) > 28:
                # en eskiyi at (yeni muzik eklendiginde)
                oldest = next(iter(self._music_cache))
                self._music_cache.pop(oldest, None)
        return snd

    def _apply_music_volume(self):
        # normal music — tension ile duck (crossfade'in bir yarisi)
        if self.enabled and self._current_music_sound:
            try:
                base = self.master_volume * self.music_volume
                # FAZ14: daha guclu duck (0.60) — threat ile crossfade
                vol = base * max(0, min(1, self._music_fade)) * (1.0 - self._tension * 0.60)
                if not self.music_enabled:
                    vol = 0.0
                self._current_music_sound.set_volume(max(0, min(1, vol)))
            except: pass
        # threat — tension ile yukselen
        self._apply_threat_volume()

    def _apply_threat_volume(self):
        if not self.enabled or not self._threat_sound:
            return
        try:
            base = self.master_volume * self.music_volume
            # threat 0..tension, master*music*0.85* tension
            vol = base * max(0, min(1, self._tension)) * 0.88
            # threat kendi fade'i yok — tension yeter
            if not self.music_enabled:
                vol = 0.0
            # cok dusuk volumde neredeyse sessiz ama loop devam
            self._threat_sound.set_volume(max(0, min(1, vol)))
        except: pass

    def _get_or_make_threat(self):
        if not self.enabled:
            return None
        key = "threat_rock"
        if key in self._threat_cache and self._threat_cache[key] is not None:
            return self._threat_cache[key]
        prof = self._MUSIC_PROFILES.get(key, {"freq":58,"wave":"saw","dur":1900,"vol":0.23})
        snd = self._make_tone(prof["freq"], prof["dur"], prof["vol"], prof["wave"])
        if snd is not None:
            # metal hissi icin hafif ikinci harmonik ekle (ikinci ton mix yerine tek ton yeterli — performans)
            self._threat_cache[key] = snd
            if len(self._threat_cache) > 8:
                oldest = next(iter(self._threat_cache))
                self._threat_cache.pop(oldest, None)
        return snd

    def _ensure_threat_playing(self):
        if not self.enabled or not self.music_enabled:
            return False
        if self._threat_sound is not None:
            # zaten caliyor mu? channel busy kontrolu yok, vol 0 bile caliyor sayilir
            return True
        snd = self._get_or_make_threat()
        if snd is None:
            return False
        self._threat_sound = snd
        self._threat_key = "threat_rock"
        try:
            snd.set_volume(0.0)
            snd.play(loops=-1)
            self._apply_threat_volume()
        except: pass
        return True

    def stop_threat(self, fade_out=0.6):
        # threat fade out — volum 0'a iner, sonra stop
        if not self.enabled or not self._threat_sound:
            self._tension_target = 0.0
            return
        # tension'i dusurerek crossfade ile sessizlesir; anlik stop istenirse
        if fade_out <= 0.05:
            try: self._threat_sound.stop()
            except: pass
            self._threat_sound = None
            self._threat_key = None
        # yoksa tension zaten 0'a gidecek — update'de vol 0 olur, bir sure sonra stop edilebilir

    def play_music_for_level(self, level_name, fade_in=0.8):
        """Bolum adindan music_key cikar, ayni key zaten caliyorsa restart etme (FAZ4 #7)."""
        if not self.enabled or not self.music_enabled:
            return False
        try:
            import config as _cfg
            mk = _cfg.get_music_key(level_name)
        except:
            mk = "ambient_air"
        if mk == self._current_music_key and self._current_music_sound:
            # zaten caliyor - gereksiz restart yok
            return False
        snd = self._get_or_make_music(mk)
        if snd is None:
            return False
        # onceki muzigi durdur (fade out yerine anlik stop + yeni fade in - basit ve ucuz)
        try:
            if self._current_music_sound:
                self._current_music_sound.stop()
        except: pass
        self._current_music_key = mk
        self._current_music_sound = snd
        self._music_fade = 0.0
        self._music_fade_target = 1.0
        self._music_fade_dur = max(0.15, float(fade_in))
        self._music_fade_time = 0.0
        try:
            snd.set_volume(0.0)
            snd.play(loops=-1)
            self._apply_music_volume()
        except: pass
        return True

    def play_music_key(self, music_key, fade_in=0.8):
        """Dogrudan music_key ile cal (level_name yokken)."""
        if not self.enabled or not self.music_enabled:
            return False
        if music_key == self._current_music_key and self._current_music_sound:
            return False
        snd = self._get_or_make_music(music_key)
        if snd is None:
            return False
        try:
            if self._current_music_sound:
                self._current_music_sound.stop()
        except: pass
        self._current_music_key = music_key
        self._current_music_sound = snd
        self._music_fade = 0.0
        self._music_fade_target = 1.0
        self._music_fade_dur = max(0.15, float(fade_in))
        self._music_fade_time = 0.0
        try:
            snd.set_volume(0.0)
            snd.play(loops=-1)
            self._apply_music_volume()
        except: pass
        return True

    def stop_music(self, fade_out=0.5):
        if not self.enabled or not self._current_music_sound:
            self._current_music_key = None
            return
        if fade_out <= 0.05:
            try: self._current_music_sound.stop()
            except: pass
            self._current_music_key = None
            self._current_music_sound = None
            self._music_fade = 0.0
            self._music_fade_target = 0.0
        else:
            self._music_fade_target = 0.0
            self._music_fade_dur = max(0.15, float(fade_out))
            self._music_fade_time = 0.0
            # stop gerceklesmesi update'de fade 0 olunca olacak

    def get_current_music_key(self):
        return self._current_music_key

    def set_tension(self, intensity):
        """Monster yaklasma 0..1 — FAZ14 crossfade: normal duck, threat yukselsin."""
        try:
            v = max(0.0, min(1.0, float(intensity)))
        except:
            v = 0.0
        self._tension_target = v
        # FAZ14: threat sesini gerektiginde baslat (lazy, ucuz)
        if v > 0.04 and self.enabled and self.music_enabled:
            self._ensure_threat_playing()

    def get_tension(self):
        return self._tension

    def update(self, dt):
        """Her frame cagirilir - fade ve tension interpolasyonu (ucuz, tek lerp)."""
        if not self.enabled:
            return
        # tension yumusak gecis (4.0 lerp -> ~0.6s %90)
        if abs(self._tension - self._tension_target) > 0.01:
            self._tension += (self._tension_target - self._tension) * min(1, dt*4.5)
        else:
            self._tension = self._tension_target
        # threat lazy start — tension yukseldi ama henuz threat yoksa baslat
        if self._tension > 0.03 and self._threat_sound is None and self.music_enabled:
            self._ensure_threat_playing()
        # threat volum guncelle (her frame, tension degisse de)
        self._apply_threat_volume()
        # muzik fade
        if self._current_music_sound and self._music_fade != self._music_fade_target:
            self._music_fade_time += dt
            t = min(1.0, self._music_fade_time / max(0.001, self._music_fade_dur))
            if self._music_fade_target > self._music_fade:
                self._music_fade = t * self._music_fade_target
            else:
                self._music_fade = (1 - t) * 1.0
                if t >= 1.0:
                    self._music_fade = 0.0
                    try: self._current_music_sound.stop()
                    except: pass
                    self._current_music_sound = None
                    self._current_music_key = None
                    # threat de sessizse durdur (kaynak korunumu)
                    if self._tension < 0.02 and self._threat_sound is not None:
                        try: self._threat_sound.stop()
                        except: pass
                        self._threat_sound = None
                        self._threat_key = None
            self._apply_music_volume()
        elif self._current_music_sound:
            # tension veya threat degistiyse volum guncelle
            self._apply_music_volume()
        # tension dusuk ve uzun suredir oyleyse threat'i durdur (ram)
        if self._threat_sound is not None and self._tension < 0.015 and self._tension_target < 0.015:
            # bir sure sonra durdurmak icin extra check — update her frame cagirildigindan hemen durdurma
            # ama crossfade icin 1.2s sessiz kalirsa durdur
            if not hasattr(self, '_threat_quiet_time'):
                self._threat_quiet_time = 0.0
            self._threat_quiet_time += dt
            if self._threat_quiet_time > 1.2:
                try: self._threat_sound.stop()
                except: pass
                self._threat_sound = None
                self._threat_key = None
                self._threat_quiet_time = 0.0
        else:
            if hasattr(self, '_threat_quiet_time'):
                self._threat_quiet_time = 0.0

audio = AudioManager()
