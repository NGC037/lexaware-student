'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { ProvenanceContract } = require('./index');

const id = '123e4567-e89b-42d3-a456-426614174000';
const hash = 'a'.repeat(64);

function context({ writer = true } = {}) {
  const data = new Map();
  let tx = 0;
  return {
    data,
    contract: new ProvenanceContract(),
    ctx: {
      clientIdentity: {
        getMSPID: () => 'Org1MSP',
        getAttributeValue: (name) => name === 'provenance.writer' && writer ? 'true' : null,
      },
      stub: {
        createCompositeKey: (_name, parts) => parts.join(':'),
        getState: async (key) => data.get(key) || Buffer.alloc(0),
        getStateByPartialCompositeKey: async (_name, parts) => {
          const prefix = `${parts.join(':')}:`;
          const entries = [...data.entries()].filter(([key]) => key.startsWith(prefix));
          let position = 0;
          return {
            [Symbol.asyncIterator]: async function* () {
              while (position < entries.length) {
                const [key, value] = entries[position++];
                yield { key, value };
              }
            },
            close: async () => {},
          };
        },
        putState: async (key, value) => data.set(key, value),
        getTxID: () => `tx-${++tx}`,
        getTxTimestamp: () => ({ seconds: { toString: () => '1700000000' } }),
      },
    },
  };
}

test('anchor is idempotent for same version and rejects conflicting duplicate', async () => {
  const { contract, ctx } = context();
  const first = JSON.parse(await contract.Anchor(ctx, 'document_report', id, '1', hash));
  const again = JSON.parse(await contract.Anchor(ctx, 'document_report', id, '1', hash));
  assert.equal(first.transaction_id, again.transaction_id);
  await assert.rejects(contract.Anchor(ctx, 'document_report', id, '1', 'b'.repeat(64)), /conflict/);
});

test('writer, object, hash, version, and transition validations reject hostile inputs', async () => {
  const denied = context({ writer: false });
  await assert.rejects(denied.contract.Anchor(denied.ctx, 'document_report', id, '1', hash), /authorization/);
  const allowed = context();
  await assert.rejects(allowed.contract.Anchor(allowed.ctx, 'student', id, '1', hash), /object type/);
  await assert.rejects(allowed.contract.Anchor(allowed.ctx, 'document_report', 'student@x.test', '1', hash), /identifier/);
  await assert.rejects(allowed.contract.Anchor(allowed.ctx, 'document_report', id, '1', 'not-a-hash'), /hash/);
  await assert.rejects(allowed.contract.Anchor(allowed.ctx, 'document_report', id, '0', hash), /version/);
  await allowed.contract.Anchor(allowed.ctx, 'document_report', id, '1', hash);
  await assert.rejects(allowed.contract.Transition(allowed.ctx, 'document_report', id, '1', 'supersede', '1'), /superseding/);
});

test('revoke and supersede are authorized and preserve immutable hash', async () => {
  const { contract, ctx, data } = context();
  await contract.Anchor(ctx, 'document_report', id, '1', hash);
  const transitioned = JSON.parse(await contract.Transition(ctx, 'document_report', id, '1', 'supersede', '2'));
  assert.equal(transitioned.status, 'superseded');
  assert.equal(transitioned.content_hash, hash);
  assert.equal(transitioned.superseded_by_version, 2);
  const verified = JSON.parse(await contract.Verify(ctx, 'document_report', id, '1'));
  assert.equal(verified.status, 'superseded');
  assert.equal(data.size, 1);
  const next = JSON.parse(await contract.Anchor(ctx, 'document_report', id, '2', 'b'.repeat(64)));
  assert.equal(next.version, 2);
});

test('a higher version cannot be anchored before the prior version transitions', async () => {
  const { contract, ctx } = context();
  await contract.Anchor(ctx, 'help_resource', id, '1', hash);
  await assert.rejects(contract.Anchor(ctx, 'help_resource', id, '2', 'b'.repeat(64)), /version transition/);
});
