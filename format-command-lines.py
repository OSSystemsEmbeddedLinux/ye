import os
import sys
import errno

if len(sys.argv) < 2:
    sys.stderr.write('Usage: %s <file> <modes> [<replacements> ...]' % sys.argv[0])
    sys.exit(1)

input_file = sys.argv[1]

modes = sys.argv[2].split(',') # format-calls, apply-replacements
format_calls = 'format-calls' in modes
apply_replacements = 'apply-replacements' in modes

replacement_args = []
if len(sys.argv) > 2:
    replacement_args = sys.argv[3:]


def show(line):
    try:
        sys.stdout.write(line)
        sys.stdout.flush()
    except IOError as e:
        if e.errno == errno.EPIPE:
            input.close()
            sys.exit(0)

input = open(input_file, 'r')
command_line_counter = 0

if apply_replacements:
    replacements = [] # a list because we want to keep order
    for arg in replacement_args:
        rep = arg.split('=')
        if len(rep) == 2:
            replacements.append((rep[0], rep[1]))
        else:
            sys.stderr.write('WARNING: invalid replacement: %s\n' % arg)

    if replacements:
        print('===\n=== Replacements made by ye\n===\n')
        for orig, rep in replacements:
            print('%s => %s' % (orig, rep))
        print('\n' + '=' * 80 + '\n')

while True:
    build_line = input.readline()
    if not build_line:
        break

    if apply_replacements:
        for orig, rep in replacements:
            build_line = build_line.replace(orig, rep)

    if format_calls:
        tokens = build_line.split()
        if len(tokens) > 0:
            prev = None
            first_token = tokens[0]

            filename = os.path.basename(first_token)
            if (filename.endswith('gcc') or
                filename.endswith('g++') or
                filename.endswith('xgcc') or
                filename.endswith('clang') or
                filename.endswith('clang++') or
                filename.endswith('javac')):
                command_line_counter += 1
                dashes = '-' * 15
                print('%s[ command line %s ]%s' % (dashes, command_line_counter, dashes))
                lines = [first_token]
                for token in tokens[1:]:
                    if prev in ['-o', '-isystem']:
                        lines[-1] += ' ' + token
                    else:
                        lines.append(token)
                    prev = token

                show(lines[0] + '\n')
                for line in lines[1:]:
                    show('  ' + line + '\n')
            else:
                show(build_line)
    else:
        show(build_line)
input.close()
