use anchor_lang::prelude::*;

#[error_code]
pub enum ErrorCode {
    #[msg("This run is frozen and can no longer be modified")]
    RunFrozen,
    #[msg("Only the run authority may write to this run")]
    Unauthorized,
    #[msg("Finding index does not follow the findings already written")]
    UnexpectedFindingIndex,
    #[msg("More findings were submitted than the run declared")]
    TooManyFindings,
    #[msg("Cannot freeze a run whose findings are incomplete")]
    IncompleteRun,
    #[msg("A run must declare at least one finding")]
    EmptyRun,
}
