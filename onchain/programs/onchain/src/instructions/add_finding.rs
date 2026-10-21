use anchor_lang::prelude::*;

use crate::{constants::*, error::ErrorCode, state::{AuditRun, Finding}};

#[derive(Accounts)]
#[instruction(index: u32)]
pub struct AddFinding<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(
        mut,
        seeds = [RUN_SEED, run.dataset_version.as_ref()],
        bump = run.bump,
        has_one = authority @ ErrorCode::Unauthorized,
    )]
    pub run: Account<'info, AuditRun>,
    #[account(
        init,
        payer = authority,
        space = 8 + Finding::INIT_SPACE,
        seeds = [FINDING_SEED, run.key().as_ref(), &index.to_le_bytes()],
        bump
    )]
    pub finding: Account<'info, Finding>,
    pub system_program: Program<'info, System>,
}

/// Append one finding to an open run.
///
/// Findings must arrive in order and may not exceed the count the run
/// declared. Both checks exist so the set of findings on chain is exactly
/// the set the Merkle root was built from: a gap or an extra would mean
/// the published root no longer describes what is stored.
pub fn handle_add_finding(
    ctx: Context<AddFinding>,
    index: u32,
    rule: [u8; RULE_LEN],
    severity: u8,
    subjects: [u8; SUBJECTS_LEN],
    country: [u8; COUNTRY_LEN],
    credits_milli: u64,
    leaf_hash: [u8; 32],
) -> Result<()> {
    let run = &mut ctx.accounts.run;
    require!(!run.frozen, ErrorCode::RunFrozen);
    require!(index == run.findings_written, ErrorCode::UnexpectedFindingIndex);
    require!(run.findings_written < run.finding_count, ErrorCode::TooManyFindings);

    let finding = &mut ctx.accounts.finding;
    finding.run = run.key();
    finding.index = index;
    finding.rule = rule;
    finding.severity = severity;
    finding.subjects = subjects;
    finding.country = country;
    finding.credits_milli = credits_milli;
    finding.leaf_hash = leaf_hash;
    finding.created_at = Clock::get()?.unix_timestamp;
    finding.bump = ctx.bumps.finding;

    run.findings_written = run.findings_written.saturating_add(1);
    Ok(())
}
