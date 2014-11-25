#! /bin/sh
# -*- shell-script -*-

### TODO

# g <args>
# grep <args>
#    Run 'repo grep <args>' under the current project.

# ll <pkg>
# loglist <pkg>
#      Show the log files for <pkg>

# l <pkg> <task expr>
# log <pkg> <task expr>
#    Show log.do_<task> for <task expr>

# lr <pkg> <task expr>
# logrun <pkg> <task expr>
#    Show run.do_<task> for <task expr>

# emacs fallback: zile, mg, vi


# No concurrent execution support
ytmp="/tmp/y.$USER"
mkdir -p $ytmp

yfind_tmp="$ytmp/yfind"
yfind_workdir_tmp="$ytmp/yfind-workdir"
yhistory="$ytmp/yhistory"
ypkg_find_tmp="$ytmp/ypkg_find"

MAX_HISTORY=20

usage() {
    cat <<EOF
`basename $0` <command> [<options>]

Commands:

f [-e] <expr>
find [-e] <expr>
    Locate paths that match the given expression <expr>.  <expr> is
    case insensitive and implicitly surrounded by '*'.  -e disables
    the implicit use of '*' around the given <expr>.

r
redisplay
    Redisplay the latest find results.

v [<n> | <path> ]
view [<n> | <path> ]
    View the file result of the last 'find' command.  If <n> or <path>
    is not provided, pick the first file.  If the PAGER environment
    variable is not set, it will fall back to "nl -ba <file> | less".
    if the optional argument is not a number, but a a path relative to
    Yocto Project's root directory, open it.

e [<n> | <path> ]
edit [<n> | <path> ]
    Edit the file result of the last 'find' command.  If <n> or <path>
    is not provided, pick the first file.  If the EDITOR environment
    variable is not set, it will use "emacs <file>".
    if the optional argument is not a number, but a a path relative to
    Yocto Project's root directory, open it.

wd [-e] <expr>
workdir [-e] <expr>
    Locate the Yocto's workdir for <expr>.  <expr> is implicitly
    suffixed by '*', unless -e is provided.

h
history
    Show the file history.

hv [<n>]
history-view
   Display file <n> in history.  If <n> is omitted, the first one is
   displayed.


he [<n>]
history-edit
   Edit file <n> in history.  If <n> is omitted, the first one is
   edited.

pf [-e] <expr>
pkg-find [-e] <expr>
   Like 'find', but for packages.

pv
pkg-view
   Like 'view', but for packages (show package contents).

pi
pkg-info
   Like, 'view', but for packages (show package information).

EOF
}

###
### Find
###
find_yocto_root() {
    local dir=$1

    if [ -d "$dir/.repo" ]; then
        echo $dir
    elif [ "$dir" = "/" ]; then
        echo /
    else
        find_yocto_root `dirname $dir`
    fi
}

find_cmd() {
    local yroot=`find_yocto_root $PWD`
    local results

    if [ "$yroot" = "/" ]; then
        echo "ERROR: won't search from /" >&2
        exit 1
    fi

    ysources=$yroot/sources

    if [ "$1" = "-e" ]; then
        shift
        find $ysources -name "$*"
    else
        if echo "$*" | grep -q /; then
            results=`find $ysources -path "*$**"`
        else
            results=`find $ysources -iname "*$**"`
        fi
        if [ -n "$results" ]; then
            echo "$results" > $yfind_tmp
            grep -n --color=auto "$*" $yfind_tmp
        fi
    fi
}

###
### Redisplay
###
redisplay_cmd() {
    [ -e $yfind_tmp ] && nl -ba $yfind_tmp
}

###
### Find workdir
###
workdir_cmd() {
    local expr
    local results
    if [ "$1" = "-e" ]; then
        shift
        expr="$*"
    else
        expr="${*}*"
    fi

    if [ -z "$BUILDDIR" ]; then
        echo "ERROR: Could not determine the Yocto Project's build directory." >&2
        exit 1
    fi

    results=`ls -d1 $BUILDDIR/tmp/work/*/$expr`
    if [ -n "$results" ]; then
        echo "$results" > $yfind_workdir_tmp
        grep --color=auto "$expr" $yfind_workdir_tmp
    fi
}


abs_yocto_path() {
    local path=$1
    local root=`find_yocto_root $PWD`
    local maybe_full_path=$root/$path
    
    if [ -e $maybe_full_path ]; then
        echo $maybe_full_path
    else
        if [ "$yroot" = "/" ]; then
            echo "ERROR: won't search from /" >&2
            exit 1
        fi
        find $root/sources -path "*/$path"
    fi
}

