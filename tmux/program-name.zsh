# Event-driven pane labels. Never wrap Codex or change how it is launched.
_tmux_codex_preexec() {
  emulate -L zsh
  setopt extendedglob
  [[ -n $TMUX && -n $TMUX_PANE ]] || return 0
  local -a words
  words=( ${(z)1} )
  # Remove shell quoting without evaluating substitutions in the command.
  words=( "${(@Q)words}" )
  while (( $#words )) && [[ $words[1] == (command|exec|env|noglob) || $words[1] == [A-Za-z_][A-Za-z0-9_]#=* ]]; do
    shift words
  done
  local executable=${words[1]:t} entry=${words[2]:t}
  if [[ $executable == codex ||
        ( $executable == (node|nodejs) && $entry == (codex|codex.js|codex.mjs) ) ]] &&
      [[ ${words[-1]} != '&' ]]; then
    command tmux set-option -p -t "$TMUX_PANE" @codex_program codex
  else
    command tmux set-option -pu -t "$TMUX_PANE" @codex_program
  fi
}

_tmux_codex_precmd() {
  [[ -n $TMUX && -n $TMUX_PANE ]] || return 0
  command tmux set-option -pu -t "$TMUX_PANE" @codex_program
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec _tmux_codex_preexec
add-zsh-hook precmd _tmux_codex_precmd
