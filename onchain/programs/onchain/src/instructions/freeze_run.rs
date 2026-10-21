use anchor_lang::prelude::*;

use crate::{constants::*, error::ErrorCode, state::AuditRun};

#[derive(Accounts)]
pub struct FreezeRun<'info> {
    pub authority: Signer<'info>,
    #[account(
        mut,
        seeds = [RUN_SEED, run.dataset_version.as_ref()],
        bump = run.bump,
        has_one = authority @ ErrorCode::Unauthorized,
    )]
    pub run: Account<'info, AuditRun>,
}

/// Seal a run. Irreversible.
///
/// A run may only be sealed once every finding it declared has been
/// written. An attestation that promised fifteen findings and stored ten
/// would publish a root nobody can reproduce from what is on chain, so
/// the incomplete run simply never seals.
pub fn handle_freeze_run(ctx: Context<FreezeRun>) -> Result<()> {
    let run = &mut ctx.accounts.run;
    require!(!run.frozen, ErrorCode::RunFrozen);
    require!(
        run.findings_written == run.finding_count,
        ErrorCode::IncompleteRun
    );
    run.frozen = true;
    msg!("audit run sealed with {} findings", run.finding_count);
    Ok(())
}
