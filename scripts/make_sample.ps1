# Génère un échantillon audio français de test (WAV 16 kHz mono 16 bits) avec la voix
# de synthèse Windows locale « Hortense » : aucune donnée personnelle, aucun réseau.
# Usage : powershell -ExecutionPolicy Bypass -File scripts\make_sample.ps1
param(
    [string]$TextFile = "$PSScriptRoot\..\tests\samples\reunion_fr.txt",
    [string]$OutFile = "$PSScriptRoot\..\tests\samples\reunion_fr.wav"
)
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq "fr-FR" } | Select-Object -First 1
if (-not $voice) { throw "Aucune voix française installée (Paramètres > Heure et langue > Voix)." }
$synth.SelectVoice($voice.VoiceInfo.Name)
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$out = Join-Path (Resolve-Path -LiteralPath (Split-Path $OutFile)).Path (Split-Path $OutFile -Leaf)
$synth.SetOutputToWaveFile($out, $format)
$synth.Speak((Get-Content -LiteralPath $TextFile -Raw -Encoding UTF8))
$synth.Dispose()
Write-Output "Echantillon ecrit : $out (voix $($voice.VoiceInfo.Name))"
