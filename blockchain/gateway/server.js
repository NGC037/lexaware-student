'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const http = require('node:http');
const grpc = require('@grpc/grpc-js');
const { connect, signers } = require('@hyperledger/fabric-gateway');

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const HASH = /^[0-9a-f]{64}$/;
const OBJECT_TYPES = new Set(['knowledge_version', 'help_resource', 'document_report']);

function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`missing ${name}`);
  return value;
}

const token = required('FABRIC_GATEWAY_TOKEN');
function privateKeyPath(location) {
  const stat = fs.statSync(location);
  if (stat.isFile()) return location;
  const candidates = fs.readdirSync(location).filter((name) => !name.startsWith('.'));
  if (candidates.length !== 1) throw new Error('invalid private key directory');
  return `${location}/${candidates[0]}`;
}
const config = {
  peer: required('FABRIC_PEER_ENDPOINT'),
  tls: required('FABRIC_TLS_CERT'),
  identity: required('FABRIC_ID_CERT'),
  key: required('FABRIC_ID_KEY'),
  msp: process.env.FABRIC_MSP_ID || 'Org1MSP',
  channel: process.env.FABRIC_CHANNEL || 'provenance',
  chaincode: process.env.FABRIC_CHAINCODE || 'provenance',
};

const tlsCert = fs.readFileSync(config.tls);
const client = new grpc.Client(config.peer, grpc.credentials.createSsl(tlsCert), {
  'grpc.ssl_target_name_override': 'peer0.org1.example.com',
});
const gateway = connect({
  client,
  identity: { mspId: config.msp, credentials: fs.readFileSync(config.identity) },
  signer: signers.newPrivateKeySigner(crypto.createPrivateKey(fs.readFileSync(privateKeyPath(config.key)))),
  evaluateOptions: () => ({ deadline: Date.now() + 5000 }),
  endorseOptions: () => ({ deadline: Date.now() + 15000 }),
  submitOptions: () => ({ deadline: Date.now() + 15000 }),
  commitStatusOptions: () => ({ deadline: Date.now() + 60000 }),
});
const contract = gateway.getNetwork(config.channel).getContract(config.chaincode);

function parseRecord(bytes) {
  const record = JSON.parse(Buffer.from(bytes).toString('utf8'));
  if (!record || typeof record !== 'object') throw new Error('invalid ledger response');
  return record;
}

function validateObject(body) {
  if (!body || !OBJECT_TYPES.has(body.object_type)) throw new Error('invalid object type');
  if (typeof body.object_id !== 'string' || !UUID.test(body.object_id)) throw new Error('invalid object id');
  if (!Number.isSafeInteger(body.version) || body.version < 1) throw new Error('invalid version');
}

async function dispatch(path, body) {
  validateObject(body);
  if (path === '/anchor') {
    if (typeof body.content_hash !== 'string' || !HASH.test(body.content_hash)) throw new Error('invalid hash');
    return parseRecord(await contract.submitTransaction('Anchor', body.object_type,
      body.object_id, String(body.version), body.content_hash));
  }
  if (path === '/verify') {
    return parseRecord(await contract.evaluateTransaction('Verify', body.object_type,
      body.object_id, String(body.version)));
  }
  if (path === '/transition') {
    if (!['revoke', 'supersede'].includes(body.action)) throw new Error('invalid transition');
    return parseRecord(await contract.submitTransaction('Transition', body.object_type,
      body.object_id, String(body.version), body.action,
      body.superseded_by_version == null ? '' : String(body.superseded_by_version)));
  }
  return null;
}

function authorized(request) {
  const supplied = Buffer.from(request.headers['x-gateway-token'] || '');
  const expected = Buffer.from(token);
  return supplied.length === expected.length && crypto.timingSafeEqual(supplied, expected);
}

const server = http.createServer(async (request, response) => {
  response.setHeader('Content-Type', 'application/json');
  response.setHeader('Cache-Control', 'no-store');
  if (request.method === 'GET' && request.url === '/health') {
    response.writeHead(200).end('{"status":"ok"}');
    return;
  }
  if (request.method !== 'POST' || !['/anchor', '/verify', '/transition'].includes(request.url)) {
    response.writeHead(404).end('{"error":"not_found"}');
    return;
  }
  if (!authorized(request)) {
    response.writeHead(403).end('{"error":"forbidden"}');
    return;
  }
  let data = '';
  request.setEncoding('utf8');
  request.on('data', (chunk) => {
    data += chunk;
    if (data.length > 4096) request.destroy();
  });
  request.on('end', async () => {
    try {
      const result = await dispatch(request.url, JSON.parse(data));
      if (!result || typeof result !== 'object' || typeof result.transaction_id !== 'string' && result.exists !== false) {
        throw new Error('invalid ledger response');
      }
      response.writeHead(200).end(JSON.stringify(result));
    } catch (_error) {
      // Fabric error bodies can include peer, endorsement, or certificate details.
      response.writeHead(503).end('{"error":"ledger_unavailable_or_rejected"}');
    }
  });
});

server.listen(Number(process.env.PORT || 8080), '0.0.0.0');
function shutdown() {
  server.close(() => {
    gateway.close();
    client.close();
  });
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