handle_match() {
    local fn=$1
    local source=$2
    local linenum_or_filename=$3
    local result

    if [ -e $source ]; then
        if [ -n "$linenum_or_filename" ]; then
            if echo "$linenum_or_filename" | grep -q -E '^[0-9]+$'; then
                result=`awk "NR==$linenum_or_filename" $source`
            else
                if [ `echo "$linenum_or_filename" | cut -c -2` = "./" ] || \
                   [ `echo "$linenum_or_filename" | cut -c -1` = "/" ]; then
                    result="$linenum_or_filename"
                else
                    result=`abs_yocto_path "$linenum_or_filename"`
                    if [ `printf "$result" | wc -l` -gt 1 ]; then
                        printf "$result"
                        echo
                        exit
                    fi
                fi
            fi
        else
            for line in `cat $source`; do
                if [ -f "$line" ]; then
                    result=$line
                    break
                fi
            done
        fi
        if [ -n "$result" ]; then
            echo "$result" >&2
            history_add "$result"
            eval "$fn $result"
        fi
    fi
}


###
### View
###
do_view() {
    local file=$1
    local ext="${file##*.}"
    local pager=

    if [ -z "$PAGER" ]; then
        pager=less
    fi

    case $ext in
        ipk | deb)
            dpkg -c "$file" | $pager
            ;;
        rpm)
            rpm -qlp "$file" | $pager
            ;;
        *)
            if [ -n "$PAGER" ]; then
                "$PAGER" "$file"
            else
                nl -ba "$file" | less
            fi
    esac
    echo $file
}

view_cmd() {
    handle_match do_view $yfind_tmp $1
}


###
### Edit
###
do_edit() {
    if [ -n "$YEDITOR" ]; then
        "$YEDITOR" "$1"
    elif [ -n "$EDITOR" ]; then
        "$EDITOR" "$1"
    else
        emacs "$1"
    fi
    echo $1
}

edit_cmd() {
    handle_match do_edit $yfind_tmp $1
}


###
### History
###
history_len() {
    echo `wc -l $yhistory | awk '{print $1}'`
}

history_add() {
    local item=$1
    local htmp=`mktemp`
    if [ -e $yhistory ]; then
        if grep -q "$item" $yhistory; then
            return
        fi
        if [ `history_len` -gt $MAX_HISTORY ]; then
            tail -n $(($MAX_HISTORY - 1))  $yhistory > $htmp
            mv $htmp $yhistory
        fi
    fi
    echo "$item" >> $yhistory
    rm -f $htmp
}

history_cmd() {
    if [ -e $yhistory ]; then
        cat $yhistory | nl
    fi
}

history_view_cmd() {
    handle_match do_view $yhistory $1
}


history_edit_cmd() {
    handle_match do_edit $yhistory $1
}


###
### Packages
###
pkg_find_cmd() {
    if [ -z "$BUILDDIR" ]; then
        echo "ERROR: Could not determine the Yocto Project's build directory." >&2
        exit 1
    fi

    local deploy_dir=$BUILDDIR/tmp/deploy
    local results
    local pkg_dirs=

    for pkg_format in ipk deb rpm; do
        if [ -d "$deploy_dir/$pkg_format" ]; then
            pkg_dirs="$pkg_dirs $deploy_dir/$pkg_format"
        fi
    done

    if [ "$1" = "-e" ]; then
        shift
        find $pkg_dirs -name "$*"
    else
        if echo "$*" | grep -q /; then
            results=`find $pkg_dirs -path "*$**"`
        else
            results=`find $pkg_dirs -iname "*$**"`
        fi
        if [ -n "$results" ]; then
            echo "$results" > $ypkg_find_tmp
            grep -n --color=auto "$*" $ypkg_find_tmp
        fi
    fi
}

pkg_view_cmd() {
    handle_match do_view $ypkg_find_tmp $1
}

do_pkg_info() {
    local file=$1
    local ext="${file##*.}"
    local pager=

    if [ -z "$PAGER" ]; then
        pager=less
    fi

    case $ext in
        ipk | deb)
            dpkg -I "$file" | $pager
            ;;
        rpm)
            rpm -qip "$file" | $pager
            ;;
        *)
            echo 'Package format not supported.'
    esac
    echo $file
}

pkg_info_cmd() {
    handle_match do_pkg_info $ypkg_find_tmp $1
}


###
### Dispatch
###

if [ -z "$1" ]; then
    usage
    exit 1
fi

if [ "$1" = "-h" ] || [ "$1" = "-help" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

cmd="$1"

case $cmd in
    find | f)
        shift
        find_cmd "$@"
        ;;
    redisplay | r)
        shift
        redisplay_cmd
        ;;
    view | v)
        shift
        view_cmd "$@"
        ;;
    edit | e)
        shift
        edit_cmd "$@"
        ;;
    workdir |  wd)
        shift
        workdir_cmd "$@"
        ;;
    history | h)
        shift
        history_cmd "$@"
        ;;
    history-view | hv)
        shift
        history_view_cmd "$@"
        ;;
    history-edit | he)
        shift
        history_edit_cmd "$@"
        ;;
    pkg-find | pf)
        shift
        pkg_find_cmd "$@"
        ;;
    pkg-view | pv)
        shift
        pkg_view_cmd "$@"
        ;;
    pkg-info | pi)
        shift
        pkg_info_cmd "$@"
        ;;
    *)
        usage
        exit 1
esac
