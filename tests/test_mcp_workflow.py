#!/usr/bin/env python3
"""Offline MCP workflow contract and integration regressions; no inference calls."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("standards_mcp_workflow", ROOT / "mcp/server.py")
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)

sys.path.insert(0, str(ROOT))
from tests.test_workflow_checker import evidence_for
from tests.test_workflow_engine import brief, html_for, renderer_identity

RETRIEVAL = {"list_systems", "get_system", "get_tokens", "get_archetypes", "select_move"}
WORKFLOW = {"plan_artifact", "assemble_context", "check_artifact", "prepare_repair"}
CAPABILITIES = {"get_workflow_capabilities"}


class MCPWorkflowTests(unittest.TestCase):
    def request(self, method, params=None, rid=1):
        message = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            message["params"] = params
        return server.handle(message)

    def call(self, name, arguments):
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def decoded(self, response):
        self.assertNotIn("error", response)
        result = response["result"]
        self.assertFalse(result.get("isError"), result)
        self.assertEqual(result["content"][0]["type"], "text")
        decoded = json.loads(result["content"][0]["text"])
        if "structuredContent" in result:
            self.assertEqual(result["structuredContent"], decoded)
        return decoded

    def assert_tool_error(self, response):
        self.assertNotIn("error", response)
        self.assertTrue(response["result"]["isError"])
        self.assertIsInstance(response["result"]["content"][0]["text"], str)

    def test_tool_surface_advertises_canonical_nested_schemas(self):
        tools = self.request("tools/list")["result"]["tools"]
        by_name = {tool["name"]: tool for tool in tools}
        self.assertEqual(set(by_name), RETRIEVAL | WORKFLOW | CAPABILITIES)
        self.assertEqual(len(tools), len(by_name))
        schema = server.workflow_module("schema")
        self.assertEqual(by_name["plan_artifact"]["inputSchema"]["properties"]["brief"],
                         schema.load_schema("brief"))
        self.assertEqual(by_name["plan_artifact"]["inputSchema"]["properties"]["renderer"],
                         schema.load_schema("renderer-identity"))
        for name in WORKFLOW - {"plan_artifact"}:
            with self.subTest(tool=name):
                self.assertEqual(by_name[name]["inputSchema"]["properties"]["plan"],
                                 schema.load_schema("plan"))
                self.assertFalse(by_name[name]["inputSchema"]["additionalProperties"])
        repair = by_name["prepare_repair"]["inputSchema"]
        self.assertEqual(repair["required"], ["plan", "html"])
        self.assertEqual(repair["properties"]["history"], schema.load_schema("history"))
        self.assertEqual(repair["properties"]["render_evidence"], schema.load_schema("render-evidence"))
        self.assertEqual(by_name["plan_artifact"]["outputSchema"], schema.load_schema("plan"))
        self.assertEqual(by_name["assemble_context"]["outputSchema"], schema.load_schema("context"))
        self.assertEqual(by_name["check_artifact"]["outputSchema"], schema.load_schema("report"))
        self.assertEqual(by_name["prepare_repair"]["outputSchema"], schema.load_schema("repair"))
        self.assertEqual(by_name["get_workflow_capabilities"]["outputSchema"],
                         schema.load_schema("support-manifest"))
        capabilities = self.decoded(self.call("get_workflow_capabilities", {}))
        self.assertEqual(capabilities, server.workflow_module("support").load_support_manifest())
        self.assertEqual(capabilities["workflow"]["version"], "0.2.0")
        self.assertEqual(len(capabilities["supported"]), 6)
        self.assert_tool_error(self.call("get_workflow_capabilities", {"unexpected": True}))

    def test_existing_retrieval_tools_keep_their_result_shapes(self):
        systems = self.decoded(self.call("list_systems", {}))
        self.assertIn("instrument", [item["system"] for item in systems["systems"]])
        self.assertIn("colour", self.decoded(self.call("get_tokens", {"system": "instrument"})))
        self.assertIn("moves", self.decoded(self.call("get_archetypes", {"system": "instrument"})))
        selected = self.decoded(self.call("select_move", {"system": "instrument", "job": "E"}))
        self.assertGreater(len(selected["matches"]), 0)
        instructions = self.call("get_system", {"system": "instrument", "build": "compact"})
        self.assertFalse(instructions["result"].get("isError"))
        self.assertTrue(instructions["result"]["content"][0]["text"])

    def test_malformed_workflow_inputs_do_not_reach_dispatch(self):
        cases = [("plan_artifact", {"brief": value, "renderer": renderer_identity()})
                 for value in ([], None, 1, True, "brief", {})]
        for name in WORKFLOW - {"plan_artifact"}:
            cases.extend((name, {"plan": value, **({"html": "<p>test</p>"} if name != "assemble_context" else {})})
                         for value in ([], None, 1, True, "plan", {}))
        for name, arguments in cases:
            with self.subTest(tool=name, arguments=arguments):
                with patch.dict(server.DISPATCH, {name: lambda **_: self.fail("malformed input reached dispatch")}):
                    self.assert_tool_error(self.call(name, arguments))

    def test_stdio_recovers_after_deep_json_and_nested_shape_errors(self):
        malformed = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                     "params": {"name": "plan_artifact", "arguments": {"brief": {"unexpected": [None]}}}}
        messages = ["[" * 2000 + "0" + "]" * 2000, json.dumps(malformed),
                    json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"})]
        stdout = io.StringIO()
        server.serve(io.StringIO("\n".join(messages)), stdout)
        replies = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(replies[0]["error"]["code"], -32600)
        self.assert_tool_error(replies[1])
        self.assertEqual(replies[2], {"jsonrpc": "2.0", "id": 3, "result": {}})

    def test_stdio_rejects_duplicate_keys_nonfinite_numbers_and_oversize_then_recovers(self):
        duplicate = '{"jsonrpc":"2.0","id":1,"id":2,"method":"ping"}'
        nonfinite = '{"jsonrpc":"2.0","id":NaN,"method":"ping"}'
        oversized = " " * (server.MAX_MESSAGE_CHARS + 1)
        ping = json.dumps({"jsonrpc": "2.0", "id": 4, "method": "ping"})
        stdout = io.StringIO()
        server.serve(io.StringIO("\n".join([duplicate, nonfinite, oversized, ping])), stdout)
        replies = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual([reply.get("error", {}).get("code") for reply in replies[:3]],
                         [-32700, -32700, -32600])
        self.assertEqual(replies[3], {"jsonrpc": "2.0", "id": 4, "result": {}})

    def test_server_launches_from_an_unrelated_working_directory(self):
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-B", str(ROOT / "mcp/server.py")],
                                    cwd=directory, input=json.dumps(message) + "\n",
                                    text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        tools = json.loads(result.stdout)["result"]["tools"]
        self.assertEqual({tool["name"] for tool in tools}, RETRIEVAL | WORKFLOW | CAPABILITIES)

    def test_complete_workflow_uses_the_selected_pack_catalogue(self):
        with tempfile.TemporaryDirectory() as directory:
            packs = Path(directory) / "catalogue"
            shutil.copytree(ROOT / "packs/instrument", packs / "instrument")
            original = server.PACKS
            server.PACKS = str(packs)
            try:
                plan = self.decoded(self.call("plan_artifact", {
                    "brief": brief(), "renderer": renderer_identity()}))
                context = self.decoded(self.call("assemble_context", {"plan": plan}))
                html = html_for(plan)
                evidence = evidence_for(plan, html)
                report = self.decoded(self.call("check_artifact", {
                    "plan": plan, "html": html, "render_evidence": evidence}))
                repair = self.decoded(self.call("prepare_repair", {
                    "plan": plan, "html": html, "render_evidence": evidence}))
            finally:
                server.PACKS = original
        self.assertEqual(plan["move"], "Schedule")
        self.assertEqual(context["planSha256"], report["planSha256"])
        self.assertEqual(report["status"], "pass")
        self.assertEqual(repair["action"], "complete")


if __name__ == "__main__":
    unittest.main()
