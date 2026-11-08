from __future__ import annotations

import asyncio
import base64
import hashlib
import unittest
from typing import Any, Dict, Tuple

from keeper.daemon import (
    COHORT_MODULO,
    EMERGENCY_THRESHOLD,
    MAX_BATCH_SIZE,
    MAX_FOOTPRINT_KEYS,
    LazarusKeeperNode,
)


class MockSorobanRPCServer:
    def __init__(self) -> None:
        self.simulated_txs = []
        self.submitted_txs = []
        self.batch_calls = []

    async def get_latest_ledger(self) -> Dict[str, int]:
        return {"sequence": 500_000}

    async def load_account(self, public_key: str) -> Dict[str, Any]:
        return {"account_id": public_key, "sequence": 1001}

    async def simulate_transaction(self, pre_tx: Any) -> Dict[str, Any]:
        self.simulated_txs.append(pre_tx)
        return {"min_resource_fee": 14_500}

    async def submit_transaction(self, tx: Any) -> Dict[str, Any]:
        self.submitted_txs.append(tx)
        tx_hash = hashlib.sha256(str(len(self.submitted_txs)).encode()).hexdigest()
        return {"hash": tx_hash, "status": "SUCCESS"}

    async def submit_batch_contract_call(self, record: Dict[str, Any]) -> None:
        self.batch_calls.append(record)


class LazarusKeeperTestSuite(unittest.TestCase):
    def setUp(self) -> None:
        self.contract_id = "CCBLENDPOOLCONTRACT0000000000000000000000000000000000001"
        self.keeper_secret = "SBZ7T5X23Y7EXAMPLEKEEPERSECRETKEY00000000000000000000000"

    def test_deterministic_cohort_sharding_and_emergency_bypass(self) -> None:
        node = LazarusKeeperNode(
            keeper_secret=self.keeper_secret,
            indexer_api_url="http://localhost:8000",
            rpc_url="https://soroban-testnet.stellar.org",
            network_passphrase="Test SDF Network ; September 2015",
            dev_stub_mode=True,
        )

        # 1. Emergency Threshold Bypass: remaining_ledgers <= 2000 ALWAYS returns True
        for i in range(25):
            self.assertTrue(
                node.is_eligible_for_key(
                    key_hash=f"emergency_key_{i}",
                    current_ledger=500_000,
                    remaining_ledgers=EMERGENCY_THRESHOLD,
                )
            )
            self.assertTrue(
                node.is_eligible_for_key(
                    key_hash=f"emergency_key_{i}",
                    current_ledger=500_000,
                    remaining_ledgers=100,
                )
            )

        # 2. Normal Window: Sharded deterministically across cohorts modulo 5
        cohort_hits = 0
        samples = 100
        for i in range(samples):
            if node.is_eligible_for_key(
                key_hash=f"normal_key_{i}",
                current_ledger=500_000,
                remaining_ledgers=15_000,
            ):
                cohort_hits += 1

        self.assertGreater(cohort_hits, 0)
        self.assertLess(cohort_hits, samples)

    def test_keeper_buffer_accumulation_and_batch_redemption_loop(self) -> None:
        mock_rpc = MockSorobanRPCServer()
        node = LazarusKeeperNode(
            keeper_secret=self.keeper_secret,
            indexer_api_url="http://localhost:8000",
            rpc_url="https://soroban-testnet.stellar.org",
            network_passphrase="Test SDF Network ; September 2015",
            dev_stub_mode=True,
            server=mock_rpc,
        )

        async def scenario() -> None:
            # Extend 10 keys -> buffer hits MAX_BATCH_SIZE = 10 -> should_flush_buffer() is True
            for idx in range(10):
                key_xdr = base64.b64encode(f"ledger_key_{idx}".encode()).decode("ascii")
                await node.extend_state(
                    {
                        "contract_id": self.contract_id,
                        "key_hash": hashlib.sha256(key_xdr.encode()).hexdigest(),
                        "key_xdr": key_xdr,
                        "live_until_ledger_seq": 501_000,
                        "bump_target": 550_000,
                    }
                )

            self.assertEqual(len(node.voucher_buffer), 10)
            self.assertTrue(node.should_flush_buffer())

            flushed = await node.redeem_batch()
            self.assertEqual(flushed, 10)
            self.assertEqual(len(node.voucher_buffer), 0)
            self.assertEqual(len(mock_rpc.batch_calls), 1)
            self.assertEqual(
                mock_rpc.batch_calls[0]["entrypoint"], "record_bump_batch"
            )

        asyncio.run(scenario())

    def test_request_voucher_polling_202_to_200_and_safety_guard(self) -> None:
        attempts = 0

        async def mock_http_post(
            url: str, payload: Dict[str, Any]
        ) -> Tuple[int, Dict[str, Any]]:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                return 202, {"status": "pending_consensus"}
            return 200, {
                "voucher": {
                    "keeper": payload["keeper_address"],
                    "target_contract": payload["contract_id"],
                    "ledger_bumped": 550_000,
                    "bounty_amount": 1_000_000,
                    "nonce": 1,
                },
                "signature": "ab" * 64,
            }

        node = LazarusKeeperNode(
            keeper_secret=self.keeper_secret,
            indexer_api_url="http://localhost:8000",
            rpc_url="https://soroban-testnet.stellar.org",
            network_passphrase="Test SDF Network ; September 2015",
            dev_stub_mode=False,
            http_post_func=mock_http_post,
        )

        res = asyncio.run(
            node.request_voucher("tx_hash_123", self.contract_id, retry_delay=0.01)
        )
        self.assertEqual(attempts, 2)
        self.assertEqual(res["voucher"]["nonce"], 1)
        self.assertEqual(len(res["signature"]), 64)


if __name__ == "__main__":
    unittest.main()
