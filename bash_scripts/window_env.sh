# window_env.sh - resolve the run window and put it in the environment.
#
# Sourced by the driver scripts; not meant to be run on its own. It reads the
# values from bash_scripts/window.conf (the only file you edit), lets a driver
# override them, and exports what the python scripts read:
#
#   forecast mode -> NDAYS_BACK, NDAYS_FWD   (START_DATE/END_DATE unset)
#   hindcast mode -> START_DATE, END_DATE    (NDAYS_BACK/NDAYS_FWD unset)
#
# Precedence (the same order python/run_window.py uses):
#   1. WIN_BACK / WIN_FWD   a driver's -b/-f option; forces a rolling window
#   2. the environment      NDAYS_BACK/NDAYS_FWD or START_DATE/END_DATE already
#                           exported by a parent job (e.g. a forecast cycle)
#   3. bash_scripts/window.conf
#
# A driver may set these BEFORE sourcing this file:
#   WIN_BACK   override NDAYS_BACK (e.g. from -b); forces forecast mode
#   WIN_FWD    override NDAYS_FWD  (e.g. from -f); forces forecast mode
#
# After sourcing, these are available for messages and checks:
#   WIN_START, WIN_END       the window as YYYY-MM-DD
#   WIN_BACK_DAYS, WIN_FWD_DAYS   whole days before/after today
#   MAX_DAYS_FWD_MET         from window.conf
#   window_describe          prints a one-line summary

WINDOW_CONF="${WINDOW_CONF:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/window.conf}"
[[ -f "$WINDOW_CONF" ]] || { echo "ERROR: window config not found: $WINDOW_CONF" >&2; return 1 2>/dev/null || exit 1; }

# Whatever is already in the environment wins over the file
_win_env_back="${NDAYS_BACK:-}"
_win_env_fwd="${NDAYS_FWD:-}"
_win_env_start="${START_DATE:-}"
_win_env_end="${END_DATE:-}"
_win_env_model="${ECMWF_MODEL:-}"
_win_env_resol="${ECMWF_RESOL:-}"

# shellcheck disable=SC1090
source "$WINDOW_CONF"

[[ -n "$_win_env_back" ]] && NDAYS_BACK="$_win_env_back"
[[ -n "$_win_env_fwd"  ]] && NDAYS_FWD="$_win_env_fwd"
[[ -n "$_win_env_model" ]] && ECMWF_MODEL="$_win_env_model"
[[ -n "$_win_env_resol" ]] && ECMWF_RESOL="$_win_env_resol"
if [[ -n "$_win_env_start" ]]; then
    # fixed dates from the environment: they win over the file's NDAYS_*
    START_DATE="$_win_env_start"
    [[ -n "$_win_env_end" ]] && END_DATE="$_win_env_end"
elif [[ -n "$_win_env_back" || -n "$_win_env_fwd" ]]; then
    # day counts from the environment mean a rolling window
    START_DATE=""
    END_DATE=""
fi

_win_is_int() { [[ "$1" =~ ^-?[0-9]+$ ]]; }

# A -b/-f override on the command line wins and means a rolling forecast window
if [[ -n "${WIN_BACK:-}" || -n "${WIN_FWD:-}" ]]; then
    [[ -n "${WIN_BACK:-}" ]] && NDAYS_BACK="$WIN_BACK"
    [[ -n "${WIN_FWD:-}"  ]] && NDAYS_FWD="$WIN_FWD"
    START_DATE=""
    END_DATE=""
fi

_win_today=$(date -d "$(date +%F)" +%s)

if [[ -n "${START_DATE:-}" ]]; then
    # ---- hindcast (fixed dates) ----
    [[ -n "${END_DATE:-}" ]] || { echo "ERROR: END_DATE must be set with START_DATE in $WINDOW_CONF" >&2; exit 1; }
    WIN_START="$START_DATE"
    WIN_END="$END_DATE"
    WIN_BACK_DAYS=$(( (_win_today - $(date -d "$START_DATE" +%s)) / 86400 ))
    WIN_FWD_DAYS=$((  ($(date -d "$END_DATE" +%s) - _win_today) / 86400 ))
    export START_DATE END_DATE
    unset NDAYS_BACK NDAYS_FWD
    WIN_MODE=hindcast
else
    # ---- forecast (rolling, relative to today) ----
    : "${NDAYS_BACK:?NDAYS_BACK not set in $WINDOW_CONF}"
    : "${NDAYS_FWD:?NDAYS_FWD not set in $WINDOW_CONF}"
    if ! _win_is_int "$NDAYS_BACK" || ! _win_is_int "$NDAYS_FWD"; then
        echo "ERROR: NDAYS_BACK/NDAYS_FWD must be whole numbers (got '$NDAYS_BACK' and '$NDAYS_FWD')" >&2
        exit 1
    fi
    (( NDAYS_BACK >= 0 && NDAYS_FWD >= 0 )) || { echo "ERROR: NDAYS_BACK/NDAYS_FWD must not be negative" >&2; exit 1; }
    (( NDAYS_BACK + NDAYS_FWD >= 1 )) || { echo "ERROR: the window must be at least 1 day" >&2; exit 1; }
    WIN_START=$(date -d "-${NDAYS_BACK} days" +%F)
    WIN_END=$(date -d "+${NDAYS_FWD} days" +%F)
    WIN_BACK_DAYS="$NDAYS_BACK"
    WIN_FWD_DAYS="$NDAYS_FWD"
    export NDAYS_BACK NDAYS_FWD
    unset START_DATE END_DATE
    WIN_MODE=forecast
fi

if [[ -z "${WIN_END:-}" || -z "${WIN_START:-}" ]]; then
    echo "ERROR: could not resolve the window from $WINDOW_CONF" >&2; exit 1
fi
MAX_DAYS_FWD_MET="${MAX_DAYS_FWD_MET:-5}"
ECMWF_MODEL="${ECMWF_MODEL:-ifs}"
ECMWF_RESOL="${ECMWF_RESOL:-0p25}"
export ECMWF_MODEL ECMWF_RESOL

ecmwf_describe() {
    echo "ECMWF open data: model ${ECMWF_MODEL}, grid ${ECMWF_RESOL}"
}

window_describe() {
    if [[ "$WIN_MODE" == hindcast ]]; then
        echo "fixed window: ${WIN_START} 00:00 to ${WIN_END} 00:00 (dates set, not counted from today)"
    else
        echo "forecast window: ${WIN_START} 00:00 to ${WIN_END} 00:00" \
             "(${WIN_BACK_DAYS} day(s) back, ${WIN_FWD_DAYS} forward; from ${WINDOW_CONF})"
    fi
}
