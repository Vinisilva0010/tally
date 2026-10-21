"""Publish an audit run to the Solana program.

The analysis is reproducible offline; this module is what makes the
result checkable by someone who does not trust the person who ran it.
It writes the input checksums and the Merkle root first, then each
finding, then seals the run.

Devnet refuses long bursts of transactions, so findings go one per
transaction with confirmation between them, and the whole operation is
resumable: the program records how many findings it has accepted, so a
run interrupted at finding 50 continues at 50 rather than starting over.

Instruction discriminators are read from the IDL the compiler produced
rather than derived here, and the RPC endpoint and wallet come from the
Solana CLI configuration, so no endpoint key is ever written into the
repository.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path

from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed

SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")

VERSION_LEN = 16
COUNTRY_LEN = 32
RULE_LEN = 4
SUBJECTS_LEN = 64

# Byte offsets into the AuditRun account, after the 8 byte discriminator.
OFFSET_PROJECT_COUNT = 8 + VERSION_LEN + 32 * 3
OFFSET_FINDING_COUNT = OFFSET_PROJECT_COUNT + 4
OFFSET_FINDINGS_WRITTEN = OFFSET_FINDING_COUNT + 4
OFFSET_FROZEN = OFFSET_FINDINGS_WRITTEN + 4 + 8 + 8 + 32


def pad(text: str, length: int) -> bytes:
    raw = text.encode("utf-8")[:length]
    return raw + b"\x00" * (length - len(raw))


@dataclass(frozen=True)
class CliConfig:
    rpc_url: str
    keypair_path: Path

    @classmethod
    def load(cls) -> "CliConfig":
        path = Path.home() / ".config/solana/cli/config.yml"
        if not path.exists():
            raise FileNotFoundError(f"Solana CLI config not found at {path}")
        values: dict[str, str] = {}
        for line in path.read_text().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                values[key.strip()] = value.strip().strip('"')
        url = values.get("json_rpc_url", "")
        keypair = values.get("keypair_path", "")
        if not url or not keypair:
            raise ValueError(f"incomplete Solana CLI config at {path}")
        return cls(url, Path(keypair).expanduser())

    def wallet(self) -> Keypair:
        data = json.loads(self.keypair_path.read_text())
        return Keypair.from_bytes(bytes(data))

    @property
    def safe_url(self) -> str:
        """The endpoint with any key query string removed, for printing."""
        return self.rpc_url.split("?")[0]


class Program:
    def __init__(self, idl_path: Path, cluster: CliConfig):
        idl = json.loads(idl_path.read_text())
        self.program_id = Pubkey.from_string(idl["address"])
        self.discriminators = {
            ix["name"]: bytes(ix["discriminator"]) for ix in idl["instructions"]
        }
        missing = {"create_run", "add_finding", "freeze_run"} - set(
            self.discriminators
        )
        if missing:
            raise ValueError(f"IDL is missing instructions: {sorted(missing)}")
        self.client = Client(cluster.rpc_url, commitment=Confirmed)
        self.payer = cluster.wallet()

    def run_pda(self, version: bytes) -> Pubkey:
        return Pubkey.find_program_address(
            [b"run", version], self.program_id
        )[0]

    def finding_pda(self, run: Pubkey, index: int) -> Pubkey:
        return Pubkey.find_program_address(
            [b"finding", bytes(run), struct.pack("<I", index)],
            self.program_id,
        )[0]

    def send(self, instruction: Instruction) -> str:
        blockhash = self.client.get_latest_blockhash().value.blockhash
        message = Message.new_with_blockhash(
            [instruction], self.payer.pubkey(), blockhash
        )
        tx = VersionedTransaction(message, [self.payer])
        signature = self.client.send_transaction(tx).value
        self.client.confirm_transaction(signature, commitment=Confirmed)
        return str(signature)

    def fetch_run(self, run: Pubkey) -> dict | None:
        info = self.client.get_account_info(run).value
        if info is None:
            return None
        data = bytes(info.data)
        return {
            "project_count": struct.unpack_from(
                "<I", data, OFFSET_PROJECT_COUNT)[0],
            "finding_count": struct.unpack_from(
                "<I", data, OFFSET_FINDING_COUNT)[0],
            "findings_written": struct.unpack_from(
                "<I", data, OFFSET_FINDINGS_WRITTEN)[0],
            "frozen": bool(data[OFFSET_FROZEN]),
            "merkle_root": data[8 + VERSION_LEN + 64: 8 + VERSION_LEN + 96],
        }

    def create_run(
        self, version: bytes, aggregate_sha: bytes, registry_sha: bytes,
        merkle_root: bytes, project_count: int, finding_count: int,
        credits_milli: int,
    ) -> str:
        run = self.run_pda(version)
        payload = (
            self.discriminators["create_run"]
            + version + aggregate_sha + registry_sha + merkle_root
            + struct.pack("<IIQ", project_count, finding_count, credits_milli)
        )
        ix = Instruction(
            self.program_id,
            payload,
            [
                AccountMeta(self.payer.pubkey(), is_signer=True, is_writable=True),
                AccountMeta(run, is_signer=False, is_writable=True),
                AccountMeta(SYSTEM_PROGRAM, is_signer=False, is_writable=False),
            ],
        )
        return self.send(ix)

    def add_finding(
        self, version: bytes, index: int, rule: str, severity: int,
        subjects: str, country: str, credits_milli: int, leaf_hash: bytes,
    ) -> str:
        run = self.run_pda(version)
        payload = (
            self.discriminators["add_finding"]
            + struct.pack("<I", index)
            + pad(rule, RULE_LEN)
            + struct.pack("<B", severity)
            + pad(subjects, SUBJECTS_LEN)
            + pad(country, COUNTRY_LEN)
            + struct.pack("<Q", credits_milli)
            + leaf_hash
        )
        ix = Instruction(
            self.program_id,
            payload,
            [
                AccountMeta(self.payer.pubkey(), is_signer=True, is_writable=True),
                AccountMeta(run, is_signer=False, is_writable=True),
                AccountMeta(
                    self.finding_pda(run, index), is_signer=False, is_writable=True
                ),
                AccountMeta(SYSTEM_PROGRAM, is_signer=False, is_writable=False),
            ],
        )
        return self.send(ix)

    def freeze_run(self, version: bytes) -> str:
        run = self.run_pda(version)
        ix = Instruction(
            self.program_id,
            self.discriminators["freeze_run"],
            [
                AccountMeta(self.payer.pubkey(), is_signer=True, is_writable=False),
                AccountMeta(run, is_signer=False, is_writable=True),
            ],
        )
        return self.send(ix)
