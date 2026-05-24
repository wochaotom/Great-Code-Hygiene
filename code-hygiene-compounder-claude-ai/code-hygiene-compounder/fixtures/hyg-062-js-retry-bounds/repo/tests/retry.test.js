const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const test = require("node:test");

const { callWithRetry } = require("../app/retry");

test("stops after the configured number of attempts", async () => {
  let calls = 0;
  await assert.rejects(
    callWithRetry(
      async () => {
        calls += 1;
        throw new Error("temporary");
      },
      { maxAttempts: 3 },
    ),
    /temporary/,
  );
  assert.equal(calls, 3);
});

test("still succeeds after transient failures", async () => {
  let calls = 0;
  const result = await callWithRetry(
    async () => {
      calls += 1;
      if (calls < 3) {
        throw new Error("temporary");
      }
      return "ok";
    },
    { maxAttempts: 3 },
  );

  assert.equal(result, "ok");
  assert.equal(calls, 3);
});

test("non-finite maxAttempts cannot create an unbounded loop", () => {
  const script = `
    const { callWithRetry } = require("./app/retry");
    let calls = 0;
    callWithRetry(
      async () => {
        calls += 1;
        throw new Error("temporary");
      },
      { maxAttempts: Infinity },
    ).then(
      () => console.log(JSON.stringify({ outcome: "resolved", calls })),
      (error) => console.log(JSON.stringify({
        outcome: "rejected",
        calls,
        message: error && error.message,
      })),
    );
  `;
  const result = spawnSync(process.execPath, ["-e", script], {
    cwd: process.cwd(),
    encoding: "utf8",
    timeout: 1000,
  });

  assert.notEqual(
    result.error && result.error.code,
    "ETIMEDOUT",
    "maxAttempts: Infinity created an unbounded retry loop",
  );
  assert.equal(result.status, 0, result.stderr);

  const outcome = JSON.parse(result.stdout.trim());
  assert.equal(outcome.outcome, "rejected");
  assert.ok(outcome.calls <= 3, `expected at most 3 attempts, saw ${outcome.calls}`);
});

test("non-positive maxAttempts still makes one bounded attempt", async () => {
  for (const maxAttempts of [0, -1]) {
    let calls = 0;
    await assert.rejects(
      callWithRetry(
        async () => {
          calls += 1;
          throw new Error("temporary");
        },
        { maxAttempts },
      ),
      /temporary/,
    );
    assert.equal(calls, 1, `maxAttempts ${maxAttempts} should make one attempt`);
  }
});

test("fractional maxAttempts is normalized before the retry loop", async () => {
  let calls = 0;
  await assert.rejects(
    callWithRetry(
      async () => {
        calls += 1;
        throw new Error("temporary");
      },
      { maxAttempts: 2.5 },
    ),
    /temporary/,
  );
  assert.equal(calls, 2);
});
