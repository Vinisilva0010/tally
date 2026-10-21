//! Attestation behaviour, including every rule the program enforces.
//!
//! The negative cases matter more than the happy path here. An audit log
//! whose entries can be rewritten, reordered or sealed half-finished is
//! not an audit log, so each of those is asserted to fail rather than
//! merely assumed not to happen.

use {
    anchor_lang::{
        prelude::Pubkey,
        solana_program::{instruction::Instruction, system_program},
        AccountDeserialize, InstructionData, ToAccountMetas,
    },
    litesvm::LiteSVM,
    onchain::constants::*,
    solana_keypair::Keypair,
    solana_message::{Message, VersionedMessage},
    solana_signer::Signer,
    solana_transaction::versioned::VersionedTransaction,
};

const VERSION: &[u8; VERSION_LEN] = b"v2026-08\0\0\0\0\0\0\0\0";

fn padded<const N: usize>(text: &str) -> [u8; N] {
    let mut out = [0u8; N];
    let bytes = text.as_bytes();
    let len = bytes.len().min(N);
    out[..len].copy_from_slice(&bytes[..len]);
    out
}

struct Harness {
    svm: LiteSVM,
    program_id: Pubkey,
    authority: Keypair,
    run: Pubkey,
}

impl Harness {
    fn new() -> Self {
        let program_id = onchain::id();
        let mut svm = LiteSVM::new();
        let bytes = include_bytes!(concat!(
            env!("CARGO_TARGET_TMPDIR"),
            "/../deploy/onchain.so"
        ));
        svm.add_program(program_id, bytes).unwrap();

        let authority = Keypair::new();
        svm.airdrop(&authority.pubkey(), 10_000_000_000).unwrap();
        let run = Pubkey::find_program_address(
            &[RUN_SEED, VERSION.as_ref()],
            &program_id,
        )
        .0;
        Self { svm, program_id, authority, run }
    }

    fn send(&mut self, ix: Instruction, signer: &Keypair) -> bool {
        let blockhash = self.svm.latest_blockhash();
        let msg = Message::new_with_blockhash(
            &[ix], Some(&signer.pubkey()), &blockhash,
        );
        let tx = VersionedTransaction::try_new(
            VersionedMessage::Legacy(msg), &[signer],
        )
        .unwrap();
        self.svm.send_transaction(tx).is_ok()
    }

    fn create_run(&mut self, finding_count: u32) -> bool {
        let ix = Instruction::new_with_bytes(
            self.program_id,
            &onchain::instruction::CreateRun {
                dataset_version: *VERSION,
                aggregate_sha256: [1u8; 32],
                registry_sha256: [2u8; 32],
                merkle_root: [3u8; 32],
                project_count: 11_856,
                finding_count,
                credits_milli: 361_903_000,
            }
            .data(),
            onchain::accounts::CreateRun {
                authority: self.authority.pubkey(),
                run: self.run,
                system_program: system_program::ID,
            }
            .to_account_metas(None),
        );
        let authority = self.authority.insecure_clone();
        self.send(ix, &authority)
    }

    fn finding_pda(&self, index: u32) -> Pubkey {
        Pubkey::find_program_address(
            &[FINDING_SEED, self.run.as_ref(), &index.to_le_bytes()],
            &self.program_id,
        )
        .0
    }

    fn add_finding_as(&mut self, index: u32, signer: &Keypair) -> bool {
        let ix = Instruction::new_with_bytes(
            self.program_id,
            &onchain::instruction::AddFinding {
                index,
                rule: padded::<RULE_LEN>("R1"),
                severity: 3,
                subjects: padded::<SUBJECTS_LEN>("ACR0931|CAR2112"),
                country: padded::<COUNTRY_LEN>("United States"),
                credits_milli: 147_508_000,
                leaf_hash: [9u8; 32],
            }
            .data(),
            onchain::accounts::AddFinding {
                authority: signer.pubkey(),
                run: self.run,
                finding: self.finding_pda(index),
                system_program: system_program::ID,
            }
            .to_account_metas(None),
        );
        self.send(ix, signer)
    }

    fn add_finding(&mut self, index: u32) -> bool {
        let authority = self.authority.insecure_clone();
        self.add_finding_as(index, &authority)
    }

    fn freeze(&mut self) -> bool {
        let ix = Instruction::new_with_bytes(
            self.program_id,
            &onchain::instruction::FreezeRun {}.data(),
            onchain::accounts::FreezeRun {
                authority: self.authority.pubkey(),
                run: self.run,
            }
            .to_account_metas(None),
        );
        let authority = self.authority.insecure_clone();
        self.send(ix, &authority)
    }

    fn run_state(&self) -> onchain::state::AuditRun {
        let account = self.svm.get_account(&self.run).unwrap();
        let mut data: &[u8] = &account.data;
        onchain::state::AuditRun::try_deserialize(&mut data).unwrap()
    }
}

#[test]
fn a_complete_run_can_be_created_filled_and_sealed() {
    let mut h = Harness::new();
    assert!(h.create_run(2));

    let state = h.run_state();
    assert_eq!(state.merkle_root, [3u8; 32]);
    assert_eq!(state.aggregate_sha256, [1u8; 32]);
    assert_eq!(state.finding_count, 2);
    assert_eq!(state.findings_written, 0);
    assert!(!state.frozen);

    assert!(h.add_finding(0));
    assert!(h.add_finding(1));
    assert_eq!(h.run_state().findings_written, 2);

    assert!(h.freeze());
    assert!(h.run_state().frozen);
}

#[test]
fn a_sealed_run_accepts_nothing_further() {
    let mut h = Harness::new();
    assert!(h.create_run(1));
    assert!(h.add_finding(0));
    assert!(h.freeze());

    assert!(!h.add_finding(1), "a frozen run must reject new findings");
    assert!(!h.freeze(), "a frozen run must not be frozen twice");
}

#[test]
fn findings_must_arrive_in_order() {
    let mut h = Harness::new();
    assert!(h.create_run(3));
    assert!(!h.add_finding(1), "index 1 before index 0 must fail");
    assert!(h.add_finding(0));
    assert!(!h.add_finding(2), "index 2 before index 1 must fail");
}

#[test]
fn more_findings_than_declared_are_refused() {
    let mut h = Harness::new();
    assert!(h.create_run(1));
    assert!(h.add_finding(0));
    assert!(!h.add_finding(1), "run declared one finding");
}

#[test]
fn an_incomplete_run_cannot_be_sealed() {
    let mut h = Harness::new();
    assert!(h.create_run(3));
    assert!(h.add_finding(0));
    assert!(!h.freeze(), "one of three findings written");
    assert!(!h.run_state().frozen);
}

#[test]
fn only_the_authority_may_write() {
    let mut h = Harness::new();
    assert!(h.create_run(2));

    let intruder = Keypair::new();
    h.svm.airdrop(&intruder.pubkey(), 10_000_000_000).unwrap();
    assert!(!h.add_finding_as(0, &intruder), "wrong signer must be rejected");
    assert_eq!(h.run_state().findings_written, 0);
}

#[test]
fn the_same_dataset_version_cannot_be_attested_twice() {
    let mut h = Harness::new();
    assert!(h.create_run(1));
    assert!(!h.create_run(1), "the run PDA is seeded by dataset version");
}

#[test]
fn a_run_must_declare_at_least_one_finding() {
    let mut h = Harness::new();
    assert!(!h.create_run(0));
}
