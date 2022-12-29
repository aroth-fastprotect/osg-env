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

    def only_win32(self, s):
        if self._build_win32:
            return s
        else:
            return None


    def __init__(self):
        self._script_dir = script_dir
        self._build_dir = None
        self._source_dir = None
        self._thirdparty_dir = None

        self._logfile_handle = None
        self._logfile = None
        self._verbose = False

        self._cmake_executable = 'cmake'
        self._cmake_definitions = {}
        if platform.system() == 'Windows':
            self._build_win32 = True
            self._cmake_generator = 'Visual Studio 15'
        else:
            self._build_win32 = False
            self._cmake_generator = 'Unix Makefiles'
        self._cmake_install_prefix = None
        self._cmake_build_type = 'Debug'

        self._submodules = {
            'OpenSceneGraph': {
                'alias': ['osg'],
                'Build': True,
                'CMake':[
                #'-DOPENGL_PROFILE=GLCORE'
                self.only_win32('-DZLIB_INCLUDE_DIR=$THIRDPARTY_gdal_DIR/include'),
                self.only_win32('-DZLIB_LIBRARY=$THIRDPARTY_gdal_DIR/lib/zlib.lib'),
                self.only_win32('-DPNG_PNG_INCLUDE_DIR=$THIRDPARTY_gdal_DIR/include'),
                self.only_win32('-DPNG_LIBRARY=$THIRDPARTY_gdal_DIR/lib/libpng.lib')
                ],
                'links': self._links_osg,
                },
            'VulkanSceneGraph': {
                'alias': ['vsg'],
                'Build': True,
                'CMake':[
                #'-DOPENGL_PROFILE=GLCORE'
                '-DBUILD_SHARED_LIBS=ON',
                self.only_win32('-DZLIB_INCLUDE_DIR=$THIRDPARTY_gdal_DIR/include'),
                self.only_win32('-DZLIB_LIBRARY=$THIRDPARTY_gdal_DIR/lib/zlib.lib'),
                self.only_win32('-DPNG_PNG_INCLUDE_DIR=$THIRDPARTY_gdal_DIR/include'),
                self.only_win32('-DPNG_LIBRARY=$THIRDPARTY_gdal_DIR/lib/libpng.lib')
                ],
                'links': self._links_vsg,
                },
            'osgearth': {
                'alias': ['oe'],
                'Build': True,
                'CMake': [
                    '-DOSG_DIR=$OpenSceneGraph_SOURCE_DIR;$OpenSceneGraph_BUILD_DIR',
                    self.only_win32('-DGDAL_INCLUDE_DIR=$THIRDPARTY_gdal_DIR/include'),
                    self.only_win32('-DGDAL_LIBRARY=$THIRDPARTY_gdal_DIR/lib/gdal_i.lib'),
                    self.only_win32('-DCURL_INCLUDE_DIR=$THIRDPARTY_gdal_DIR/include'),
                    self.only_win32('-DCURL_LIBRARY=$THIRDPARTY_gdal_DIR/lib/libcurl_imp.lib'),
                    ],
                'links': self._links_osgearth,
                },
            'sgi': {
                'Build': True,
                'CMake': ['-DOSG_DIR=$OpenSceneGraph_SOURCE_DIR;$OpenSceneGraph_BUILD_DIR',
                          '-DOSGEARTH_DIR=$osgearth_SOURCE_DIR;$osgearth_BUILD_DIR'],
                'links': self._links_sgi,
                },
            }
        
        
        self._thirdparty_modules = {
            'glcore': {
                'Build': self._build_win32,
                'prepare': self._win32_glcore,
            },
            'qt5': {
                'Build': self._build_win32,
                'prepare': self._win32_qt5,
            },
            'gdal': {
                'Build': self._build_win32,
                'prepare': self._win32_gdal,
            },
        }
            
            
    def _win32_symlink_hint(self):
        print("For getting symlink support on Windows 7 to the same level as a UNIX machine please follow the instructions at:")
        print("""https://superuser.com/questions/124679/how-do-i-create-a-link-in-windows-7-home-premium-as-a-regular-user""")

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

    def _rmdir(self, dir):
        if os.path.lexists(dir):
            if os.path.isdir(dir) and not os.path.islink(dir):
                print('rm %s' % dir)
                shutil.rmtree(dir, ignore_errors=True)
            else:
                print('unlink %s' % dir)
                os.unlink(dir)

    def _symlink(self, target, dest, dir=False):
        self._rmdir(dest)
        try:
            os.symlink(target, dest)
        except OSError as e:
            if platform.system() == 'Windows':
                print("OSError %s: %s" % (e.winerror, e))
                self._win32_symlink_hint()
                sys.exit(-1)
            else:
                print("OSError %s: %s" % (e.errno, e))

    def _download_file(self, url, dest):
        from urllib.request import urlretrieve
        if not os.path.isfile(dest):
            self.log('Download %s to %s' % (url, dest))
            urlretrieve(url, dest)
        else:
            self.log('Downloaded file %s already exists.' % (dest))
            
    def _unzip_file(self, filename, destination_dir):
        import zipfile
        self.log('Unzip %s to %s' % (filename, destination_dir))
        zip_ref = zipfile.ZipFile(filename, 'r')
        zip_ref.extractall(destination_dir)
        zip_ref.close()

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


        self._thirdparty_dir = os.path.join(self._build_dir, 'thirdparty')

        self._mkpath(self._thirdparty_dir)
        for tmod, tmod_opts in self._thirdparty_modules.items():
            tmod_build = tmod_opts.get('Build', True)
            prepare = tmod_opts.get('prepare', None)
            if tmod_build and prepare:
                prepare()

    def _configure_and_build(self, build=True):
        for submod, submod_opts in self._submodules.items():
            if submod not in self._selected_submodules:
                self.log('Skip module %s' % submod)
                continue

            submod_build_dir = os.path.join(self._build_dir, submod)
            submod_source_dir = os.path.join(self._source_dir, submod)
            submod_build = submod_opts.get('Build', True)
            if submod_build:
                self._run_cmake(submod_source_dir, submod_build_dir, opts=submod_opts['CMake'], build=build)

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
            
        for mod in self._thirdparty_modules.keys():
            d = os.path.join(self._thirdparty_dir, mod )
            self._vars['$THIRDPARTY_%s_DIR' % mod] = d
        print(self._vars)

    def _expand_vars(self, s):
        for k,v in self._vars.items():
            s = s.replace(k, v)
        return s

    def _run_cmake(self, source_dir, build_dir, opts, build=True):

        cmake_stdout = logfile_writer_proxy(self._logfile_handle)
        cmake_stderr = subprocess.STDOUT

        cmake_env = self._get_build_environment()
        cmake_cache_txt = os.path.join(build_dir, 'CMakeCache.txt')
        makefile = os.path.join(build_dir, 'Makefile')
        if not os.path.isfile(cmake_cache_txt) or not os.path.isfile(makefile) or self._force:
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
                if o is not None:
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

            self._cmake_end_timestamp = time()
            self._cmake_time = timedelta(seconds=self._cmake_end_timestamp - self._cmake_start_timestamp)

            if ret:
                self.log('CMake build successful in %s' % (self._cmake_time))
            else:
                self.error('CMake build failed with status %i in %s' % (cmake_exitcode, self._cmake_time))

        return ret
        
    def _win32_glcore(self):
        d = os.path.join(self._thirdparty_dir, 'glcore', 'GL')
        print('Prepare GLCore in %s' % d)
        self._mkpath(d)
        self._download_file("""https://www.khronos.org/registry/OpenGL/api/GL/glcorearb.h""", os.path.join(d, 'glcorearb.h'))
        self._download_file("""https://www.khronos.org/registry/OpenGL/api/GL/wglext.h""", os.path.join(d, 'wglext.h'))

    def _win32_qt5(self):
        d = os.path.join(self._thirdparty_dir, 'qt5')
        print('Prepare Qt5 in %s' % d)

    def _win32_gdal(self):
        gdal_dir = os.path.join(self._thirdparty_dir, 'gdal')
        d = os.path.join(gdal_dir, 'zip')
        print('Prepare GDAL in %s' % d)
        self._mkpath(d)
        self._download_file('''http://download.gisinternals.com/sdk/downloads/release-1911-gdal-2-3-0-mapserver-7-0-7-libs.zip''', os.path.join(d, 'release-1911-gdal-2-3-0-mapserver-7-0-7-libs.zip'))
        self._download_file('''http://download.gisinternals.com/sdk/downloads/release-1911-gdal-2-3-0-mapserver-7-0-7.zip''', os.path.join(d, 'release-1911-gdal-2-3-0-mapserver-7-0-7.zip'))
        self._unzip_file(os.path.join(d, 'release-1911-gdal-2-3-0-mapserver-7-0-7-libs.zip'), gdal_dir)
        self._unzip_file(os.path.join(d, 'release-1911-gdal-2-3-0-mapserver-7-0-7.zip'), gdal_dir)

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
                    self._symlink('%sd.lib' % f, os.path.join(build_dir, 'lib', '%s.lib' % f))
                else:
                    self._symlink('lib%sd.so' % f, os.path.join(build_dir, 'lib', 'lib%s.so' % f))

    def _links_vsg(self, src_dir, build_dir):
        #print('_links_osg %s, %s' % (src_dir, build_dir))
        build_inc_vsg = os.path.join(build_dir, 'include/vsg')
        self._mkpath(build_inc_vsg)

        build_inc_ot = os.path.join(build_dir, 'include/OpenThreads')
        self._mkpath(build_inc_ot)

        for f in ['Version', 'Config', 'GL']:
            self._symlink(os.path.join(build_inc_vsg, f), os.path.join(src_dir, 'include/vsg', f))
        for f in ['Version', 'Config']:
            self._symlink(os.path.join(build_inc_ot, f), os.path.join(src_dir, 'include/OpenThreads', f))

        if self._cmake_build_type == 'Debug':
            for f in ['OpenThreads', 'osgAnimation', 'osgDB', 'osg', 'osgFX', 'osgGA', 'osgManipulator', 'osgParticle', 'osgPresentation',
                    'osgShadow', 'osgSim', 'osgTerrain', 'osgText', 'osgUI', 'osgUtil', 'osgViewer', 'osgVolume', 'osgWidget']:
                if platform.system() == 'Windows':
                    self._symlink('%sd.lib' % f, os.path.join(build_dir, 'lib', '%s.lib' % f))
                else:
                    self._symlink('lib%sd.so' % f, os.path.join(build_dir, 'lib', 'lib%s.so' % f))

    def _links_osgearth(self, src_dir, build_dir):

        build_inc = os.path.join(build_dir, 'include')
        self._mkpath(build_inc)

        for f in ['osgEarth', 'osgEarthAnnotation', 'osgEarthDrivers', 'osgEarthFeatures', 'osgEarthQt', 'osgEarthSplat', 'osgEarthSymbology', 'osgEarthUtil']:
            self._symlink(os.path.join(src_dir, 'src', f), os.path.join(build_inc, f), dir=True)

        build_inc_oe = os.path.join(build_dir, 'build_include/osgEarth')
        for f in ['BuildConfig.h']:
            self._symlink(os.path.join(build_inc_oe, f), os.path.join(build_dir, 'include/osgEarth', f))

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
        parser.add_argument('-f', '--force', dest='force', action='store_true', help='force to run CMake for each submodules')
        parser.add_argument('-n', '--no-build', dest='build', action='store_false', help='disable building of modules')
        parser.add_argument('submodule', nargs='*', help='override the logfile')
        args = parser.parse_args()

        self._verbose = args.verbose
        self._force = args.force
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
        if self._force:
            self.log('CMake: forced')

        if args.submodule is None or len(args.submodule) == 0:
            self._selected_submodules = self._submodules.keys()
        else:
            self._selected_submodules = []
            for s in args.submodule:
                found = False
                for sk, sv in self._submodules.items():
                    if sk.lower() == s.lower():
                        self._selected_submodules.append(sk)
                        found = True
                        break
                    else:
                        for a in sv.get('alias', []):
                            if a.lower() == s.lower():
                                self._selected_submodules.append(sk)
                                found = True
                                break

                if not found:
                    self.error('Unknown submodule %s (available submodule %s)' % (s, ','.join(self._submodules.keys())))
                    return 2

        self.log('Submodules: %s' % ','.join(self._selected_submodules))
        self._create_build_dir()
        self._prepare_vars()
        self._configure_and_build(build=args.build)

        return 0


if __name__ == "__main__":
    app = osg_env_build()
    sys.exit(app.main())

