pushd ..\..

for %%I in (.) do set DIRNAME=%%~nxI

set KODI_ADDON_DIRNAME=C:\Users\Kodi\AppData\Roaming\Kodi\addons\%DIRNAME%
rem set KODI_ADDON_DIRNAME=%APPDATA%\Kodi\addons\%DIRNAME%

rmdir %KODI_ADDON_DIRNAME%
mklink /J %KODI_ADDON_DIRNAME% .

popd