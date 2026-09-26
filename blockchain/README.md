# Local Hyperledger Fabric provenance

The ledger is an integrity/provenance layer. PostgreSQL remains the operational source of truth. Fabric stores a random internal UUID, object type, version, canonical SHA-256 digest, ledger timestamps, transaction IDs, and current lifecycle status. It never receives names, emails, student IDs, uploaded files, document text, report contents, prompts, or contact details. A digest proves only that a matching representation was anchored; it does not establish legal correctness, applicability, enforceability, or factual accuracy.

## Prerequisites

- Windows with Git for Windows (Git Bash) and Docker Desktop, or Linux with Docker Compose. WSL2 Ubuntu is also supported when Docker Desktop WSL integration is enabled.
- Git, curl, jq, and Node.js 20 or later (Node is used to install the private Gateway service packages).
- Hyperledger Fabric binaries and images are downloaded by the setup script on first use. Defaults are Fabric 2.5.16, Fabric CA 1.5.17, and the pinned `fabric-samples` source commit `9465222a37a54873e4c3e74431cd3d169e21b01b`. Set `FABRIC_VERSION` / `CA_VERSION` / `FABRIC_SAMPLES_COMMIT` together to select another compatible pair.
- Allow Docker to download the Fabric peer, orderer, CA, and tools images. The local test network uses two organization peers and one orderer.

## Start, deploy, and stop

On Windows, run the commands in Git Bash from the repository. On Linux or WSL2 with Docker integration, run them from the repository root. The upstream checkout and platform-specific Fabric tools live in ignored `blockchain/fabric-samples/` by default on Windows and `$HOME/.lexaware-fabric/` on Linux/WSL:

```sh
bash blockchain/scripts/fabric.sh up
bash blockchain/scripts/fabric.sh deploy
```

`up` obtains the official Fabric test-network sample if absent, downloads the selected Fabric tools/images, starts the certificate authorities, peers, and orderer, creates the `provenance` channel, and enrolls a dedicated Org1 client identity with the `provenance.writer=true` enrollment attribute. The local writer secret is generated once into the ignored `blockchain/.generated/writer-secret` file; set `FABRIC_WRITER_SECRET` before `up` to provide a different local secret. Do not reuse it outside this disposable network.

`deploy` installs the JavaScript provenance chaincode on both organizations and commits it to the channel. The contract accepts writes only from `Org1MSP` identities carrying the writer attribute. Org2, identities without the attribute, and the ordinary API/database credentials cannot write to the ledger.

Set a random `FABRIC_GATEWAY_TOKEN` in the ignored root `.env` (never commit it), then start the isolated Gateway service:

```sh
FABRIC_NETWORK_DIR="$(cygpath -m blockchain/fabric-samples/test-network/organizations)" \
  docker compose --env-file .env -f blockchain/gateway/docker-compose.yml \
  up --build -d
```

Set `BLOCKCHAIN_ENABLED=true` and `FABRIC_GATEWAY_TOKEN` in the local root `.env`, then restart the API and provenance-worker process/container so both read the same private token. `FABRIC_GATEWAY_ENDPOINT` defaults to `http://localhost:8080` for host processes; the Compose worker uses the separate `FABRIC_GATEWAY_DOCKER_ENDPOINT` default at `http://host.docker.internal:8080`. The Gateway port binds to loopback only; its API requires the shared private token. Fabric authorization is independently enforced inside chaincode using the enrolled client certificate attributes.

Use `bash blockchain/scripts/fabric.sh down` to stop the test network. This preserves local Fabric state/artifacts. `bash blockchain/scripts/fabric.sh reset` removes the disposable test network/channel state, recreates the network and writer identity, and deploys chaincode again. Stop the Gateway with:

```sh
docker compose --env-file .env -f blockchain/gateway/docker-compose.yml down
```

Generated Fabric source checkout, binaries, certificates, keys, and packages live in ignored `blockchain/.generated/` or WSL's `$HOME/.lexaware-fabric/`. Keep the dedicated writer key material local and readable only by the Gateway process.

## Application lifecycle

Publication of a governed knowledge version, verification of an eligible help resource, and creation of an analysis-report manifest insert an idempotent PostgreSQL outbox row in the same transaction as the existing event. The outbox contains only the supported object UUID, version, SHA-256 digest, requested actor reference, retry metadata, and state. Its database row is authoritative for application status. The provenance worker handles requests asynchronously; an unavailable or disabled Fabric Gateway leaves the row `pending` with a bounded failure code and exponential retry time. Article publication, help verification, report creation, student reads, and document deletion do not wait on Fabric.

Knowledge hashes use `knowledge-version-v1` canonical JSON containing the published governed content and applicability fields. Report hashes reuse F8's exact canonical JSON serialization (UTF-8, sorted object keys, compact separators, no ASCII escaping); the report manifest is never sent to Fabric. Help-resource hashes use `verified-help-resource-v1` and deliberately exclude names, description, phone, email, and contact URL; that proof attests to the verified classification/source/scope/timing projection and does not claim to prove contact-detail integrity.

The chaincode `Anchor` operation is idempotent for the same object/version/hash and rejects conflicting digests. New versions must advance the highest existing version after it has been revoked or superseded. `Verify` returns a safe negative result for unknown keys. `Transition` allows only `anchored -> revoked|superseded`, is idempotent for the same target state, and preserves the digest and original anchoring transaction while recording the transition transaction/time. The authenticated `GET /api/v1/provenance/{anchor_id}` API checks current governed visibility for article/help records and document ownership for private report records before querying Fabric. Owners can see pending state and safe retry metadata; gateway internals and content are never returned.

For ambiguous transaction timeouts, the worker queries the ledger before resubmitting. A committed matching record is accepted; a different digest remains pending with a safe conflict code. A network outage can therefore delay provenance but cannot fabricate an anchored state or block the core workflow.

## Tests and limitations

Run chaincode contract tests with `npm test --prefix blockchain/chaincode/provenance`. The Fabric test network is a single-machine development/test topology using the official sample configuration, not a production deployment. Local peer state can be reset; there is no production certificate rotation, external ordering organization, privacy collection, disaster recovery, or independent organizational governance. A compromised authorized writer identity can make otherwise authorized ledger requests until that credential is revoked. Resource hashes intentionally omit contact/name/description fields. An anchor is an integrity timestamp, not an endorsement of legal quality.
