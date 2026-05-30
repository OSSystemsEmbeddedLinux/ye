import glob
import os
import re
import subprocess


def uniq(paths):
    result = []
    seen = set()
    for path in paths:
        if not path:
            continue
        real = os.path.realpath(os.path.abspath(os.path.expanduser(path)))
        if real not in seen:
            seen.add(real)
            result.append(real)
    return result


def existing_dirs(paths):
    return [path for path in uniq(paths) if os.path.isdir(path)]


def find_upwards(start, names):
    start = os.path.realpath(os.path.abspath(start or os.getcwd()))
    if os.path.isfile(start):
        start = os.path.dirname(start)
    while True:
        for name in names:
            path = os.path.join(start, name)
            if os.path.exists(path):
                return start
        parent = os.path.dirname(start)
        if parent == start:
            return None
        start = parent


def is_program_available(program):
    for directory in os.environ.get('PATH', '').split(os.pathsep):
        path = os.path.join(directory, program)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return True
    return False


def get_builddir():
    builddir = os.environ.get('BUILDDIR')
    if builddir:
        return os.path.realpath(os.path.abspath(builddir))

    found = find_upwards(os.getcwd(),
                         [os.path.join('conf', 'bblayers.conf')])
    if found:
        return found
    return None


def get_repo_root():
    builddir = get_builddir()
    starts = [os.getcwd()]
    if builddir:
        starts.insert(0, builddir)
    for start in starts:
        root = find_upwards(start, ['.repo'])
        if root:
            return root
    return None


def join_bitbake_lines(text):
    logical_lines = []
    current = ''
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped.endswith('\\'):
            current += stripped[:-1] + ' '
            continue
        logical_lines.append(current + stripped)
        current = ''
    if current:
        logical_lines.append(current)
    return logical_lines


def strip_comment(line):
    result = []
    quote = None
    escaped = False
    for char in line:
        if escaped:
            result.append(char)
            escaped = False
            continue
        if char == '\\':
            result.append(char)
            escaped = True
            continue
        if char in ['"', "'"]:
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
        if char == '#' and quote is None:
            break
        result.append(char)
    return ''.join(result)


def expand_bitbake_path(path, variables):
    value = os.path.expanduser(path)
    for _ in range(8):
        expanded = re.sub(r'\${([^}]+)}',
                          lambda m: variables.get(m.group(1),
                                                  os.environ.get(m.group(1), m.group(0))),
                          value)
        if expanded == value:
            break
        value = expanded
    return os.path.expandvars(value)


def quoted_values(line):
    values = []
    quote = None
    value = []
    escaped = False
    for char in line:
        if escaped:
            if quote:
                value.append(char)
            escaped = False
            continue
        if char == '\\':
            escaped = True
            if quote:
                value.append(char)
            continue
        if char in ['"', "'"]:
            if quote == char:
                values.append(''.join(value))
                value = []
                quote = None
            elif quote is None:
                quote = char
            elif quote:
                value.append(char)
            continue
        if quote:
            value.append(char)
    return values


def parse_bblayers_conf(builddir=None):
    builddir = builddir or get_builddir()
    if not builddir:
        return []

    conf = os.path.join(builddir, 'conf', 'bblayers.conf')
    if not os.path.exists(conf):
        return []

    try:
        with open(conf, 'r') as fd:
            data = fd.read()
    except OSError:
        return []

    variables = {
        'TOPDIR': builddir,
        'BUILDDIR': builddir,
        'HOME': os.environ.get('HOME', ''),
    }
    for var in ['OEROOT', 'COREBASE', 'POKYBASE']:
        if os.environ.get(var):
            variables[var] = os.environ[var]

    layers = []
    for line in join_bitbake_lines(data):
        line = strip_comment(line).strip()
        if not re.match(r'^BBLAYERS(?:\s|[:?+.=:]|$)', line):
            continue
        for value in quoted_values(line):
            for token in value.split():
                expanded = expand_bitbake_path(token, variables)
                if not os.path.isabs(expanded):
                    expanded = os.path.join(builddir, expanded)
                matches = glob.glob(expanded)
                layers.extend(matches or [expanded])
    return existing_dirs(layers)


