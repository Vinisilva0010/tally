use anchor_lang::prelude::*;

use crate::{constants::*, state::AuditRun, error::ErrorCode};

#[derive(Accounts)]
#[instruction(dataset_version: [u8; VERSION_LEN])]
pub struct CreateRun<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(
        init,
        payer = authority,
        space = 8 + AuditRun::INIT_SPACE,
        seeds = [RUN_SEED, dataset_version.as_ref()],
        bump
    )]
    pub run: Account<'info, AuditRun>,
    pub system_program: Program<'info, System>,
}

/// Open an attestation for one dataset version.
///
/// The seed is the dataset version, so one version can be attested once
/// per program. Re-running an analysis over the same files cannot quietly
/// replace an earlier result; a different result for the same inputs is a
/// contradiction that should be visible, not overwritten.
pub fn handle_create_run(
    ctx: Context<CreateRun>,
    dataset_version: [u8; VERSION_LEN],
    aggregate_sha256: [u8; 32],
    registry_sha256: [u8; 32],
    merkle_root: [u8; 32],
    project_count: u32,
    finding_count: u32,
    credits_milli: u64,
) -> Result<()> {
    require!(finding_count > 0, ErrorCode::EmptyRun);

    let run = &mut ctx.accounts.run;
    run.dataset_version = dataset_version;
    run.aggregate_sha256 = aggregate_sha256;
    run.registry_sha256 = registry_sha256;
    run.merkle_root = merkle_root;
    run.project_count = project_count;
    run.finding_count = finding_count;
    run.findings_written = 0;
    run.credits_milli = credits_milli;
    run.created_at = Clock::get()?.unix_timestamp;
    run.authority = ctx.accounts.authority.key();
    run.frozen = false;
    run.bump = ctx.bumps.run;

    msg!("audit run opened for {:?}", core::str::from_utf8(&dataset_version));
    Ok(())
}
