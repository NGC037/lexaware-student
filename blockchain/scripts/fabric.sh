#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BLOCKCHAIN="$ROOT/blockchain"
PLATFORM="$(uname -s)"
if [[ "$PLATFORM" == MINGW* || "$PLATFORM" == MSYS* ]]; then
  DEFAULT_SAMPLES="$BLOCKCHAIN/fabric-samples"
  PEER_BINARY="peer.exe"
else
  DEFAULT_SAMPLES="$HOME/.lexaware-fabric/fabric-samples"
  PEER_BINARY="peer"
fi
SAMPLES="${FABRIC_SAMPLES_DIR:-$DEFAULT_SAMPLES}"
TEST_NETWORK="$SAMPLES/test-network"
CHANNEL="${FABRIC_CHANNEL:-provenance}"
CHAINCODE="${FABRIC_CHAINCODE:-provenance}"
FABRIC_VERSION="${FABRIC_VERSION:-2.5.16}"
CA_VERSION="${CA_VERSION:-1.5.17}"
SAMPLES_COMMIT="${FABRIC_SAMPLES_COMMIT:-9465222a37a54873e4c3e74431cd3d169e21b01b}"
JQ_VERSION="1.8.1"

prepare() {
  mkdir -p "$BLOCKCHAIN/.generated/bin"
  if [[ "$PLATFORM" == MINGW* || "$PLATFORM" == MSYS* ]]; then
    export PATH="$BLOCKCHAIN/.generated/bin:$PATH"
    if ! command -v jq >/dev/null 2>&1; then
      if [[ ! -f "$BLOCKCHAIN/.generated/bin/jq.exe" ]]; then
        curl -fsSL "https://github.com/jqlang/jq/releases/download/jq-${JQ_VERSION}/jq-windows-amd64.exe" \
          -o "$BLOCKCHAIN/.generated/bin/jq.exe"
        chmod 700 "$BLOCKCHAIN/.generated/bin/jq.exe"
      fi
    fi
  fi
  local docker_exe=""
  if [[ "$PLATFORM" == MINGW* || "$PLATFORM" == MSYS* ]]; then
    docker_exe="$(command -v docker.exe || command -v docker || true)"
  else
    docker_exe="/mnt/c/Users/${USER}/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
  fi
  if [[ -n "$docker_exe" ]]; then
    cat > "$BLOCKCHAIN/.generated/bin/docker" <<EOF
#!/usr/bin/env bash
exec "$docker_exe" "\$@"
EOF
    chmod 700 "$BLOCKCHAIN/.generated/bin/docker"
    cat > "$BLOCKCHAIN/.generated/bin/docker-compose" <<EOF
#!/usr/bin/env bash
MSYS_NO_PATHCONV=1 exec "$docker_exe" compose "\$@"
EOF
    chmod 700 "$BLOCKCHAIN/.generated/bin/docker-compose"
    export PATH="$BLOCKCHAIN/.generated/bin:$PATH"
  fi
  if [[ ! -d "$TEST_NETWORK" ]]; then
    mkdir -p "$SAMPLES"
    git -C "$SAMPLES" init
    git -C "$SAMPLES" remote add origin https://github.com/hyperledger/fabric-samples.git
    git -C "$SAMPLES" fetch --depth 1 origin "$SAMPLES_COMMIT"
    git -C "$SAMPLES" checkout --detach FETCH_HEAD
  fi
  local installer="$BLOCKCHAIN/.generated/install-fabric.sh"
  local install_marker="$BLOCKCHAIN/.generated/fabric-${FABRIC_VERSION}-installed"
  if [[ ! -x "$SAMPLES/bin/$PEER_BINARY" || ! -f "$install_marker" ]]; then
    mkdir -p "$SAMPLES/bin" "$BLOCKCHAIN/.generated/bin"
    curl -fsSL "https://raw.githubusercontent.com/hyperledger/fabric/v${FABRIC_VERSION}/scripts/install-fabric.sh" \
      -o "$installer"
    chmod 700 "$installer"
    local components="docker"
    if [[ ! -x "$SAMPLES/bin/$PEER_BINARY" ]]; then
      components="binary docker"
    fi
    # shellcheck disable=SC2086
    (cd "$SAMPLES" && "$installer" --fabric-version "$FABRIC_VERSION" \
      --ca-version "$CA_VERSION" $components)
    touch "$install_marker"
  fi
  export PATH="$SAMPLES/bin:$PATH"
}

up() {
  prepare
  (cd "$TEST_NETWORK" && ./network.sh up -ca -c "$CHANNEL")
  enroll_writer
}

enroll_writer() {
  local org1="$TEST_NETWORK/organizations/peerOrganizations/org1.example.com"
  local ca_cert="$TEST_NETWORK/organizations/fabric-ca/org1/ca-cert.pem"
  local writer_home="$org1/users/provenance-writer@org1.example.com"
  local secret_file="$BLOCKCHAIN/.generated/writer-secret"
  mkdir -p "$(dirname "$secret_file")"
  if [[ -n "${FABRIC_WRITER_SECRET:-}" ]]; then
    local writer_secret="$FABRIC_WRITER_SECRET"
  elif [[ -f "$secret_file" ]]; then
    local writer_secret
    writer_secret="$(<"$secret_file")"
  else
    local writer_secret
    writer_secret="$(openssl rand -hex 24)"
    (umask 077 && printf '%s' "$writer_secret" > "$secret_file")
  fi
  if [[ -f "$org1/users/provenance-writer@org1.example.com/msp/signcerts/cert.pem" ]]; then
    return 0
  fi
  export PATH="$SAMPLES/bin:$PATH"
  export FABRIC_CA_CLIENT_HOME="$org1"
  fabric-ca-client register --caname ca-org1 --url https://localhost:7054 \
    --id.name provenance-writer --id.secret "$writer_secret" --id.type client \
    --id.affiliation org1.department1 --id.attrs 'provenance.writer=true:ecert' \
    --tls.certfiles "$ca_cert" || true
  mkdir -p "$writer_home"
  export FABRIC_CA_CLIENT_HOME="$writer_home"
  fabric-ca-client enroll --caname ca-org1 \
    --url "https://provenance-writer:${writer_secret}@localhost:7054" \
    -M "$writer_home/msp" --enrollment.attrs provenance.writer --tls.certfiles "$ca_cert"
}

deploy() {
  prepare
  (cd "$TEST_NETWORK" && ./network.sh deployCC -c "$CHANNEL" -ccn "$CHAINCODE" \
    -ccp "$BLOCKCHAIN/chaincode/provenance" -ccl javascript)
}

down() {
  if [[ -d "$TEST_NETWORK" ]]; then
    (cd "$TEST_NETWORK" && ./network.sh down -c "$CHANNEL")
  fi
}

reset() {
  down
  up
  deploy
}

case "${1:-help}" in
  up) up ;;
  enroll-writer) prepare; enroll_writer ;;
  deploy) deploy ;;
  down) down ;;
  reset) reset ;;
  *) echo "Usage: $0 {up|enroll-writer|deploy|down|reset}" >&2; exit 2 ;;
esac
