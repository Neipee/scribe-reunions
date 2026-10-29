@echo off
rem Lance le serveur Scribe (s'il ne tourne pas deja) puis ouvre l'interface dans le navigateur.
rem Utilisation : double-clic. Pour arreter le serveur, fermer la fenetre "Scribe serveur".
setlocal
cd /d "%~dp0.."
set "URL=http://127.0.0.1:8765"

if not exist ".venv\Scripts\python.exe" (
  echo L'environnement Python est introuvable : voir le README ^(section Installation^).
  pause
  exit /b 1
)

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if %errorlevel%==0 (
  echo Le serveur tourne deja. Ouverture du navigateur...
  start "" "%URL%"
  exit /b 0
)

echo Demarrage du serveur Scribe ^(le chargement du modele prend environ 20 secondes^)...
start "Scribe serveur" /min cmd /c ".venv\Scripts\python run.py"

set /a essais=0
:attente
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if %errorlevel%==0 goto pret
set /a essais+=1
if %essais% GEQ 90 goto echec
timeout /t 1 /nobreak >nul
goto attente

:pret
start "" "%URL%"
exit /b 0

:echec
echo Le serveur n'a pas demarre dans le delai. Regardez la fenetre "Scribe serveur" pour le message d'erreur.
pause
exit /b 1
