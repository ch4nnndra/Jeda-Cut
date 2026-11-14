# Sintesis tiap kalimat ke WAV 16 kHz mono, satu file per suara per kalimat.
param([string]$Out)
Add-Type -AssemblyName System.Speech
$sentences = @(
  "Good morning everyone, and welcome back to the course.",
  "Today we are going to talk about digital video processing.",
  "Okay.",
  "First, let us look at how audio is stored inside a video file.",
  "Every sound is a sequence of numbers sampled many times per second.",
  "Right.",
  "When nobody is speaking, the energy of the signal drops close to the background noise.",
  "So, how do we find those pauses automatically?",
  "One simple idea is to measure the energy of short frames.",
  "Another idea is to count how often the signal crosses zero.",
  "Hmm, let me think about that for a second.",
  "Consonants like s and f have low energy but cross zero very often.",
  "That is why we combine both features.",
  "Next, we need a threshold that adapts to every recording.",
  "A fixed threshold fails when the room is noisy.",
  "Yes.",
  "We also add a little padding before and after each word.",
  "Otherwise the start and the end of a sentence may be cut off.",
  "Finally, the video is rendered again with all the pauses removed.",
  "The result is a shorter lecture with exactly the same content.",
  "Any questions so far?",
  "Great, let us continue with the next topic.",
  "Remember to submit your assignment before Friday.",
  "Thank you, and see you next week."
)
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
foreach ($voice in @("Microsoft David Desktop", "Microsoft Zira Desktop")) {
  $tag = $voice.Split(" ")[1].ToLower()
  for ($i = 0; $i -lt $sentences.Count; $i++) {
    $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $s.SelectVoice($voice)
    $s.SetOutputToWaveFile((Join-Path $Out ("{0}_{1:D2}.wav" -f $tag, $i)), $fmt)
    $s.Speak($sentences[$i])
    $s.Dispose()
  }
}
"done"
