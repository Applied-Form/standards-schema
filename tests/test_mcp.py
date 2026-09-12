#!/usr/bin/env python3
"""Offline MCP boundary regressions; synthetic files only, no client required."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("standards_mcp", Path(__file__).resolve().parents[1] / "mcp/server.py")
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


class MCPBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.packs = self.root / "packs"
        self.pack = self.packs / "instrument"
        self.pack.mkdir(parents=True)
        original = server.PACKS
        server.PACKS = str(self.packs)
        self.addCleanup(setattr, server, "PACKS", original)
        files = {
            "manifest.json": '{"system":"Instrument"}',
            "SKILL.md": "Full synthetic instructions",
            "SKILL-compact.md": "Compact synthetic instructions",
            "REFERENCE.md": "Synthetic reference",
            "LICENSE": "CC BY 4.0",
            "tokens.json": '{"synthetic":"token"}',
            "archetypes.json": json.dumps({"moves": [{"job": "E", "jobName": "Evidence", "name": "Readout"}]}),
            "assets/type scale.json": '{"size":12}',
        }
        for name, value in files.items():
            target = self.pack / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value, encoding="utf-8")
        self.secret = self.root / "private.txt"
        self.secret.write_text("OUTSIDE-CATALOGUE-SENTINEL", encoding="utf-8")

    def request(self, method, params=None):
        message = {"jsonrpc": "2.0", "id": 7, "method": method}
        if params is not None:
            message["params"] = params
        return server.handle(message)

    def assert_protocol_error(self, response, code=-32602):
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["error"]["code"], code)
        self.assertNotIn("OUTSIDE-CATALOGUE-SENTINEL", json.dumps(response))

    def test_valid_requests_and_nested_resource_reads_still_work(self):
        self.assertEqual(self.request("initialize")["result"]["protocolVersion"], server.PROTOCOL_VERSION)
        tools = self.request("tools/list")["result"]["tools"]
        self.assertEqual({tool["name"] for tool in tools}, set(server.DISPATCH))
        for uri, expected in (("standards://instrument/SKILL.md", "Full synthetic instructions"),
                              ("standards://instrument/assets/type%20scale.json", '{"size":12}')):
            response = self.request("resources/read", {"uri": uri})
            self.assertEqual(response["result"]["contents"][0]["text"], expected)
        for job in ("E", "evidence", " Evidence "):
            response = self.request("tools/call", {"name": "select_move", "arguments": {"system": "instrument", "job": job}})
            self.assertEqual(json.loads(response["result"]["content"][0]["text"])["matches"][0]["name"], "Readout")
        self.assertFalse(self.request("tools/call", {"name": "list_systems"})["result"].get("isError"))

    def test_traversal_absolute_and_encoded_resource_paths_are_rejected(self):
        other = self.packs / "other"
        other.mkdir()
        (other / "manifest.json").write_text('{}')
        (other / "private.txt").write_text("OUTSIDE-CATALOGUE-SENTINEL")
        bad = [
            "standards://instrument/../../private.txt",
            "standards://instrument/../other/private.txt",
            "standards://../private.txt",
            "standards:///private.txt",
            f"standards://instrument/{self.secret}",
            "standards://instrument/C:/private.txt",
            "standards://instrument/..\\..\\private.txt",
            "standards://instrument/%2e%2e/%2e%2e/private.txt",
            "standards://instrument/%2E%2E%2f%2E%2E%2fprivate.txt",
            "standards://%2e%2e/private.txt",
            "standards://instrument/%5c..%5cprivate.txt",
            "standards://instrument/%2fprivate.txt",
            "standards://instrument/%252e%252e/private.txt",
            "standards://instrument/SKILL.md%00",
            "standards://instrument/%ff",
            "standards://instrument/SKILL.md?other=private.txt",
            "standards://instrument/SKILL.md#fragment",
            "standards://instrument/SKILL.md\n",
        ]
        for uri in bad:
            with self.subTest(uri=uri):
                self.assert_protocol_error(self.request("resources/read", {"uri": uri}))

    def test_tools_cannot_select_paths_as_systems(self):
        for system in ("..", "../outside", str(self.root), "instrument/../other", "instrument\\..\\other", "C:\\outside", "instrument\x00"):
            with self.subTest(system=system):
                response = self.request("tools/call", {"name": "get_tokens", "arguments": {"system": system}})
                self.assertTrue(response["result"]["isError"])
                self.assertNotIn("OUTSIDE-CATALOGUE-SENTINEL", json.dumps(response))

    def test_symlink_escapes_cannot_be_read_or_advertised(self):
        outside = self.root / "outside-pack"
        outside.mkdir()
        (outside / "manifest.json").write_text('{"system":"OUTSIDE-CATALOGUE-SENTINEL"}')
        (outside / "tokens.json").write_text("OUTSIDE-CATALOGUE-SENTINEL")
        (self.packs / "linked-pack").symlink_to(outside, target_is_directory=True)
        (self.pack / "escape.txt").symlink_to(self.secret)
        (self.pack / "nested").symlink_to(outside, target_is_directory=True)
        (self.pack / "REFERENCE.md").unlink()
        (self.pack / "REFERENCE.md").symlink_to(self.secret)
        # A file in another installed pack is also outside the selected pack.
        sibling = self.packs / "sibling"
        sibling.mkdir()
        (sibling / "manifest.json").write_text('{}')
        (sibling / "private.txt").write_text("OUTSIDE-CATALOGUE-SENTINEL")
        (self.pack / "sibling.txt").symlink_to(sibling / "private.txt")
        for uri in ("standards://linked-pack/tokens.json", "standards://instrument/escape.txt",
                    "standards://instrument/nested/tokens.json", "standards://instrument/REFERENCE.md",
                    "standards://instrument/sibling.txt"):
            with self.subTest(uri=uri):
                self.assert_protocol_error(self.request("resources/read", {"uri": uri}))
        self.assertNotIn("linked-pack", server.slugs())
        listing = self.request("resources/list")
        self.assertNotIn("standards://instrument/REFERENCE.md", json.dumps(listing))
        self.assertNotIn("OUTSIDE-CATALOGUE-SENTINEL", json.dumps(self.request("tools/call", {"name": "list_systems"})))

    def test_uninstalled_directory_is_not_a_pack_resource(self):
        directory = self.packs / "not-a-pack"
        directory.mkdir()
        (directory / "private.txt").write_text("OUTSIDE-CATALOGUE-SENTINEL")
        self.assert_protocol_error(self.request("resources/read", {"uri": "standards://not-a-pack/private.txt"}))

    def test_internal_symlink_is_readable_but_a_loop_is_handled(self):
        (self.pack / "alias.json").symlink_to(self.pack / "tokens.json")
        response = self.request("resources/read", {"uri": "standards://instrument/alias.json"})
        self.assertEqual(response["result"]["contents"][0]["text"], '{"synthetic":"token"}')
        (self.pack / "loop.txt").symlink_to(self.pack / "loop.txt")
        self.assert_protocol_error(self.request("resources/read", {"uri": "standards://instrument/loop.txt"}))

    def test_malformed_request_envelopes_return_invalid_request(self):
        for message in ([], [1], None, 1, "request", {},
                        {"jsonrpc": "2.0", "id": 7, "method": []},
                        {"jsonrpc": "1.0", "id": 7, "method": "ping"},
                        {"jsonrpc": "2.0", "id": {}, "method": "ping"},
                        {"jsonrpc": "2.0", "id": True, "method": "ping"}):
            with self.subTest(message=message):
                self.assert_protocol_error(server.handle(message), -32600)

    def test_malformed_params_and_tool_call_shapes_return_invalid_params(self):
        for params in ([], [1], None, "params", 1, False):
            with self.subTest(params=params):
                self.assert_protocol_error(server.handle({"jsonrpc": "2.0", "id": 7, "method": "resources/read", "params": params}))
        for uri in (None, [], {}, 1, True):
            self.assert_protocol_error(self.request("resources/read", {"uri": uri}))
        for name in (None, [], {}, 1, True):
            self.assert_protocol_error(self.request("tools/call", {"name": name}))
        for arguments in ([], [1], None, "arguments", 1, False):
            self.assert_protocol_error(self.request("tools/call", {"name": "list_systems", "arguments": arguments}))

    def test_non_string_and_invalid_tool_arguments_are_handled_tool_errors(self):
        for name, arguments in (("select_move", {"system": "instrument", "job": []}),
                                ("select_move", {"system": "instrument", "job": None}),
                                ("select_move", {"system": "instrument", "job": 1}),
                                ("get_tokens", {"system": {}}),
                                ("get_system", {"system": "instrument", "build": []}),
                                ("get_system", {"system": "instrument", "build": "invalid"}),
                                ("get_tokens", {}), ("list_systems", {"extra": "argument"})):
            with self.subTest(name=name, arguments=arguments):
                response = self.request("tools/call", {"name": name, "arguments": arguments})
                self.assertEqual(response["id"], 7)
                self.assertTrue(response["result"]["isError"])
                self.assertEqual(response["result"]["content"][0]["type"], "text")

    def test_notifications_and_unknown_methods_preserve_protocol_behavior(self):
        for method in ("notifications/initialized", "notifications/cancelled", "unknown", "ping"):
            self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": method}))
        self.assert_protocol_error(self.request("unknown"), -32601)
        self.assert_protocol_error(self.request("tools/call", {"name": "unknown"}), -32601)

    def test_stdio_recovers_after_bad_json_list_and_non_string_job(self):
        messages = ["{invalid json", "[]", json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "select_move", "arguments": {"system": "instrument", "job": []}}}),
                    json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                    json.dumps({"jsonrpc": "2.0", "id": 4, "method": "ping"})]
        stdout = io.StringIO()
        server.serve(io.StringIO("\n".join(messages)), stdout)
        responses = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(len(responses), 4)
        self.assert_protocol_error(responses[0], -32700)
        self.assert_protocol_error(responses[1], -32600)
        self.assertTrue(responses[2]["result"]["isError"])
        self.assertEqual(responses[3], {"jsonrpc": "2.0", "id": 4, "result": {}})


if __name__ == "__main__":
    unittest.main()
