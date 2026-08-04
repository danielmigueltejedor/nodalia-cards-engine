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
        self.assertEqual(manifest["version"], "2.0.0-alpha.61")
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(manifest["dependencies"], [])
        self.assertTrue((COMPONENT / "translations" / "en.json").exists())
        self.assertFalse((COMPONENT / "strings.json").exists())

        config_flow = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn(
            "from homeassistant.config_entries import ConfigFlow, ConfigFlowResult",
            config_flow,
        )
        self.assertNotIn(
            "from homeassistant.data_entry_flow import ConfigFlowResult",
            config_flow,
        )

        websocket_api = (COMPONENT / "websocket_api.py").read_text(encoding="utf-8")
        self.assertIn("@websocket_api.require_admin", websocket_api)
        self.assertNotIn("connection.require_admin()", websocket_api)

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

    def test_publication_contract_includes_license_and_required_validation(self) -> None:
        self.assertIn("MIT License", (ROOT / "LICENSE").read_text(encoding="utf-8"))
        self.assertIn(
            "custom_components/nodalia/brand/icon.png",
            (ROOT / "README.md").read_text(encoding="utf-8"),
        )
        hacs_workflow = (ROOT / ".github" / "workflows" / "hacs.yml").read_text(
            encoding="utf-8"
        )
        hassfest_workflow = (
            ROOT / ".github" / "workflows" / "hassfest.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("category: integration", hacs_workflow)
        self.assertNotIn("ignore:", hacs_workflow)
        self.assertIn("home-assistant/actions/hassfest@", hassfest_workflow)

    def test_runtime_and_manifest_versions_stay_aligned(self) -> None:
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        const_source = (COMPONENT / "const.py").read_text(encoding="utf-8")
        self.assertIn(
            f'INTEGRATION_VERSION: Final = "{manifest["version"]}"',
            const_source,
        )


if __name__ == "__main__":
    unittest.main()
