#!/usr/bin/env python

import argparse
import os
import subprocess
import sys
import logging
import shlex
import apt
import apt_inst
import apt_pkg


def create_ipython_wrapper(base_dir):
    ipython_file = """#!/bin/bash\n"exec" "{0}/bin/python" "$0" "$@" "--ipython-dir={0}/.ipython"\n""".format(base_dir) + \
                   """# -*- coding: utf-8 -*-\nimport re\nimport sys\n\nfrom IPython import start_ipython\n\n""" + \
                   """if __name__ == '__main__':\n     sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])\n""" + \
                   """     sys.exit(start_ipython())"""

    with open('{0}/bin/ipython'.format(base_dir), 'w') as stream:
        stream.write(ipython_file)

def main():
    parser = argparse.ArgumentParser(description='Setup user environment')
    parser.add_argument('--loglevel', help='Logging level', choices=['DEBUG',
                        'ERROR', 'INFO', 'WARN'])
    parser.add_argument('--vdir', help='Directory to create the virtual environment in')

    args = parser.parse_args()

    if args.vdir:
        work_space = os.path.abspath(args.vdir)
    else:
        work_space = os.getcwd()

    base_dir = work_space + '/.venv'
    cmds = ['virtualenv {0}'.format(base_dir)]

    # Link the apt libraries in the virtual environment
    sitepkgs = "{0}/lib/python2.7/site-packages/".format(base_dir)
    apt_libs = [os.path.dirname(apt.__file__)]
    apt_libs.append( apt_inst.__file__)
    apt_libs.append(apt_pkg.__file__)

    for apt_file in apt_libs:
        cmds.append("ln -s {0} {1}".format(apt_file, sitepkgs))

    cmds.append('{0}/bin/pip install --no-cache-dir -q -r requirements.txt -e {1}'.format(base_dir, work_space))

    for cmd in cmds:
        subprocess.check_output(shlex.split(cmd))

    create_ipython_wrapper(base_dir)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)5s: %(message)s')
    log = logging.getLogger(__name__)
    sys.exit(main())
