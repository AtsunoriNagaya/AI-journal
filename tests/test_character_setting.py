from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.input.character_setting import load_setting_from_markdown


def _write_persona(path: Path, *, role_heading: str = "主人公", include_supplement: bool = True) -> None:
    lines = [
        "# 日記ペルソナ",
        "",
        f"## {role_heading}",
        "テスト用の人物",
        "",
        "## 背景",
        "任意の背景設定",
        "",
        "## 期間",
        "開始日 2026-04-01",
        "7日間",
        "",
        "## 1週間のテーマ",
        "日々の変化を記録する",
        "",
        "## 平日傾向",
        "主要な活動を中心に過ごす",
        "",
        "## 休日傾向",
        "休息と生活の見直しを中心に過ごす",
        "",
        "## 文体",
        "自然体",
        "",
        "## 想定読者",
        "同じ課題を持つ読者",
        "",
        "## 現実味の制約",
        "現実的な範囲の出来事に限定する",
        "",
    ]

    if include_supplement:
        lines.extend(
            [
                "## 補足設定",
                "- よく使う行動範囲: 生活圏",
                "- 興味・趣味: 読書",
                "- 不安や悩み: 進め方の迷い",
                "- 日常で起こりやすいこと: 連絡と確認作業",
                "- 避けたい展開: 不自然な偶然",
                "- 1週間を通して見せたい変化: 迷いから落ち着きへ",
                "",
            ]
        )

    path.write_text("\n".join(lines), encoding="utf-8")


class CharacterSettingCompatibilityRemovalTests(unittest.TestCase):
    def test_load_setting_requires_canonical_role_heading(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            persona_path = Path(tmp_dir) / "persona.md"
            _write_persona(persona_path, role_heading="キャラクター")

            with self.assertRaisesRegex(ValueError, "Markdown見出しが見つかりません: 主人公"):
                load_setting_from_markdown(str(persona_path))

    def test_load_setting_requires_supplement_section(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            persona_path = Path(tmp_dir) / "persona.md"
            _write_persona(persona_path, include_supplement=False)

            with self.assertRaisesRegex(ValueError, "Markdown見出しが見つかりません: 補足設定"):
                load_setting_from_markdown(str(persona_path))


if __name__ == "__main__":
    unittest.main()
