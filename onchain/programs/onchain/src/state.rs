use anchor_lang::prelude::*;

use crate::constants::*;

/// One audit run over one version of the public registry data.
///
/// The account commits to the inputs before it commits to the result:
/// both source checksums are recorded alongside the Merkle root, so a
/// reader can fetch the same files, confirm they hash to the same values,
/// rerun the analysis and compare roots. Without the input hashes the
/// root would prove only that someone published something.
#[account]
#[derive(InitSpace)]
pub struct AuditRun {
    /// Dataset version of the Berkeley database, e.g. "v2026-08".
    pub dataset_version: [u8; VERSION_LEN],
    /// SHA-256 of the aggregate workbook.
    pub aggregate_sha256: [u8; 32],
    /// SHA-256 of the raw registry workbook.
    pub registry_sha256: [u8; 32],
    /// Merkle root over all findings, in their canonical order.
    pub merkle_root: [u8; 32],
    /// Projects analysed.
    pub project_count: u32,
    /// Findings the root commits to.
    pub finding_count: u32,
    /// Findings actually written so far.
    pub findings_written: u32,
    /// Credits evidenced as double counted, in thousandths.
    pub credits_milli: u64,
    pub created_at: i64,
    pub authority: Pubkey,
    /// Once true, nothing in this run can change or be added.
    pub frozen: bool,
    pub bump: u8,
}

/// One finding belonging to a run.
///
/// The leaf hash is what ties this account to the committed root: a
/// reader rebuilds the leaf from the public data and checks it against
/// the Merkle proof. The human-readable fields are there so the account
/// is useful on its own, not so they are trusted.
#[account]
#[derive(InitSpace)]
pub struct Finding {
    pub run: Pubkey,
    pub index: u32,
    /// Rule identifier, e.g. "R1".
    pub rule: [u8; RULE_LEN],
    /// 0 for context rules, 1 to 3 for evidenced double counting.
    pub severity: u8,
    /// Project identifiers, pipe separated.
    pub subjects: [u8; SUBJECTS_LEN],
    pub country: [u8; COUNTRY_LEN],
    pub credits_milli: u64,
    /// SHA-256 of 0x00 || canonical payload.
    pub leaf_hash: [u8; 32],
    pub created_at: i64,
    pub bump: u8,
}
