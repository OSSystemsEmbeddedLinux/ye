_ye() {
    local cur

    compreply() {
        COMPREPLY=( $(compgen -W "$(ye plumbing find $cur > /dev/null; cat ~/.ye/plumbing/find | xargs dirname | xargs -n1 basename)" -- "$cur") )
    }

    local command i
    for (( i=0; i < ${#COMP_WORDS[@]}-1; i++ )); do
        if [[ ${COMP_WORDS[i]} == @(cd|x|expand|e|edit|pv|pkg-view|pi|pkg-info) ]]; then
            command=${COMP_WORDS[i]}
        fi
    done

    cur=${COMP_WORDS[COMP_CWORD]}

    if [[ -n $command ]] && [[ -n $cur ]]; then
        if [[ $command = 'cd' ]]; then
            case "${COMP_WORDS[2]}" in
                wd|src)
                    compreply
                    return 0
                    ;;
                *)
                    return 0
            esac
        else
            compreply
        fi
    fi

    return 0
}

complete -F _ye ye
