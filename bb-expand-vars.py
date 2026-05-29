#! /usr/bin/env python3
# -*- encoding: utf-8 -*-
import os
import sys
import ye_compat

PATH = os.getenv('PATH').split(':')
bitbake_paths = [os.path.join(path, '..', 'lib')
                 for path in PATH if os.path.exists(os.path.join(path, 'bitbake'))]
if not bitbake_paths:
    raise ImportError("Unable to locate bitbake, please ensure PATH is set correctly.")

sys.path[0:0] = bitbake_paths

def find_yocto_root():
    return ye_compat.workspace_root()

def get_yocto_path():
    candidates = []
    for env_name in ['OEROOT', 'COREBASE']:
        if os.environ.get(env_name):
            candidates.append(os.environ[env_name])

    root = find_yocto_root()
    if root:
        candidates.extend([
            os.path.join(root, 'poky'),
            os.path.join(root, 'openembedded-core'),
            os.path.join(root, 'sources', 'poky'),
            os.path.join(root, 'sources', 'openembedded-core'),
            os.path.join(root, 'sources', 'oe'),
        ])

    for layer in ye_compat.source_dirs():
        candidates.extend([
            layer,
            os.path.dirname(layer),
            os.path.dirname(os.path.dirname(layer)),
        ])

    paths = ye_compat.existing_dirs(
        [os.path.join(path, 'scripts', 'lib') for path in candidates])
    if len(paths) < 1:
        print("ERROR: Can't find scripts path")
        sys.exit(1)
    sys.path.append(paths[0])

basepath = ''

get_yocto_path()
from devtool import setup_tinfoil

# For printing indented expression expansions
indent_step = 4

class BBVar():
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return 'BBVAR<' + str(self.name) + '>'

def tokenize_expr(expr):
    def next(pos, expr):
        next_pos = pos + 1
        if next_pos < len(expr):
            return expr[next_pos]
        return None
    tokens = []
    token = ''
    depth = 0
    for charno, char in enumerate(expr):
        if char == '$' and next(charno, expr) == '{':
            if token and depth == 0:
                tokens.append(token)
                token = ''
            depth += 1
        if char == '}':
            if depth == 1:
                tokens.append(token + char)
                token = ''
            else:
                token += char
            depth -= 1
        else:
            token += char
    if depth != 0:
        raise SyntaxError('Unexpected expression depth (> 0) when tokenizing %s' % expr)
    if token:
        tokens.append(token)
    return tokens

def parse_expr(expr):
    if expr[0] == '$':
        return BBVar([parse_expr(token) for token in tokenize_expr(expr[2:-1])])
    else:
        return expr

def parse_exprs(exprs):
    return [parse_expr(expr) for expr in exprs]

def unparse_expr(expr):
    if isinstance(expr, list):
        return ''.join(unparse_expr(exp) for exp in expr)
    elif isinstance(expr, BBVar):
        if isinstance(expr.name, list):
            return ''.join(unparse_expr(exp) for exp in expr.name)
        else:
            return expr.name
    else:
        return expr

def show_expansion(var, val, indent):
    margin_spacing = indent - indent_step
    if margin_spacing == 0:
        margin = ''
    else:
        margin = ' ' * margin_spacing
    print(('%s%s ==> %s' % (margin, unparse_expr(var), val)))

def get_var_val(var, metadata):
    val = None
    if var.startswith('@'):
        try:
            val = eval(var[1:], {'d': metadata})
        except:
            val = '<could not expand>'
    else:
        val = metadata.getVar(var, False)
    return val

def expand_var(var, metadata, indent):
    next_indent = indent + indent_step
    if isinstance(var, list):
        return expand_var(''.join([ expand_var(v, metadata, next_indent) for v in var ]),
                          metadata,
                          next_indent)
    else:
        if isinstance(var, BBVar):
            if isinstance(var.name, list):
                val = get_var_val(expand_var(var.name, metadata, next_indent), metadata)
                exprs = parse_exprs(tokenize_expr(val))
                if filter(lambda e: isinstance(e, BBVar), exprs):
                    show_expansion(var, val, next_indent)
                    return expand_vars(exprs, metadata, next_indent)
                else:
                    show_expansion(var.name[0], val, next_indent)
                    return val
            else:
                name = var.name
                val = get_var_val(var.name, metadata)
                show_expansion(name, val, next_indent)
                return val
        else:
            return var

def expand_vars(vars, metadata, indent=0):
    return ''.join([expand_var(v, metadata, indent) for v in vars])

def expand_expr(expr, metadata):
    return expand_vars(parse_exprs(tokenize_expr(expr)), metadata)

def show_var_expansions(recipe, var, plumbing_mode=False):
    # When plumbing_mode is truthy, var is a list of variables
    tinfoil = None
    try:
        tinfoil = setup_tinfoil(config_only=True, basepath=basepath)
        metadata = getattr(tinfoil, 'config_data', None)
        if recipe:
            if hasattr(tinfoil, 'parseRecipes'):
                tinfoil.parseRecipes()
            elif hasattr(tinfoil, 'parse_recipes'):
                tinfoil.parse_recipes()

            try:
                metadata = tinfoil.parse_recipe(recipe)
            except:
                sys.exit(1)

        if metadata is None:
            sys.stderr.write('Could not load BitBake metadata.\n')
            sys.exit(1)

        if plumbing_mode:
            vars_vals = {}
            for v in var:
                vars_vals[v] = metadata.getVar(v, True)
            return vars_vals
        else:
            val = metadata.getVar(var, True)

        if val is not None:
            print('=== Final value')
            print( '%s = %s' % (var, val))

            print('\n=== Expansion')
            expand_expr('${' + var + '}', metadata)
        else:
            sys.stderr.write('%s: no such variable.\n' % var)
            sys.exit(1)

    finally:
        if tinfoil:
            tinfoil.shutdown()


if __name__ == '__main__':
    recipe = sys.argv[1]
    var = sys.argv[2]
    show_var_expansions(recipe, var)
