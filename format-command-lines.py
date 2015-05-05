import os
import sys
import errno

def show(line):
    try:
        sys.stdout.write(line)
        sys.stdout.flush()
    except IOError as e:
        if e.errno == errno.EPIPE:
            input.close()
            sys.exit(0)

input_file = sys.argv[1]
input = open(input_file, 'r')
command_line_counter = 0

while True:
    build_line = input.readline()
    if not build_line:
        break

    tokens = build_line.split()
    if len(tokens) > 0:
        prev = None
        first_token = tokens[0]

        filename = os.path.basename(first_token)
        if (filename.endswith('gcc') or
            filename.endswith('g++') or
            filename.endswith('xgcc') or
            filename.endswith('javac')):
            command_line_counter += 1
            print('--------------[ command line %s ]----------------------' % command_line_counter)
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
input.close()
