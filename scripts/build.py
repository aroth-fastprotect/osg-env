#!/usr/bin/python3
# -*- coding: utf-8 -*-
# kate: space-indent on; indent-width 4; mixedindent off; indent-mode python;

import os
import platform
import argparse
import sys
import re
import io
import fnmatch
import shutil
import subprocess
from time import gmtime, strftime, time
from datetime import timedelta, datetime
from socket import gethostname
import codecs

script_file = os.path.abspath(__file__)
script_dir = os.path.dirname(script_file)

def current_timestamp(timestamp=None):
    if timestamp is None:
        now = datetime.now()
    else:
        now = datetime.fromtimestamp(timestamp)
    return now.strftime("%Y-%m-%d %H:%M:%S.%f")

def _read_line_from_handle(handle, output_handler, encoding):
    line = ""
    try:
        line = handle.readline()
    except Exception:
        pass
    try:
        line = line.decode(encoding)
    except:
        ret = False
    if not line:
        ret = False
    else:
        line = line.rstrip('\n\r')
        output_handler(line)
        ret = True
    return ret

class logfile_writer_proxy(object):
    def __init__(self, writer, prefix=None, target_file=sys.stdout, insert_timestamp=True):
        self._writer = writer
        self._prefix = prefix
        self._target_file = target_file
        self._insert_timestamp = insert_timestamp

    def __call__(self, line):
        if self._prefix:
            full = self._prefix + line + '\n'
        else:
            full = line + '\n'
        _now = time()
        if self._target_file:
            self._target_file.write(full)
            self._target_file.flush()
        if self._insert_timestamp:
            self._writer.write(current_timestamp() + '\t' + full)
        else:
            self._writer.write(full)

def runcmdAndGetData(exe, args=[], verbose=False, outputStdErr=False, outputStdOut=False, stdin=None, stdout=None, stderr=None, input=None, cwd=None, env=None, shell=False):
    all_args = [str(exe)]
    all_args.extend(args)
    if verbose:
        sys.stdout.write("runcmd " + ' '.join(all_args) + (('< %s' % stdin.name) if stdin is not None else '') + '\n')
        sys.stdout.flush()

    stdin_param = stdin if stdin is not None else subprocess.PIPE
    if stdout is not None and hasattr(stdout, '__call__'):
        stdout_param = subprocess.PIPE
    else:
        stdout_param = stdout if stdout is not None else subprocess.PIPE
    if stderr is not None and hasattr(stderr, '__call__'):
        stderr_param = subprocess.PIPE
    else:
        stderr_param = stderr if stderr is not None else subprocess.PIPE

    p = subprocess.Popen(all_args, stdout=stdout_param, stderr=stderr_param, stdin=stdin_param, shell=shell, cwd=cwd, env=env)
    if p:
        if stdout is not None and hasattr(stdout, '__call__') and stderr is not None and hasattr(stderr, '__call__'):
            encoding = 'CP1252' if platform.system() == 'Windows' else 'utf-8'
            epoll = select.epoll()
            epoll.register(p.stdout.fileno(), select.EPOLLIN)
            epoll.register(p.stderr.fileno(), select.EPOLLIN)
            reached_eof = False
            while not reached_eof:
                events = epoll.poll(1)
                for fileno, event in events:
                    if fileno == p.stdout.fileno():
                        if not _read_line_from_handle(p.stdout, stdout, encoding):
                            reached_eof = True
                    elif fileno == p.stderr.fileno():
                        if not _read_line_from_handle(p.stderr, stderr, encoding):
                            reached_eof = True
            sts = p.wait()
            stdoutdata = None
            stderrdata = None
        elif stdout is not None and hasattr(stdout, '__call__'):
            encoding = 'CP1252' if platform.system() == 'Windows' else 'utf-8'
            while True:
                if not _read_line_from_handle(p.stdout, stdout, encoding):
                    break
            sts = p.wait()
            stdoutdata = None
            stderrdata = None
        else:
            if input:
                (stdoutdata, stderrdata) = p.communicate(input.encode())
            else:
                (stdoutdata, stderrdata) = p.communicate()
            if stdoutdata is not None and outputStdOut:
                if int(python_major) < 3: # check for version < 3
                    sys.stdout.write(stdoutdata)
                    sys.stdout.flush()
                else:
                    sys.stdout.buffer.write(stdoutdata)
                    sys.stdout.buffer.flush()
            if stderrdata is not None and outputStdErr:
                if int(python_major) < 3: # check for version < 3
                    sys.stderr.write(stderrdata)
                    sys.stderr.flush()
                else:
                    sys.stderr.buffer.write(stderrdata)
                    sys.stderr.buffer.flush()
            sts = p.returncode
    else:
        sts = -1
        stdoutdata = None
        stderrdata = None
    return (sts, stdoutdata, stderrdata)

