'use strict';

const { Contract } = require('fabric-contract-api');

const OBJECT_TYPES = new Set(['knowledge_version', 'help_resource', 'document_report']);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const HASH = /^[0-9a-f]{64}$/;

class ProvenanceContract extends Contract {
  _assertWriter(ctx) {
    const identity = ctx.clientIdentity;
    if (identity.getMSPID() !== 'Org1MSP' || identity.getAttributeValue('provenance.writer') !== 'true') {
      throw new Error('provenance writer authorization required');
    }
  }

  _validate(objectType, objectId, version) {
    if (!OBJECT_TYPES.has(objectType)) throw new Error('invalid object type');
    if (!UUID.test(objectId)) throw new Error('invalid object identifier');
    if (!Number.isSafeInteger(version) || version < 1) throw new Error('invalid version');
  }

  _key(ctx, objectType, objectId, version) {
    return ctx.stub.createCompositeKey('provenance', [objectType, objectId, String(version)]);
  }

  _timestamp(ctx) {
    const seconds = Number(ctx.stub.getTxTimestamp().seconds.toString());
    return new Date(seconds * 1000).toISOString();
  }

  async Anchor(ctx, objectType, objectId, versionValue, contentHash) {
    this._assertWriter(ctx);
    const version = Number(versionValue);
    this._validate(objectType, objectId, version);
    if (!HASH.test(contentHash)) throw new Error('invalid sha256 hash');
    const key = this._key(ctx, objectType, objectId, version);
    const existing = await ctx.stub.getState(key);
    if (existing.length) {
      const record = JSON.parse(existing.toString());
      if (record.content_hash !== contentHash) throw new Error('anchor version hash conflict');
      return JSON.stringify(record);
    }
    const history = await ctx.stub.getStateByPartialCompositeKey('provenance', [objectType, objectId]);
    let highestVersion = 0;
    let highestRecord = null;
    try {
      for await (const entry of history) {
        const prior = JSON.parse(entry.value.toString());
        if (prior.version > highestVersion) {
          highestVersion = prior.version;
          highestRecord = prior;
        }
      }
    } finally {
      await history.close();
    }
    if (highestVersion && (version <= highestVersion || !['superseded', 'revoked'].includes(highestRecord.status))) {
      throw new Error('invalid version transition');
    }
    const record = {
      object_type: objectType,
      object_id: objectId,
      version,
      content_hash: contentHash,
      status: 'anchored',
      transaction_id: ctx.stub.getTxID(),
      last_transaction_id: ctx.stub.getTxID(),
      anchored_at: this._timestamp(ctx),
      changed_at: null,
      superseded_by_version: null,
    };
    await ctx.stub.putState(key, Buffer.from(JSON.stringify(record)));
    return JSON.stringify(record);
  }

  async Verify(ctx, objectType, objectId, versionValue) {
    const version = Number(versionValue);
    this._validate(objectType, objectId, version);
    const state = await ctx.stub.getState(this._key(ctx, objectType, objectId, version));
    return state.length
      ? JSON.stringify({ exists: true, ...JSON.parse(state.toString()) })
      : JSON.stringify({ exists: false });
  }

  async Transition(ctx, objectType, objectId, versionValue, action, supersededByValue) {
    this._assertWriter(ctx);
    const version = Number(versionValue);
    this._validate(objectType, objectId, version);
    if (action !== 'revoke' && action !== 'supersede') throw new Error('invalid transition');
    const supersededBy = supersededByValue === '' ? null : Number(supersededByValue);
    if (action === 'supersede' && (!Number.isSafeInteger(supersededBy) || supersededBy <= version)) {
      throw new Error('invalid superseding version');
    }
    const key = this._key(ctx, objectType, objectId, version);
    const state = await ctx.stub.getState(key);
    if (!state.length) throw new Error('anchor not found');
    const record = JSON.parse(state.toString());
    const targetStatus = action === 'revoke' ? 'revoked' : 'superseded';
    if (record.status === targetStatus) return JSON.stringify(record);
    if (record.status !== 'anchored') throw new Error('invalid anchor state transition');
    record.status = targetStatus;
    record.changed_at = this._timestamp(ctx);
    record.last_transaction_id = ctx.stub.getTxID();
    record.superseded_by_version = supersededBy;
    await ctx.stub.putState(key, Buffer.from(JSON.stringify(record)));
    return JSON.stringify(record);
  }
}

module.exports = { ProvenanceContract };
