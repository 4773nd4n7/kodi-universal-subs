pushd ..\..

for %%I in (.) do set DIRNAME=%%~nxI
pushd ..
del .\%DIRNAME%\%DIRNAME%.zip
"%PROGRAMFILES%\7-Zip\7z.exe" a .\%DIRNAME%\%DIRNAME%.zip .\%DIRNAME% -x!%DIRNAME%\%DIRNAME%.zip -xr!.git -xr!%DIRNAME%\resources\scripts -xr!%DIRNAME%\resources\examples
popd

popd