class osg_env_build(object):
    def __init__(self):
        self._script_dir = script_dir
        self._build_dir = None
        self._source_dir = None

        self._logfile_handle = None
        self._logfile = None
        self._verbose = False

        self._cmake_executable = 'cmake'
        self._cmake_definitions = {}
        if platform.system() == 'Windows':
            self._cmake_generator = 'Visual Studio 15'
        else:
            self._cmake_generator = 'Unix Makefiles'
        self._cmake_install_prefix = None
        self._cmake_build_type = 'Debug'

        self._submodules = {
            'OpenSceneGraph': {
                'Build': True,
                'CMake':[],
                'links': self._links_osg,
                },
            'osgearth': {
                'Build': False,
                'CMake': ['-DOSG_DIR="$OpenSceneGraph_SOURCE_DIR;$OpenSceneGraph_BUILD_DIR"'],
                'links': self._links_osgearth,
                },
            'sgi': {
                'Build': False,
                'CMake': ['-DOSG_DIR="$OpenSceneGraph_SOURCE_DIR;$OpenSceneGraph_BUILD_DIR"',
                          '-DOSGEARTH_DIR="$osgearth_SOURCE_DIR;$osgearth_BUILD_DIR"'],
                'links': self._links_sgi,
                },
            }

    def log(self, msg):
        sys.stdout.write(msg + '\n')
        sys.stdout.flush()
        if self._logfile_handle:
            self._logfile_handle.write(current_timestamp() + '\t' + msg + '\n')

    def error(self, msg):
        sys.stdout.write('ERROR:' + msg + '\n')
        sys.stdout.flush()
        if self._logfile_handle:
            self._logfile_handle.write(current_timestamp() + '\tERROR:' + msg + '\n')

    def warning(self, msg):
        sys.stdout.write('WARNING:' + msg + '\n')
        sys.stdout.flush()
        if self._logfile_handle:
            self._logfile_handle.write(current_timestamp() + '\tWARNING:' + msg + '\n')

    def _mkpath(self, dir):
        if not os.path.exists(dir):
            try:
                os.makedirs(dir)
                ret = True
            except (IOError, WindowsError, OSError) as e:
                self.error('Failed to create directory ' + dir + ' (error ' + str(e) + ')\n')
                ret = False
                pass
        else:
            ret = True
        return ret

    def _symlink(self, target, dest, dir=False):
        if os.path.exists(dest) or os.path.islink(dest):
            os.unlink(dest)
        os.symlink(target, dest)

    def _create_build_dir(self):
        build_dir_name = os.path.basename(self._build_dir)
        for f in ['', 'bin', 'lib']:
            d = os.path.join(self._build_dir, f)
            self._mkpath(d)
            for submod in self._submodules.keys():
                submoddir = os.path.join(self._build_dir, submod)
                if f:
                    r = os.path.relpath(d, submoddir)
                    self._symlink(r, os.path.join(submoddir, f), dir=True)
                else:
                    self._mkpath(submoddir)
        for submod, submod_opts in self._submodules.items():
            submod_build_dir = os.path.join(self._build_dir, submod)
            submod_source_dir = os.path.join(self._source_dir, submod)
            links = submod_opts.get('links', None)
            if links:
                links(submod_source_dir, submod_build_dir)

    def _configure_and_build(self):
        for submod, submod_opts in self._submodules.items():
            submod_build_dir = os.path.join(self._build_dir, submod)
            submod_source_dir = os.path.join(self._source_dir, submod)
            build = submod_opts.get('Build', True)
            if build:
                self._run_cmake(submod_source_dir, submod_build_dir, opts=submod_opts['CMake'])

    def _get_build_environment(self, use_os_environ=True):
        cmake_env = os.environ if use_os_environ else {}
        return cmake_env

    def _prepare_vars(self):
        self._vars = {}
        for submod in self._submodules.keys():
            submod_build_dir = os.path.join(self._build_dir, submod)
            submod_source_dir = os.path.join(self._source_dir, submod)
            self._vars['$%s_BUILD_DIR' % submod] = submod_build_dir
            self._vars['$%s_SOURCE_DIR' % submod] = submod_source_dir
        #print(self._vars)

    def _expand_vars(self, s):
        for k,v in self._vars.items():
            s = s.replace(k, v)
        return s

    def _run_cmake(self, source_dir, build_dir, opts, build=True):

        cmake_stdout = logfile_writer_proxy(self._logfile_handle)
        cmake_stderr = subprocess.STDOUT

        cmake_env = self._get_build_environment()
        self.log('CMake generator: %s' % (self._cmake_generator))
        self.log('CMake build type: %s' % (self._cmake_build_type))
        self.log('CMake install prefix: %s' % (self._cmake_install_prefix))


        cmake_opts=[]
        cmake_opts.extend(['-G', self._cmake_generator])
        cmake_opts.append('-DCMAKE_BUILD_TYPE=%s' % self._cmake_build_type)

        if self._cmake_definitions:
            for k,v in self._cmake_definitions.items():
                cmake_opts.append('-D%s=%s' % (k,v))

        if self._cmake_install_prefix is not None:
            cmake_opts.append('-DCMAKE_INSTALL_PREFIX=%s' % self._cmake_install_prefix)

        for o in opts:
            cmake_opts.append(self._expand_vars(o))
        cmake_opts.append(source_dir)

        self.log('CMake defines:')
        for opt in cmake_opts:
            if opt.startswith('-D'):
                self.log('   %s' % opt[2:])

        self._cmake_start_timestamp = time()
        self.log('CMake:')
        (cmake_exitcode, stdout, stderr) = runcmdAndGetData(self._cmake_executable, cmake_opts, env=cmake_env, cwd=build_dir, stdout=cmake_stdout, stderr=cmake_stderr, verbose=self._verbose)
        ret = True if cmake_exitcode == 0 else False

        self._cmake_end_timestamp = time()
        self._cmake_time = timedelta(seconds=self._cmake_end_timestamp - self._cmake_start_timestamp)

        if ret:
            self.log('CMake configuration successful in %s' % (self._cmake_time))
        else:
            self.error('CMake configuration failed with status %i in %s' % (cmake_exitcode, self._cmake_time))

        if build:
            cmake_opts=[]
            cmake_opts.append('--build')
            cmake_opts.append(build_dir)
            if self._cmake_generator == 'Unix Makefiles':
                cmake_opts.append('--')
                cmake_opts.append('-j4')

            self._cmake_start_timestamp = time()
            self.log('CMake build:')
            (cmake_exitcode, stdout, stderr) = runcmdAndGetData(self._cmake_executable, cmake_opts, env=cmake_env, cwd=build_dir, stdout=cmake_stdout, stderr=cmake_stderr, verbose=self._verbose)
            ret = True if cmake_exitcode == 0 else False
            if ret:
                self.log('CMake build successful in %s' % (self._cmake_time))
            else:
                self.error('CMake build failed with status %i in %s' % (cmake_exitcode, self._cmake_time))

        return ret

    def _links_osg(self, src_dir, build_dir):
        #print('_links_osg %s, %s' % (src_dir, build_dir))
        build_inc_osg = os.path.join(build_dir, 'include/osg')
        self._mkpath(build_inc_osg)

        build_inc_ot = os.path.join(build_dir, 'include/OpenThreads')
        self._mkpath(build_inc_ot)

        for f in ['Version', 'Config', 'GL']:
            self._symlink(os.path.join(build_inc_osg, f), os.path.join(src_dir, 'include/osg', f))
        for f in ['Version', 'Config']:
            self._symlink(os.path.join(build_inc_ot, f), os.path.join(src_dir, 'include/OpenThreads', f))

        if self._cmake_build_type == 'Debug':
            for f in ['OpenThreads', 'osgAnimation', 'osgDB', 'osg', 'osgFX', 'osgGA', 'osgManipulator', 'osgParticle', 'osgPresentation',
                    'osgShadow', 'osgSim', 'osgTerrain', 'osgText', 'osgUI', 'osgUtil', 'osgViewer', 'osgVolume', 'osgWidget']:
                if platform.system() == 'Windows':
                    self._symlink('%sd.lib', os.path.join(build_dir, 'lib', '%s.lib'))
                else:
                    self._symlink('lib%sd.so', os.path.join(build_dir, 'lib', 'lib%s.so'))

    def _links_osgearth(self, src_dir, build_dir):

        build_inc = os.path.join(build_dir, 'include')
        self._mkpath(build_inc)

        for f in ['osgEarth', 'osgEarthAnnotation', 'osgEarthDrivers', 'osgEarthFeatures', 'osgEarthQt', 'osgEarthSplat', 'osgEarthSymbology', 'osgEarthUtil']:
            self._symlink(os.path.join(src_dir, 'include', f), os.path.join(build_inc, f), dir=True)

    def _links_sgi(self, src_dir, build_dir):

        pass

    def main(self):
        #=============================================================================================
        # process command line
        #=============================================================================================
        parser = argparse.ArgumentParser(description='executes a build job under jenkins')
        parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='enable verbose output of this script.')
        parser.add_argument('--source-dir', dest='source_dir', help='specifies the name of the source directory relative to the jenkins workspace.')
        parser.add_argument('--build-dir', dest='build_dir', help='specifies the name of the build directory relative to the jenkins workspace.')
        parser.add_argument('--logfile', dest='logfile', help='override the logfile')
        args = parser.parse_args()

        self._verbose = args.verbose
        self._logfile = args.logfile
        if args.source_dir is None:
            sys.stderr.write('No source directory specified.\n')
            return -1
        else:
            self._source_dir = os.path.abspath(args.source_dir)
        if args.build_dir:
            self._build_dir = os.path.abspath(args.build_dir)
        else:
            self._build_dir = os.path.abspath(os.path.join(self._source_dir, 'build'))

        logfile_encoding = 'utf-8'
        if not self._logfile:
            self._logfile = os.path.abspath(os.path.join(self._build_dir, 'build.log'))
        if self._logfile:
            logfile_dir = os.path.dirname(self._logfile)
            self._mkpath(logfile_dir)
            try:
                self._logfile_handle = codecs.open(self._logfile, 'w', logfile_encoding)
            except IOError as e:
                sys.stderr.write('Failed to create logfile at %s\n' %self._logfile)
                self._logfile_handle = None
        self.log('Logfile: %s' % self._logfile)
        self._create_build_dir()
        self._prepare_vars()
        self._configure_and_build()

        return 0


if __name__ == "__main__":
    app = osg_env_build()
    sys.exit(app.main())

