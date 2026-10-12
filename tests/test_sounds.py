from __future__ import annotations

import json
import os

from j2b.report import Report
from j2b.vanilla_assets import _convert_sounds


def test_login_music_uses_music_category_and_global_distance(tmp_path):
    assets = tmp_path / "assets"
    sounds = assets / "minecraft" / "sounds"
    sounds.mkdir(parents=True)
    (sounds / "friends_wine.ogg").write_bytes(b"OggS")
    (assets / "minecraft" / "sounds.json").write_text(
        json.dumps({"friends_wine": {"sounds": ["friends_wine"]}}),
        encoding="utf-8",
    )

    pack = tmp_path / "pack"
    report = Report()
    _convert_sounds(str(assets), str(pack), report)

    output = json.loads(
        (pack / "sounds" / "sound_definitions.json").read_text(encoding="utf-8")
    )
    definition = output["sound_definitions"]["friends_wine"]
    assert definition["category"] == "music"
    assert definition["max_distance"] == 9999.0
