import test from "node:test";
import assert from "node:assert/strict";
import { sessionAuthHeaders } from "../src/auth-headers.js";

test("direct deployment keeps backend Bearer transport", () => {
    assert.deepEqual(sessionAuthHeaders("session", {}), { Authorization: "Bearer session" });
});

test("proxy deployment leaves Authorization available for browser Basic auth", () => {
    const document = { querySelector: () => ({ content: "X-App-Authorization" }) };
    assert.deepEqual(sessionAuthHeaders("session", document), { "X-App-Authorization": "Bearer session" });
});

test("unexpected metadata cannot select an arbitrary credential header", () => {
    const document = { querySelector: () => ({ content: "X-Untrusted" }) };
    assert.deepEqual(sessionAuthHeaders("session", document), { Authorization: "Bearer session" });
});
