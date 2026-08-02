# dhybrid-agent bash completion
# usage: source scripts/completions.bash  (atau otomatis via installer)

_dhybrid_completions() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "repl run tokens resume sessions skills doctor self-update --model --cwd --config --yes --help --version --list-presets" -- "$cur") )
    elif [[ "$prev" == "--model" || "$prev" == "-m" ]]; then
        COMPREPLY=( $(compgen -W "$(dhybrid --list-presets 2>/dev/null)" -- "$cur") )
    fi
}
complete -F _dhybrid_completions dhybrid
