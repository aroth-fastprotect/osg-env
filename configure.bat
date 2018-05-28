@echo off
set BATCH_FILE=%~f0
set BATCH_DIR=%~dp0
set BUILD_SCRIPT=scripts\build.py
for %%X in (python.exe) do (set PYTHON_EXE=%%~$PATH:X)
for %%i in (echo %BATCH_DIR%) do set ROOT_DIR=%%~fi
for %%i in (echo %BATCH_DIR%) do set SOURCE_DIR=%%~fi

if exist %ROOT_DIR%\%BUILD_SCRIPT% goto find_python
:up_one_level
for %%i in (echo %ROOT_DIR%\..) do set ROOT_DIR_NEXT=%%~fi
echo Next %ROOT_DIR_NEXT% from %ROOT_DIR%
if "%ROOT_DIR_NEXT%"=="%ROOT_DIR%" goto not_found_root_dir
set ROOT_DIR=%ROOT_DIR_NEXT%
echo Checl %ROOT_DIR%\%BUILD_SCRIPT%
if exist %ROOT_DIR%\%BUILD_SCRIPT% goto find_python
goto up_one_level

:find_python
if NOT "%PYTHON_EXE%"=="" goto run_build_script
if exist "%SystemDrive%\Python36\python.exe" set PYTHON_EXE="%SystemDrive%\Python36\python.exe"
if NOT "%PYTHON_EXE%"=="" goto run_build_script
if exist "%SystemDrive%\Python35\python.exe" set PYTHON_EXE="%SystemDrive%\Python35\python.exe"
if NOT "%PYTHON_EXE%"=="" goto run_build_script
if exist "%SystemDrive%\Python34\python.exe" set PYTHON_EXE="%SystemDrive%\Python34\python.exe"
if NOT "%PYTHON_EXE%"=="" goto run_build_script
if exist "%SystemDrive%\Python33\python.exe" set PYTHON_EXE="%SystemDrive%\Python33\python.exe"
if "%PYTHON_EXE%"!="" goto run_build_script
if "%PYTHON_EXE%"=="" goto not_found_python
goto run_build_script

:run_build_script
"%PYTHON_EXE%" %ROOT_DIR%\%BUILD_SCRIPT% --source-dir %SOURCE_DIR% %*
pause
goto end

:not_found_python
echo Unable to find python in PATH or on %SystemDrive%
pause
goto end

:not_found_root_dir
echo Unable to find root directory of source tree
pause
goto end

:end
