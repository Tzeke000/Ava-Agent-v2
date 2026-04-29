# Training a custom "Hey Ava" wake word model

The runtime currently uses openWakeWord's stock `hey_jarvis` model as a
proxy. Phonetics are close enough that "Hey Ava" usually fires reliably,
but a custom model trained on your voice + the actual phrase will be much
more accurate (lower false-positive rate, better in noise).

This is **optional**. The default install works without it.

## Output

When training finishes you'll have:
```
D:\AvaAgentv2\models\wake_words\hey_ava.onnx
```

`brain/wake_word.py` auto-detects this file on next startup and adds it to
`Model.wakeword_models` alongside `hey_jarvis`. No code changes needed.

## Prerequisites

- WSL2 with Ubuntu (the openWakeWord training pipeline only runs cleanly
  on Linux)
- Python 3.10 or 3.11 inside WSL
- ~10 GB free disk for the negative-data corpus
- ~30–60 minutes for a full training run

## Steps

```bash
# Inside WSL2 Ubuntu
sudo apt-get update
sudo apt-get install -y python3-venv ffmpeg sox

cd ~
git clone https://github.com/dscripka/openWakeWord.git
cd openWakeWord
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install openwakeword[training]
```

## Config — `models/wake_words/hey_ava_config.yaml`

```yaml
model_name: hey_ava
target_phrase:
  - "hey ava"
  - "hey eva"          # Whisper sometimes hears it this way
  - "ava"              # solo "Ava" should also fire
n_samples: 5000        # synthetic positives generated
n_samples_val: 500
custom_negative_phrases:
  - "hey"
  - "java"
  - "lava"
  - "data"
  - "amber"
  - "amazon"
  - "alexa"
augmentation_batch_size: 16
augmentation_rounds: 1
```

## Run training

```bash
python -m openwakeword.train \
  --config_file models/wake_words/hey_ava_config.yaml \
  --target_phrase "hey ava" \
  --output_dir trained_models/hey_ava
```

Training generates synthetic samples via Piper TTS, fetches a negative
corpus, then trains a small LSTM head on top of frozen Google Speech
embeddings. Output is a single `.onnx` file.

## Install

```bash
# From WSL back on the Windows side:
mkdir -p /mnt/d/AvaAgentv2/models/wake_words
cp trained_models/hey_ava/hey_ava.onnx \
   /mnt/d/AvaAgentv2/models/wake_words/hey_ava.onnx
```

Restart `avaagent.py`. You should see:

```
[wake_word] custom hey_ava model loaded: D:\AvaAgentv2\models\wake_words\hey_ava.onnx
[wake_word] openWakeWord ready models=['hey_jarvis', 'hey_ava']
```

Both models will fire — keep `hey_jarvis` if you want belt-and-suspenders,
or remove it from the model list once your custom model proves out.

## Tuning

If your custom model triggers too often:
- Raise the threshold in `brain/wake_word.py` (`_DEFAULT_THRESHOLD = 0.5` →
  `0.6`)
- Add more `custom_negative_phrases` to the config and retrain

If it misses real wake words:
- Lower the threshold to `0.4`
- Add more positive variants ("ava", "okay ava", "yo ava") to
  `target_phrase`