def fallback_source_dirs(builddir=None):
    candidates = []
    repo_root = get_repo_root()
    if repo_root:
        candidates.extend([
            os.path.join(repo_root, 'sources'),
            os.path.join(repo_root, 'layers'),
        ])

    for env_name in ['PLATFORM_ROOT_DIR', 'YE_TOPDIR']:
        if os.environ.get(env_name):
            root = os.environ[env_name]
            candidates.extend([
                os.path.join(root, 'sources'),
                os.path.join(root, 'layers'),
                root,
            ])

    for env_name in ['OEROOT', 'COREBASE']:
        if os.environ.get(env_name):
            candidates.append(os.environ[env_name])

    builddir = builddir or get_builddir()
    if builddir:
        parent = os.path.dirname(builddir)
        candidates.extend([
            os.path.join(parent, 'sources'),
            os.path.join(parent, 'layers'),
            os.path.join(parent, 'poky'),
            os.path.join(parent, 'openembedded-core'),
        ])

    root = find_upwards(os.getcwd(), ['sources', 'layers', 'poky',
                                     'openembedded-core'])
    if root:
        candidates.extend([
            os.path.join(root, 'sources'),
            os.path.join(root, 'layers'),
            os.path.join(root, 'poky'),
            os.path.join(root, 'openembedded-core'),
        ])

    return existing_dirs(candidates)


def source_dirs():
    env_dirs = os.environ.get('YE_SOURCE_DIRS')
    if env_dirs:
        return existing_dirs(env_dirs.split(os.pathsep))

    builddir = get_builddir()
    layers = parse_bblayers_conf(builddir)
    if layers:
        return layers
    return fallback_source_dirs(builddir)


def source_root_dir():
    root = workspace_root()
    if root:
        for name in ['sources', 'layers']:
            path = os.path.join(root, name)
            if os.path.isdir(path):
                return os.path.realpath(path)

    dirs = source_dirs()
    if not dirs:
        return None
    try:
        common = os.path.commonpath(dirs)
        if common and common != os.path.sep and os.path.isdir(common):
            return os.path.realpath(common)
    except ValueError:
        pass
    return dirs[0]


def workspace_root():
    repo_root = get_repo_root()
    if repo_root:
        return repo_root

    roots = []
    builddir = get_builddir()
    if builddir:
        roots.append(builddir)
    roots.extend(source_dirs())
    if roots:
        try:
            common = os.path.commonpath(roots)
            if common and common != os.path.sep:
                return os.path.realpath(common)
        except ValueError:
            pass

    for env_name in ['PLATFORM_ROOT_DIR', 'YE_TOPDIR', 'OEROOT', 'COREBASE']:
        if os.environ.get(env_name):
            return os.path.realpath(os.path.abspath(os.environ[env_name]))
    return find_upwards(os.getcwd(), ['sources', 'layers', 'poky',
                                     'openembedded-core'])


def find_git_root(path):
    if not path or not is_program_available('git'):
        return None
    try:
        out = subprocess.check_output(
            ['git', '-C', path, 'rev-parse', '--show-toplevel'],
            stderr=subprocess.DEVNULL)
        return os.path.realpath(out.decode().strip())
    except (subprocess.CalledProcessError, OSError):
        return None


def git_repos(dirs=None):
    dirs = dirs or source_dirs()
    repos = []
    for directory in dirs:
        root = find_git_root(directory)
        if root:
            repos.append(root)
            continue
        for current, subdirs, _ in os.walk(directory):
            subdirs[:] = [d for d in subdirs
                          if d not in ['.git', 'tmp', 'downloads',
                                       'sstate-cache', 'cache']]
            if '.git' in subdirs:
                repos.append(current)
                subdirs[:] = []
    return existing_dirs(repos)


def sysroot_dirs(machine=None):
    builddir = get_builddir()
    if not builddir:
        return []

    candidates = []
    components = os.path.join(builddir, 'tmp', 'sysroots-components')
    if machine:
        candidates.append(os.path.join(components, machine))
        candidates.append(os.path.join(components, machine.replace('-', '_')))
    candidates.append(components)

    old_sysroots = os.path.join(builddir, 'tmp', 'sysroots')
    if machine:
        candidates.append(os.path.join(old_sysroots, machine))
    candidates.append(old_sysroots)

    candidates.extend(glob.glob(os.path.join(builddir, 'tmp', 'work', '*',
                                             '*', '*', 'recipe-sysroot')))
    candidates.extend(glob.glob(os.path.join(builddir, 'tmp', 'work', '*',
                                             '*', '*', 'recipe-sysroot-native')))
    return existing_dirs(candidates)


def deploy_pkg_dir(pkg_type=None, machine=None):
    builddir = get_builddir()
    if not builddir:
        return None
    deploy = os.path.join(builddir, 'tmp', 'deploy')
    candidates = []
    if pkg_type:
        pkg_base = os.path.join(deploy, pkg_type)
        if machine:
            candidates.append(os.path.join(pkg_base, machine.replace('-', '_')))
            candidates.append(os.path.join(pkg_base, machine))
        candidates.append(pkg_base)
    candidates.append(deploy)
    dirs = existing_dirs(candidates)
    return dirs[0] if dirs else None
