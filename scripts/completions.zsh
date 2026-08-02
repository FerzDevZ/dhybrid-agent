# dhybrid-agent zsh completion
# usage: autoload -Uz compinit && compinit && source scripts/completions.zsh
#        (atau otomatis via installer)

# reuse bash completion via bashcompinit
autoload -Uz bashcompinit
bashcompinit
source "${0:A:h}/completions.bash"
