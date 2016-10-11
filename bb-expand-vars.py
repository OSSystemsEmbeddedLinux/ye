#! /usr/bin/env python3
# -*- encoding: utf-8 -*-

""" From https://github.com/kergoth/bb/blob/master/libexec/bbcmd.py """

import re
import argparse
import contextlib
import logging
import os
import sys
import warnings

PATH = os.getenv('PATH').split(':')
bitbake_paths = [os.path.join(path, '..', 'lib')
                 for path in PATH if os.path.exists(os.path.join(path, 'bitbake'))]
if not bitbake_paths:
    raise ImportError("Unable to locate bitbake, please ensure PATH is set correctly.")

sys.path[0:0] = bitbake_paths

import bb.msg
import bb.utils
import bb.providers
import bb.tinfoil
from bb.cookerdata import CookerConfiguration, ConfigParameters


class Terminate(BaseException):
    pass


class Tinfoil(bb.tinfoil.Tinfoil):
    def __init__(self, output=sys.stdout):
        # Needed to avoid deprecation warnings with python 2.6
        warnings.filterwarnings("ignore", category=DeprecationWarning)

        # Set up logging
        self.logger = logging.getLogger('BitBake')
        if output is not None:
            setup_log_handler(self.logger, output)

        self.config = self.config = CookerConfiguration()
        configparams = bb.tinfoil.TinfoilConfigParameters(parse_only=True)
        self.config.setConfigParameters(configparams)
        self.config.setServerRegIdleCallback(self.register_idle_function)
        self.cooker = bb.cooker.BBCooker(self.config)
        self.config_data = self.cooker.data
        bb.providers.logger.setLevel(logging.ERROR)
        bb.taskdata.logger.setLevel(logging.CRITICAL)
        self.cooker_data = None
        self.taskdata = {}

        self.localdata = bb.data.createCopy(self.config_data)
        self.localdata.finalize()
        # TODO: why isn't expandKeys a method of DataSmart?
        bb.data.expandKeys(self.localdata)


    def prepare_taskdata(self, provided=None, rprovided=None):
        self.cache_data = self.cooker.recipecaches['']
        self.taskdata[''] = self.taskdata.get('', bb.taskdata.TaskData(abort=False))

        if provided:
            self.add_provided(provided)

        if rprovided:
            self.add_rprovided(rprovided)

    def add_rprovided(self, rprovided):
        for item in rprovided:
            self.taskdata[''].add_rprovider(self.localdata, self.cache_data, item)

        self.taskdata[''].add_unresolved(self.localdata, self.cache_data)

    def add_provided(self, provided):
        if 'world' in provided:
            if not self.cache_data.world_target:
                self.cooker.buildWorldTargetList()
            provided.remove('world')
            provided.extend(self.cache_data.world_target)

        if 'universe' in provided:
            provided.remove('universe')
            provided.extend(self.cache_data.universe_target)

        for item in provided:
            self.taskdata[''].add_provider(self.localdata, self.cache_data, item)

        self.taskdata[''].add_unresolved(self.localdata, self.cache_data)

    def get_buildid(self, target):
        if not self.taskdata[''].have_build_target(target):
            if target in self.cooker.recipecaches[''].ignored_dependencies:
                return

            reasons = self.taskdata[''].get_reasons(target)
            if reasons:
                self.logger.error("No buildable '%s' recipe found:\n%s", target, "\n".join(reasons))
            else:
                self.logger.error("No '%s' recipe found", target)
            return
        else:
            return self.taskdata[''].getbuild_id(target)

    def target_filenames(self):
        """Return the filenames of all of taskdata's targets"""
        filenames = set()

        for targetid in self.taskdata[''].build_targets:
            fnid = self.taskdata[''].build_targets[targetid][0]
            fn = self.taskdata[''].fn_index[fnid]
            filenames.add(fn)

        for targetid in self.taskdata[''].run_targets:
            fnid = self.taskdata[''].run_targets[targetid][0]
            fn = self.taskdata[''].fn_index[fnid]
            filenames.add(fn)

        return filenames

    def all_filenames(self):
        return self.cooker.recipecaches[''].file_checksums.keys()

    def all_preferred_filenames(self):
        """Return all the recipes we have cached, filtered by providers.

        Unlike target_filenames, this doesn't operate against taskdata.
        """
        filenames = set()
        excluded = set()
        for provide, fns in self.cooker.recipecaches[''].providers.items():
            eligible, foundUnique = bb.providers.filterProviders(fns, provide,
                                                                 self.localdata,
                                                                 self.cooker.recipecaches[''])
            preferred = eligible[0]
            if len(fns) > 1:
                # Excluding non-preferred providers in multiple-provider
                # situations.
                for fn in fns:
                    if fn != preferred:
                        excluded.add(fn)
            filenames.add(preferred)

        filenames -= excluded
        return filenames

    def provide_to_fn(self, provide):
        """Return the preferred recipe for the specified provide"""
        filenames = self.cooker.recipecaches.providers[provide]
        eligible, foundUnique = bb.providers.filterProviders(filenames, provide, self.localdata)
        return eligible[0]

    def build_target_to_fn(self, target):
        """Given a target, prepare taskdata and return a filename"""
        self.prepare_taskdata([target])
        if target in self.taskdata[''].build_targets and self.taskdata[''].build_targets[target]:
            fn = self.taskdata[''].build_targets[target][0]
        return fn

    def parse_recipe_file(self, recipe_filename):
        """Given a recipe filename, do a full parse of it"""
        bb_cache = bb.cache.NoCache(self.cooker.databuilder)
        appends = self.cooker.collection.get_file_appends(recipe_filename)
        try:
            recipe_data = bb_cache.loadDataFull(recipe_filename, appends)
        except Exception:
            raise
        return recipe_data

    def parse_metadata(self, recipe=None):
        """Return metadata, either global or for a particular recipe"""
        if recipe:
            self.prepare_taskdata([recipe])
            filename = self.build_target_to_fn(recipe)
            return self.parse_recipe_file(filename)
        else:
            return self.localdata


def setup_log_handler(logger, output=sys.stderr):
    log_format = bb.msg.BBLogFormatter("%(levelname)s: %(message)s")
    if output.isatty() and hasattr(log_format, 'enable_color'):
        log_format.enable_color()
    handler = logging.StreamHandler(output)
    handler.setFormatter(log_format)

    bb.msg.addDefaultlogFilter(handler)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def sigterm_exception(signum, stackframe):
    raise Terminate()

###### end of bbcmd

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

    ## tinfoil sets up log output for the bitbake loggers, but bb uses
    ## a separate namespace at this time
    setup_log_handler(logging.getLogger('bb'))

    tinfoil = Tinfoil(output=sys.stderr)
    tinfoil.prepare(config_only=True)

    tinfoil.parseRecipes()

    try:
        metadata = tinfoil.parse_metadata(recipe)
    except:
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


if __name__ == '__main__':
    recipe = sys.argv[1]
    var = sys.argv[2]
    show_var_expansions(recipe, var)
