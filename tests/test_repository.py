"""Repository-level contracts for Nodalia Cards Engine."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "nodalia"


class RepositoryTests(unittest.TestCase):
    def test_hacs_and_manifest_describe_an_optional_integration(self) -> None:
        hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(hacs["name"], "Nodalia Cards Engine")
        self.assertNotIn("filename", hacs)
        self.assertEqual(manifest["domain"], "nodalia")
        self.assertEqual(manifest["name"], "Nodalia Cards Engine")
        self.assertEqual(manifest["version"], "2.0.0-alpha.59")
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(manifest["dependencies"], [])
        self.assertTrue((COMPONENT / "strings.json").exists())

    def test_engine_does_not_bundle_or_register_frontend_files(self) -> None:
        self.assertFalse((COMPONENT / "frontend.py").exists())
        self.assertFalse((COMPONENT / "frontend").exists())
        init_source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("NodaliaFrontendRegistration", init_source)
        self.assertNotIn("DATA_FRONTEND", init_source)

    def test_hacs_brand_icon_is_a_256_pixel_png(self) -> None:
        icon = (COMPONENT / "brand" / "icon.png").read_bytes()
        self.assertEqual(icon[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", icon[16:24])
        self.assertEqual((width, height), (256, 256))


if __name__ == "__main__":
    unittest.main()
