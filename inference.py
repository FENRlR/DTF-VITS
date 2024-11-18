import os

#- For windows operations
os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = r"C:\Program Files\eSpeak NG\libespeak-ng.dll"
os.environ["PHONEMIZER_ESPEAK_PATH"] = r"C:\Program Files\eSpeak NG"


import matplotlib.pyplot as plt
#import IPython.display as ipd

import json
import math
import torch
import torchaudio
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader

import commons
import utils
from data_utils import TextAudioLoader, TextAudioCollate, TextAudioSpeakerLoader, TextAudioSpeakerCollate
#from models import SynthesizerTrn
from text.symbols import symbols
from text import text_to_sequence

import pyaudio
import numpy as np

from scipy.io.wavfile import write


def get_text(text, hps):
    text_norm = text_to_sequence(text, hps.data.text_cleaners)
    if hps.data.add_blank:
        text_norm = commons.intersperse(text_norm, 0)
    text_norm = torch.LongTensor(text_norm)
    return text_norm

def audiooutput(audio):
    p = pyaudio.PyAudio()

    stream = p.open(format=pyaudio.paInt16, channels=1, rate=22050, output=True)
    stream.start_stream()

    audio = (audio * 32767).astype(np.int16)

    chunk_size = 1024
    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i + chunk_size].astype(np.int16).tobytes()
        stream.write(chunk)

    stream.stop_stream()
    stream.close()
    p.terminate()

def ttsinfer(hps, mpath, text):
    if hps.model.differential_transformers == "v2":
        from models import SynthesizerTrn
    elif hps.model.differential_transformers == "v1":
        from models_v1 import SynthesizerTrn
    else:
        from models_normal import SynthesizerTrn

    net_g = SynthesizerTrn(
        len(symbols),
        hps.data.filter_length // 2 + 1,
        hps.train.segment_size // hps.data.hop_length,
        n_speakers=hps.data.n_speakers,
        **hps.model).cuda()
    _ = net_g.eval()

    _ = utils.load_checkpoint(mpath, net_g, None)
    stn_tst = get_text(text, hps)
    with torch.no_grad():
        x_tst = stn_tst.cuda().unsqueeze(0)
        x_tst_lengths = torch.LongTensor([stn_tst.size(0)]).cuda()
        sid = torch.LongTensor([4]).cuda()
        audio = net_g.infer(x_tst, x_tst_lengths, sid=sid, noise_scale=.667, noise_scale_w=0.8, length_scale=1)[0][
            0, 0].data.cpu().float().numpy()

        audiooutput(audio)


def testscript(fpath):
    try:
        with open(fpath, 'r', encoding='utf-8') as file:
            sentence = [line.strip() for line in file if line.strip()]
        return sentence
    except Exception as e:
        print(f"ERROR! : {e}")


fpath = './testscript.txt'
testlines = testscript(fpath)

for i in range(len(testlines)):
    text = testlines[i]
    print(f"- TEXT : {text}")
    print("- VITS")
    hps = utils.get_hparams_from_file("./configs/ljs_nosdp_normal.json")
    mpath = "outputs/normal/G_20000.pth"
    ttsinfer(hps, mpath, text)

    print("- VITS with DTF")
    hps = utils.get_hparams_from_file("./configs/ljs_nosdp.json")
    mpath = "outputs/dtf/G_20000.pth"
    ttsinfer(hps, mpath, text)

    print("- VITS with DTF-v2")
    hps = utils.get_hparams_from_file("./configs/ljs_nosdp_v2.json")
    mpath = "outputs/dtf_v2/G_20000.pth"
    ttsinfer(hps, mpath, text)

