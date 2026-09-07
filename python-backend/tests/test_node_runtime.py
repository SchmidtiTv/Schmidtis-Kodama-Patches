import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.lib.integrations.node_runtime import NodeRuntime


def test_adopts_bundled_node_and_keeps_it_outside_the_bundle() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bundle = root / "bundle"
        bundle.mkdir()
        executable = bundle / ("node.exe" if os.name == "nt" else "node")
        executable.write_bytes(b"node")
        runtime = NodeRuntime(root / "runtime", bundle_roots=[bundle])

        runtime._adopt(executable)

        assert runtime.installed_path.read_bytes() == b"node"
        assert runtime.installed_path.parent == root / "runtime"


def test_checksum_lookup_accepts_only_the_requested_node_asset() -> None:
    response = Mock()
    response.text = "abc  win-x64/node.exe\ndef  other-file\n"
    runtime = NodeRuntime(Path("/tmp/runtime"), bundle_roots=[])

    with patch("src.lib.integrations.node_runtime.requests.get", return_value=response):
        assert runtime._expected_checksum("win-x64/node.exe") == "abc"
        assert runtime._expected_checksum("missing") is None
