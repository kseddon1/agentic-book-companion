# Choosing Hardware for Local LLM Serving

The single biggest hardware decision for local serving is how much VRAM
the GPU has, because VRAM is what limits model size, quantization level,
and context window all at once. A GPU with more VRAM gives more room to
trade off between those three; a GPU with less VRAM forces smaller
models, more aggressive quantization, or a shorter context window — or
some combination of the three.

The Lantern Notes project ran its tests on three different machines: a
laptop with 8 GB of VRAM, a desktop with 16 GB, and a workstation with
24 GB. The 8 GB laptop could only run a 4-bit quantized small model with
a modest context window. The 16 GB desktop could run the same model at
8-bit with more headroom for context, or a larger model at 4-bit. The
24 GB workstation had enough room to run a mid-size model at 8-bit with
a generous context window and still leave VRAM free for the embedding
model used by the note-retrieval step.

CPU and system RAM matter less for inference speed once the model fits
entirely in VRAM, but they matter a lot when it doesn't. A model that
spills partly onto the CPU runs dramatically slower — often an order of
magnitude — because the GPU has to wait on much slower CPU memory for
part of every calculation. If `ps`-style tooling or the runtime's own
status command shows a model split between CPU and GPU instead of
100% GPU, that is usually the first thing to fix, either by lowering the
context window, choosing a smaller model, or adding VRAM.

Disk space is the easy one to forget: several quantization levels of the
same model, downloaded for comparison, add up fast. The Lantern Notes
team kept only the quantization level they'd settled on per machine and
deleted the rest.
