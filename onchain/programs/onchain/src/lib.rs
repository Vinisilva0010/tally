//! Tally: tamper-evident attestation of carbon credit audit runs.
//!
//! The analysis itself happens off chain over public registry files. What
//! lives here is the commitment: which files were analysed, what the
//! result was, and who published it, in a record that cannot be rewritten
//! afterwards.
//!
//! That property is the point. The parties whose data is being audited are
//! the registries themselves, so storing audit results in any database a
//! single operator controls would ask readers to trust exactly the kind of
//! party the tool exists to check. An append-only account, seeded by
//! dataset version and sealed when complete, lets anyone verify the result
//! independently and makes a silent revision impossible.

pub mod constants;
pub mod error;
pub mod instructions;
pub mod state;

use anchor_lang::prelude::*;

pub use constants::*;
pub use instructions::*;
pub use state::*;

declare_id!("2DNtSVqoQPgrZz17C6zTEKt3WUqgVJo1vxxkYLCBM29e");

#[program]
pub mod onchain {
    use super::*;

    #[allow(clippy::too_many_arguments)]
    pub fn create_run(
        ctx: Context<CreateRun>,
        dataset_version: [u8; VERSION_LEN],
        aggregate_sha256: [u8; 32],
        registry_sha256: [u8; 32],
        merkle_root: [u8; 32],
        project_count: u32,
        finding_count: u32,
        credits_milli: u64,
    ) -> Result<()> {
        crate::instructions::create_run::handle_create_run(
            ctx, dataset_version, aggregate_sha256, registry_sha256,
            merkle_root, project_count, finding_count, credits_milli,
        )
    }

    #[allow(clippy::too_many_arguments)]
    pub fn add_finding(
        ctx: Context<AddFinding>,
        index: u32,
        rule: [u8; RULE_LEN],
        severity: u8,
        subjects: [u8; SUBJECTS_LEN],
        country: [u8; COUNTRY_LEN],
        credits_milli: u64,
        leaf_hash: [u8; 32],
    ) -> Result<()> {
        crate::instructions::add_finding::handle_add_finding(
            ctx, index, rule, severity, subjects, country, credits_milli,
            leaf_hash,
        )
    }

    pub fn freeze_run(ctx: Context<FreezeRun>) -> Result<()> {
        crate::instructions::freeze_run::handle_freeze_run(ctx)
    }
}
