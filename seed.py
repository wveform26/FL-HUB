"""Create demo users, items and generated media for FL HUB."""
from __future__ import annotations

import io
import json
import wave
import zipfile
from array import array
from datetime import datetime, timedelta, timezone
from pathlib import Path

import art
import db
import security
import synth

DEMO_PASSWORD = "flhub1234"


def _iso(days_ago: float) -> str:
    moment = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return moment.replace(microsecond=0).isoformat()


def wav_bytes(buf: list[float]) -> bytes:
    synth.fade_edges(buf)
    synth.normalize(buf)
    data = array("h", (int(max(-1.0, min(1.0, value)) * 32767) for value in buf))
    stream = io.BytesIO()
    with wave.open(stream, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(synth.SR)
        handle.writeframes(data.tobytes())
    return stream.getvalue()


def _vlq(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


def midi_bytes(notes: list[tuple[float, float, int]], bpm: float, name: str) -> bytes:
    division = 480
    track = bytearray()
    track += b"\x00\xff\x51\x03" + int(60_000_000 / bpm).to_bytes(3, "big")
    encoded_name = name.encode("utf-8")
    track += b"\x00\xff\x03" + _vlq(len(encoded_name)) + encoded_name
    events: list[tuple[int, int, int, int]] = []
    for start, duration, note in notes:
        events.append((int(start * division), 0, note, 96))
        events.append((int((start + duration) * division), 1, note, 0))
    events.sort(key=lambda event: (event[0], event[1]))
    last_tick = 0
    for tick, kind, note, velocity in events:
        delta = max(0, tick - last_tick)
        last_tick = tick
        track += _vlq(delta) + bytes([0x80 if kind else 0x90, note, velocity])
    track += b"\x00\xff\x2f\x00"
    header = (
        b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big")
        + (1).to_bytes(2, "big") + division.to_bytes(2, "big")
    )
    return header + b"MTrk" + len(track).to_bytes(4, "big") + bytes(track)


def _readme(title: str, lines: list[str]) -> str:
    body = "\n".join(lines)
    return (
        f"{title}\n{'=' * len(title)}\n\n"
        "Демо-материал с FL HUB — сообщества продюсеров FL Studio.\n"
        "Файлы сгенерированы специально для демонстрации сайта.\n\n"
        f"{body}\n\n"
        "Лицензия: используйте свободно в своих проектах.\n"
        "Сайт: FL HUB (локальная демо-версия)\n"
    )


def _zip_pack(filename: str, entries: dict[str, bytes]) -> int:
    path = db.UPLOAD_DIR / filename
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return path.stat().st_size


def build_project_pack(slug: str, bpm: float, root: str, title: str) -> tuple[str, str, int]:
    stems = {
        "drums": synth.render_loop("drums", bpm, 4)[0],
        "bass": synth.render_loop("bass", bpm, 4, root)[0],
        "keys": synth.render_loop("keys", bpm, 4, root)[0],
        "melody": synth.render_loop("melody", bpm, 4, root)[0],
    }
    root_number = synth.note_number(root)
    chord_notes = [root_number, root_number + 3, root_number + 7]
    keys_midi: list[tuple[float, float, int]] = []
    bass_midi: list[tuple[float, float, int]] = []
    melody_midi: list[tuple[float, float, int]] = []
    for bar in range(4):
        for offset in chord_notes:
            keys_midi.append((bar * 4.0, 3.6, offset))
        bass_midi.append((bar * 4.0, 1.5, root_number - 12))
        bass_midi.append((bar * 4.0 + 2.5, 1.0, root_number - 12))
        for i, step in enumerate((0.0, 1.5, 2.5, 3.5)):
            melody_midi.append((bar * 4.0 + step, 0.4, root_number + 12 + (i * 3) % 12))
    entries = {
        "README.txt": _readme(title, [
            "Внутри:",
            "  stems/  — 4 аудио-лупа (WAV, 22.05 kHz)",
            "  midi/   — MIDI-паттерны для баса, клавиш и мелодии",
            "  project_notes.txt — структура и советы по сборке",
            "",
            f"BPM: {int(bpm)}",
            "Открой stems в FL Studio, перетащи MIDI на каналы и собери свой бит.",
        ]).encode("utf-8"),
        "project_notes.txt": (
            f"{title}\n\nТемп: {int(bpm)} BPM\nКорень: {root}\n\n"
            "1. Закинь stems в плейлист, выставь темп.\n"
            "2. MIDI-дорожки можно переназначить на любые плагины.\n"
            "3. Добавь свои 808, эффекты и автоматизацию.\n"
            "4. Не забудь про mono-совместимость баса.\n"
        ).encode("utf-8"),
    }
    for name, buffer in stems.items():
        entries[f"stems/{name}.wav"] = wav_bytes(buffer)
    entries["midi/keys.mid"] = midi_bytes(keys_midi, bpm, "Keys")
    entries["midi/bass.mid"] = midi_bytes(bass_midi, bpm, "Bass")
    entries["midi/melody.mid"] = midi_bytes(melody_midi, bpm, "Melody")
    filename = f"seed_{slug}.zip"
    size = _zip_pack(filename, entries)
    return filename, f"{title.replace(' ', '_')}.zip", size


def build_instrument_pack(slug: str, title: str, table: str, root: str,
                          note_count: int = 8) -> tuple[str, str, int]:
    entries = {
        "README.txt": _readme(title, [
            "Внутри:",
            f"  samples/ — {note_count} WAV-сэмплов (22.05 kHz, mono)",
            "  mapping.txt — карта нот",
            "",
            "Загрузи сэмплы в Sampler / DirectWave и играй.",
        ]).encode("utf-8"),
    }
    root_number = synth.note_number(root)
    mapping_lines = []
    scale = [0, 2, 3, 5, 7, 8, 10, 12, 14, 15, 17, 19]
    for index in range(note_count):
        semitone = scale[index % len(scale)]
        midi_note = root_number + semitone
        names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        note_name = f"{names[midi_note % 12]}{midi_note // 12 - 1}"
        duration = 2.4 if table in ("rhodes", "organ") else 1.6
        sound = synth.osc(table, synth.freq(note_name), duration, 0.55, attack=0.008,
                          decay=1.2 if table in ("rhodes", "organ") else 0.5,
                          sustain=0.15, release=0.4)
        entries[f"samples/{index + 1:02d}_{note_name.replace('#', 's')}.wav"] = wav_bytes(sound)
        mapping_lines.append(f"{index + 1:02d}.wav -> {note_name} (MIDI {midi_note})")
    entries["mapping.txt"] = "\n".join(mapping_lines).encode("utf-8")
    filename = f"seed_{slug}.zip"
    size = _zip_pack(filename, entries)
    return filename, f"{title.replace(' ', '_')}.zip", size


def build_plugin_pack(slug: str, title: str, kind: str) -> tuple[str, str, int]:
    presets = {
        "01_warm_vocal.json": {"drive": 0.32, "tone": 0.58, "mix": 0.45, "mode": "tape"},
        "02_glue_bus.json": {"drive": 0.18, "tone": 0.5, "mix": 0.3, "mode": "clean"},
        "03_lofi_drums.json": {"drive": 0.62, "tone": 0.35, "mix": 0.6, "mode": "tape"},
        "04_808_saturation.json": {"drive": 0.74, "tone": 0.42, "mix": 0.55, "mode": "fat"},
        "05_master_soft.json": {"drive": 0.12, "tone": 0.6, "mix": 0.25, "mode": "clean"},
        "06_wide_synth.json": {"drive": 0.28, "tone": 0.72, "mix": 0.5, "mode": "wide"},
    }
    entries = {
        "README.md": _readme(title, [
            "Демонстрационный плагин-пак.",
            "Внутри: manual.txt и папка presets с настройками.",
            "Это концепт для витрины FL HUB, а не рабочий VST-бинарник.",
        ]).encode("utf-8"),
        "manual.txt": (
            f"{title}\n\n"
            f"Тип: {kind}\n"
            "Параметры:\n"
            "  Drive — количество насыщения\n"
            "  Tone  — тембральный баланс\n"
            "  Mix   — параллельный микс\n"
            "  Mode  — clean / tape / fat / wide\n\n"
            "Рекомендации:\n"
            "  Вокал: 20–35% drive, mix 40%.\n"
            "  Барабаны: 40–60% drive, mix 30%.\n"
            "  Мастер: не более 10–15% drive.\n"
        ).encode("utf-8"),
        "LICENSE.txt": "Free for personal and commercial use. Demo build.\n".encode("utf-8"),
    }
    for name, payload in presets.items():
        entries[f"presets/{name}"] = json.dumps(payload, indent=2).encode("utf-8")
    filename = f"seed_{slug}.zip"
    size = _zip_pack(filename, entries)
    return filename, f"{title.replace(' ', '_')}.zip", size


def build_drumkit_pack(slug: str, title: str, bpm: float, root: str) -> tuple[str, str, int]:
    shots = synth.drum_one_shots()
    entries = {
        "README.txt": _readme(title, [
            "Внутри:",
            f"  one_shots/ — {len(shots)} WAV-сэмпла (22.05 kHz, mono)",
            "  loops/ — 2 готовых лупа",
            "",
            "Все сэмплы можно использовать без ограничений.",
        ]).encode("utf-8"),
    }
    for name, buffer in shots.items():
        entries[f"one_shots/{name}.wav"] = wav_bytes(buffer)
    entries["loops/break_4bars.wav"] = wav_bytes(synth.render_loop("drums", bpm, 4)[0])
    entries["loops/bass_4bars.wav"] = wav_bytes(synth.render_loop("bass", bpm, 4, root)[0])
    filename = f"seed_{slug}.zip"
    size = _zip_pack(filename, entries)
    return filename, f"{title.replace(' ', '_')}.zip", size


USERS = [
    {
        "username": "nightdrive", "email": "nightdrive@flhub.local",
        "bio": "Трэп, 808 и ночные сессии в FL Studio. Собираю биты с 2017 года, делюсь шаблонами и сэмплами.",
        "avatar_color": "#ff7a1a", "days": 240,
    },
    {
        "username": "lofi_mira", "email": "mira@flhub.local",
        "bio": "Lo-fi, тёплые клавиши и виниловый шум. Пишу музыку для уютных вечеров и долгих поездок.",
        "avatar_color": "#b794f6", "days": 198,
    },
    {
        "username": "subbass", "email": "subbass@flhub.local",
        "bio": "House, techno и drum & bass. Люблю глубокий низ и аккуратную стереопанораму.",
        "avatar_color": "#4fd1c5", "days": 172,
    },
    {
        "username": "glitchkid", "email": "glitchkid@flhub.local",
        "bio": "Экспериментальная электроника, фонк и текстуры. Собираю звуки из полевых записей.",
        "avatar_color": "#ff6b9d", "days": 140,
    },
    {
        "username": "plugin_lab", "email": "pluginlab@flhub.local",
        "bio": "Разработка плагинов и пресетов. Делаю инструменты, которые помогают быстрее доходить до идеи.",
        "avatar_color": "#ffd166", "days": 320,
    },
    {
        "username": "beatcartel", "email": "beatcartel@flhub.local",
        "bio": "Drill, trap и немного R&B. Всегда открыт к коллаборациям.",
        "avatar_color": "#7dd3fc", "days": 96,
    },
    {
        "username": "tapehead", "email": "tapehead@flhub.local",
        "bio": "Сэмплы с кассет и винила, брейки и пыльные барабаны. Копаюсь в архивах, чтобы вы копались в звуке.",
        "avatar_color": "#f59e0b", "days": 64,
    },
    {
        "username": "verba", "email": "verba@flhub.local",
        "bio": "Пишу тексты и вокал, иногда собираю биты. Ищу продюсеров для совместных треков.",
        "avatar_color": "#a3e635", "days": 38,
    },
]

ITEMS = [
    {
        "slug": "neon-rain", "author": "nightdrive", "category": "music", "title": "Neon Rain",
        "genre": "Trap", "bpm": 140, "key": "A minor", "featured": 1, "days": 9.2,
        "plays": 1240, "downloads": 187, "track": "neon_rain",
        "tags": ["trap", "808", "dark", "night"],
        "description": "Тёмный трэп-бит с ледяными пэдами, скользящими 808 и арпеджио, которое не отпускает до последнего такта. Все партии собраны в MIDI — можно разобрать по дорожкам и переделать под себя.",
        "likes": ["lofi_mira", "subbass", "glitchkid", "plugin_lab", "beatcartel", "tapehead", "verba"],
    },
    {
        "slug": "midnight", "author": "lofi_mira", "category": "music", "title": "Полночь",
        "genre": "Lo-Fi", "bpm": 82, "key": "D minor", "days": 7.4,
        "plays": 986, "downloads": 142, "track": "midnight",
        "tags": ["lofi", "rhodes", "chill", "vinyl"],
        "description": "Тёплый lo-fi инструментал для поздних сессий. Родес, виниловый шум, ленивый свинг и мягкий бас. Идеально под вокал или как фон для работы над собственным битом.",
        "likes": ["nightdrive", "subbass", "glitchkid", "tapehead", "verba"],
    },
    {
        "slug": "deep-signal", "author": "subbass", "category": "music", "title": "Deep Signal",
        "genre": "Tech House", "bpm": 124, "key": "F# minor", "days": 5.1,
        "plays": 733, "downloads": 96, "track": "deep_signal",
        "tags": ["house", "groove", "club", "bassline"],
        "description": "Грувовый tech house с четырёхдольным киком, offbeat-басом и короткими стабами. Сводил в FL Studio, готово к клубному сету — осталось добавить свой вокал или эффекты.",
        "likes": ["nightdrive", "lofi_mira", "plugin_lab", "beatcartel"],
    },
    {
        "slug": "fracture", "author": "subbass", "category": "music", "title": "Fracture",
        "genre": "Drum & Bass", "bpm": 174, "key": "G minor", "days": 12.6,
        "plays": 1512, "downloads": 214, "track": "fracture",
        "tags": ["dnb", "reese", "dark", "breaks"],
        "description": "Атмосферный drum & bass на 174 BPM: риз-бас, ломаный бит и широкие пэды. Для любителей тёмной стороны драм-н-бейса. Внутри — готовый WAV, можно смело резать и семплить.",
        "likes": ["nightdrive", "glitchkid", "plugin_lab", "beatcartel", "tapehead"],
    },
    {
        "slug": "concrete-morning", "author": "glitchkid", "category": "music", "title": "Утро в бетоне",
        "genre": "Phonk", "bpm": 132, "key": "C# minor", "days": 3.2,
        "plays": 468, "downloads": 61, "track": "concrete_morning",
        "tags": ["phonk", "cowbell", "808", "dusty"],
        "description": "Фонк из бетонных дворов: 808, ковбелл и пыльный винил. Утренний свет, но с характером. Семплируй, режь, добавляй свои куплеты.",
        "likes": ["nightdrive", "lofi_mira", "beatcartel", "verba"],
    },
    {
        "slug": "trap-starter", "author": "nightdrive", "category": "project", "title": "Trap Starter Pack",
        "genre": "Trap", "bpm": 140, "key": "A minor", "days": 4.3,
        "plays": 0, "downloads": 328, "pack": ("project", 140.0, "A2"),
        "tags": ["flp", "stems", "midi", "template"],
        "description": "Готовый каркас трэп-бита: 4 stems, MIDI-паттерны баса, клавиш и мелодии, заметки по сборке. Открывай в FL Studio, меняй инструменты и доводи до релиза.",
        "likes": ["lofi_mira", "subbass", "glitchkid", "beatcartel", "tapehead", "verba"],
    },
    {
        "slug": "lofi-template", "author": "lofi_mira", "category": "project", "title": "Lo-Fi Template",
        "genre": "Lo-Fi", "bpm": 82, "key": "D minor", "days": 11.8,
        "plays": 0, "downloads": 241, "pack": ("project", 82.0, "D2"),
        "tags": ["lofi", "template", "stems", "midi"],
        "description": "Шаблон для lo-fi: stems с родесом, басом и барабанами, MIDI-дорожки и советы по обработке. Открой, выстави темп 82 — и играй.",
        "likes": ["nightdrive", "subbass", "tapehead", "verba"],
    },
    {
        "slug": "velvet-keys", "author": "plugin_lab", "category": "instrument", "title": "Velvet Keys",
        "genre": "R&B / Soul", "bpm": None, "key": "C major", "days": 6.6,
        "plays": 0, "downloads": 174, "pack": ("instrument", "Velvet Keys", "rhodes", "C3"),
        "tags": ["serum", "presets", "keys", "rnb"],
        "description": "Тёплый банк клавиш: родес, мягкие пэды и плюки в духе современного R&B. 8 сэмплов с картой нот — загружай в Sampler или DirectWave и играй.",
        "likes": ["nightdrive", "lofi_mira", "glitchkid", "beatcartel"],
    },
    {
        "slug": "vital-textures", "author": "glitchkid", "category": "instrument", "title": "Vital Textures Vol. 1",
        "genre": "Ambient", "bpm": None, "key": "A minor", "days": 15.3,
        "plays": 0, "downloads": 132, "pack": ("instrument", "Vital Textures Vol 1", "saw_soft", "A2", 10),
        "tags": ["vital", "textures", "ambient", "pads"],
        "description": "10 текстур для Vital: эмбиент, гранулярные пэды и атмосферные слои. Записал с полевых семплов и мягких синтезаторов — для интро, переходов и киношных моментов.",
        "likes": ["lofi_mira", "subbass", "plugin_lab"],
    },
    {
        "slug": "tapewarm", "author": "plugin_lab", "category": "plugin", "title": "TapeWarm Free",
        "genre": "Mixing", "bpm": None, "key": "", "days": 8.1,
        "plays": 0, "downloads": 402, "pack": ("plugin", "TapeWarm Free", "Saturation"),
        "tags": ["saturation", "tape", "free", "mix"],
        "description": "Бесплатный концепт плагина для мягкого насыщения: лёгкая сатурация, авто-гейн и режим Tape. Внутри — мануал и 6 готовых пресетов для вокала, барабанов и мастера.",
        "likes": ["nightdrive", "subbass", "glitchkid", "beatcartel", "tapehead", "verba"],
    },
    {
        "slug": "stereo-field", "author": "subbass", "category": "plugin", "title": "Stereo Field",
        "genre": "Mixing", "bpm": None, "key": "", "days": 19.4,
        "plays": 0, "downloads": 219, "pack": ("plugin", "Stereo Field", "Stereo imaging"),
        "tags": ["stereo", "mid-side", "utility", "mix"],
        "description": "Утилита для расширения стереобазы: mid/side, моно-совместимость и анализатор. Не разваливает низ и помогает аккуратно развести инструменты в миксе.",
        "likes": ["nightdrive", "plugin_lab", "tapehead"],
    },
    {
        "slug": "concrete-808", "author": "nightdrive", "category": "drumkit", "title": "Concrete 808 Kit",
        "genre": "Trap", "bpm": 140, "key": "A minor", "days": 2.4,
        "plays": 0, "downloads": 512, "pack": ("drumkit", "Concrete 808 Kit", 140.0, "A2"),
        "tags": ["808", "trap", "drums", "samples"],
        "description": "50 сэмплов: 808, кики, снейры, клэпы, хэты и перкуссия. Записано с аналоговых источников и обработано для плотного низа. Внутри — 9 one-shot'ов и два бонусных лупа.",
        "likes": ["lofi_mira", "subbass", "glitchkid", "plugin_lab", "beatcartel", "tapehead", "verba"],
    },
    {
        "slug": "dusty-breaks", "author": "tapehead", "category": "drumkit", "title": "Dusty Break Kit",
        "genre": "Lo-Fi", "bpm": 82, "key": "D minor", "days": 14.7,
        "plays": 0, "downloads": 367, "pack": ("drumkit", "Dusty Break Kit", 82.0, "D2"),
        "tags": ["breaks", "lofi", "dusty", "drums"],
        "description": "Пыльные брейки и one-shot'ы для lo-fi и boom bap: 9 сэмплов, два лупа и запас фактуры. Всё уже прогрето, осталось только нарезать по вкусу.",
        "likes": ["nightdrive", "lofi_mira", "subbass", "glitchkid", "verba"],
    },
]

COMMENTS = [
    ("neon-rain", "subbass", "808 на шестой доле — это огонь. Забрал в референсы.", 1.2),
    ("neon-rain", "lofi_mira", "Атмосфера просто космос. Пэды хочется слушать отдельно.", 0.8),
    ("neon-rain", "verba", "Под этот бит сразу придумался куплет. Есть контакт для коллаба?", 0.3),
    ("midnight", "tapehead", "Идеально под дождь за окном. Винил на своём месте.", 2.1),
    ("midnight", "nightdrive", "Родес звучит как надо. Какие настройки атаки?", 1.5),
    ("midnight", "verba", "Очень хочется напеть что-то поверх. Сохранила.", 0.6),
    ("deep-signal", "beatcartel", "Клубный грув, заберу в сет на выходные.", 1.9),
    ("deep-signal", "nightdrive", "Бас-линия качает. Стабы хорошо сидят.", 1.1),
    ("fracture", "glitchkid", "Риз-бас разрывает. 174 и такой воздух — респект.", 3.4),
    ("fracture", "plugin_lab", "Интересно, чем обрабатывал reese? Очень плотно.", 2.7),
    ("concrete-morning", "nightdrive", "Ковбелл-мелодия застряла в голове.", 0.9),
    ("concrete-morning", "beatcartel", "Вот это вайб. Скинь пак с 808, если можно.", 0.4),
    ("trap-starter", "verba", "Спасибо за шаблон, удобно разбирать автоматизацию.", 1.4),
    ("trap-starter", "beatcartel", "MIDI-дорожки — то, что нужно. Уже перекинул в свой проект.", 0.7),
    ("lofi-template", "tapehead", "Наконец-то нормальный lo-fi шаблон без лишнего.", 4.2),
    ("velvet-keys", "lofi_mira", "Сэмплы реально тёплые, спасибо! Родес — любовь.", 2.3),
    ("velvet-keys", "verba", "Уже набросала вокал поверх. Звучит дорого.", 1.0),
    ("vital-textures", "lofi_mira", "Текстуры красивые, особенно в интро.", 5.1),
    ("tapewarm", "nightdrive", "На вокале попробовал — мягко, не мылит.", 1.7),
    ("tapewarm", "subbass", "Tape-режим на барабанах звучит приятно. Спасибо, что бесплатно.", 1.3),
    ("concrete-808", "beatcartel", "Кик сидит отлично, 808 не конфликтуют. Забрал.", 0.8),
    ("concrete-808", "glitchkid", "Пак плотный. Особенно перкуссия.", 0.5),
    ("dusty-breaks", "lofi_mira", "Вот этих брейков мне не хватало. Спасибо!", 3.0),
]


def seed(force: bool = False) -> None:
    db.init_db()
    conn = db.connect()
    try:
        existing = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        if existing and not force:
            print("FL HUB: база уже содержит данные, пропускаю генерацию.")
            return
        if existing and force:
            conn.execute("DELETE FROM comments")
            conn.execute("DELETE FROM likes")
            conn.execute("DELETE FROM items")
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM users")
            conn.execute(
                "DELETE FROM sqlite_sequence WHERE name IN ('users', 'items', 'comments')"
            )
            conn.commit()
            for folder in (db.UPLOAD_DIR, db.COVER_DIR):
                for path in folder.glob("seed_*"):
                    path.unlink(missing_ok=True)

        print("FL HUB: создаю демо-пользователей...")
        password_hash = security.hash_password(DEMO_PASSWORD)
        user_ids: dict[str, int] = {}
        for user in USERS:
            cursor = conn.execute(
                "INSERT INTO users (username, email, password_hash, bio, avatar_color, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user["username"], user["email"], password_hash, user["bio"],
                 user["avatar_color"], _iso(user["days"])),
            )
            user_ids[user["username"]] = cursor.lastrowid

        print("FL HUB: генерирую треки, обложки и паки (это займёт около минуты)...")
        item_ids: dict[str, int] = {}
        for spec in ITEMS:
            category = spec["category"]
            slug = spec["slug"]
            cover_name = f"seed_{slug}.svg"
            (db.COVER_DIR / cover_name).write_text(
                art.generate_cover_svg(spec["title"], category, slug), encoding="utf-8"
            )
            file_path = ""
            audio_path = ""
            file_name = ""
            file_size = 0
            duration = None
            if category == "music":
                print(f"  • трек {spec['title']}...")
                buffer, actual_bpm = synth.render_track(spec["track"])
                audio_name = f"seed_{slug}.wav"
                synth.write_wav(db.UPLOAD_DIR / audio_name, buffer)
                audio_path = audio_name
                file_path = audio_name
                file_name = f"{slug}.wav"
                file_size = (db.UPLOAD_DIR / audio_name).stat().st_size
                duration = round(len(buffer) / synth.SR, 1)
                spec["bpm"] = int(actual_bpm)
            else:
                print(f"  • пак {spec['title']}...")
                kind = spec["pack"][0]
                if kind == "project":
                    _, bpm, root = spec["pack"]
                    stored, display_name, file_size = build_project_pack(
                        slug, bpm, root, spec["title"]
                    )
                    file_path = stored
                    file_name = display_name
                elif kind == "instrument":
                    _, title, table, root, *rest = spec["pack"]
                    count = rest[0] if rest else 8
                    stored, display_name, file_size = build_instrument_pack(
                        slug, title, table, root, count
                    )
                    file_path = stored
                    file_name = display_name
                elif kind == "plugin":
                    _, title, plugin_kind = spec["pack"]
                    stored, display_name, file_size = build_plugin_pack(
                        slug, title, plugin_kind
                    )
                    file_path = stored
                    file_name = display_name
                else:
                    _, title, bpm, root = spec["pack"]
                    stored, display_name, file_size = build_drumkit_pack(
                        slug, title, bpm, root
                    )
                    file_path = stored
                    file_name = display_name
            cursor = conn.execute(
                "INSERT INTO items (author_id, category, title, description, genre, bpm, "
                "music_key, tags, cover_path, file_path, file_name, file_size, audio_path, "
                "duration, plays, downloads, featured, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_ids[spec["author"]], category, spec["title"], spec["description"],
                    spec.get("genre", ""), spec.get("bpm"), spec.get("key", ""),
                    ",".join(spec.get("tags", [])), cover_name, file_path, file_name,
                    file_size, audio_path, duration, spec.get("plays", 0),
                    spec.get("downloads", 0), spec.get("featured", 0), _iso(spec["days"]),
                ),
            )
            item_ids[slug] = cursor.lastrowid
            for username in spec.get("likes", []):
                conn.execute(
                    "INSERT OR IGNORE INTO likes (item_id, user_id, created_at) VALUES (?, ?, ?)",
                    (item_ids[slug], user_ids[username], _iso(spec["days"] - 0.2)),
                )
        for slug, username, body, days in COMMENTS:
            conn.execute(
                "INSERT INTO comments (item_id, user_id, body, created_at) VALUES (?, ?, ?, ?)",
                (item_ids[slug], user_ids[username], body, _iso(days)),
            )
        conn.commit()
        print(f"FL HUB: готово — {len(USERS)} пользователей, {len(ITEMS)} работ.")
        print(f"FL HUB: демо-вход — nightdrive / {DEMO_PASSWORD}")
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    seed(force="--force" in sys.argv)
