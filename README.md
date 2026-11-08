# Lazarus Keeper Node Daemon

[![CI](https://github.com/LazarusProtocol/keeper/actions/workflows/ci.yml/badge.svg)](https://github.com/LazarusProtocol/keeper/actions)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)](https://github.com/LazarusProtocol/keeper/pkgs/container/keeper-daemon)

Autonomous, permissionless state-warming keeper node daemon for the **Lazarus Protocol** on Stellar (Soroban). Monitors expiring storage keys for registered protocols, broadcasts batched `ExtendFootprintTTLOp` transactions, acquires cryptographic `BumpVoucher` attestations, and settles rewards on-chain via `record_bump_batch`.

---

## What Keepers Do

1. **Poll Expiring State:** Polls the Lazarus Indexer (`/api/v1/keys/expiring`) every ledger (~5 seconds).
2. **Cohort Sharding:** Evaluates `sha256(keeper_pk : key_hash : epoch) % 5 == 0` to minimize collision waste with other keepers across 100-ledger epochs.
3. **Emergency Bypass:** When a key's remaining TTL drops below `2,000 ledgers` (~2.7 hours), cohort sharding is bypassed immediately to prevent archival.
4. **Footprint Packing:** Packs up to **100 storage keys** into a single transaction footprint, maximizing XLM gas efficiency.
5. **Attestation & Settlement:** Sends the transaction hash to the Attestation Engine, buffers up to **10 vouchers**, and submits `record_bump_batch` to `LazarusVault` on Stellar to claim USDC bounties.

---

## Quickstart

### Prerequisites
* Docker (or Python 3.11+ if running from source)
* A funded Stellar Testnet (or Mainnet) account (`S...` secret key) with XLM for base transaction fees.

### Option 1: Run the Prebuilt Container Package (Fastest)
Pull and run the official image directly from GitHub Container Registry without cloning the repository:

```bash
docker pull ghcr.io/lazarusprotocol/keeper-daemon:latest

docker run -d \
  --name lazarus-keeper \
  --restart unless-stopped \
  -e LAZARUS_KEEPER_SECRET="S...YOUR_STELLAR_SECRET_KEY" \
  -e LAZARUS_INDEXER_API_URL="https://api.lazarusprotocol.online" \
  -e LAZARUS_RPC_URL="https://soroban-testnet.stellar.org" \
  -e LAZARUS_VAULT_CONTRACT_ID="CCWAH7BVPGYOEBPRFWPZIONBYUCCQH7OARGZLOD6ZV66SOAFBVA2DHD5" \
  -e LAZARUS_BUFFER_FLUSH_INTERVAL="600" \
  ghcr.io/lazarusprotocol/keeper-daemon:latest

# View live keeper logs
docker logs -f lazarus-keeper
```

### Option 2: Run with Docker Compose
```bash
git clone https://github.com/LazarusProtocol/keeper.git
cd keeper

# Copy environment template and fill in your Stellar secret
cp .env.example .env
nano .env

# Run daemon in background
docker compose up -d
```

### Option 3: Run from Source
```bash
git clone https://github.com/LazarusProtocol/keeper.git
cd keeper

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run a single keeper pass in dev-stub mode
python3 -m keeper.cli --once --dev-stub

# Run continuous keeper loop
python3 -m keeper.cli --interval 5.0
```

---

## Configuration (`.env`)

| Variable | Description |
| :--- | :--- |
| `LAZARUS_KEEPER_SECRET` | Your Stellar secret key (`S...`) used to sign `ExtendFootprintTTLOp` and claim bounties |
| `LAZARUS_INDEXER_API_URL` | Lazarus Indexer API endpoint (default: `https://api.lazarusprotocol.online`) |
| `LAZARUS_RPC_URL` | Stellar Soroban RPC endpoint (default: `https://soroban-testnet.stellar.org`) |
| `LAZARUS_NETWORK_PASSPHRASE` | Network passphrase (`Test SDF Network ; September 2015` or `Public Global Stellar Network ; September 2015`) |
| `LAZARUS_VAULT_CONTRACT_ID` | Deployed `LazarusVault` contract ID |
| `LAZARUS_BUFFER_FLUSH_INTERVAL` | Maximum voucher retention time before flushing to vault (seconds, default: `600`) |
| `LAZARUS_DEV_STUB_MODE` | Set `false` for live execution; `true` for offline simulation |

---

## Testing
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

