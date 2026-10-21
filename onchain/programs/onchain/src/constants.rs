use anchor_lang::prelude::*;

#[constant]
pub const RUN_SEED: &[u8] = b"run";

#[constant]
pub const FINDING_SEED: &[u8] = b"finding";

/// Dataset version strings are short and fixed ("v2026-08"), so they are
/// stored as a fixed byte array rather than a String. A variable-length
/// field would make the account size depend on caller input, which is both
/// harder to reason about and an avenue for inflating rent costs.
pub const VERSION_LEN: usize = 16;

/// ISO-ish country label, fixed width for the same reason.
pub const COUNTRY_LEN: usize = 32;

/// Rule identifier: "R1".."R4".
pub const RULE_LEN: usize = 4;

/// Project identifiers involved in one finding, e.g. "ACR0931|CAR2112".
pub const SUBJECTS_LEN: usize = 64;
