# Quantization Formats for Local Serving

Quantization shrinks a model by storing its weights with fewer bits per
number. A model trained and stored at 16-bit precision can often be
quantized down to 8-bit or 4-bit with only a small quality loss, and the
size savings are large: a 4-bit quantized model takes roughly a quarter
of the disk space and VRAM of its 16-bit original.

For the Lantern Notes project, the team tested three quantization levels
on the same base model: 16-bit (the original), 8-bit, and 4-bit. The
16-bit version did not fit in the test laptop's 8 GB of VRAM at all. The
8-bit version fit, but left very little headroom for context. The 4-bit
version left enough free VRAM to run a reasonably long conversation
alongside the model weights.

Quality did drop slightly from 16-bit to 4-bit, most noticeably on tasks
that needed precise formatting, like producing valid JSON on the first
try. For free-form summarization and tagging — Lantern Notes' actual
workload — the difference was hard to notice in casual use.

Not every serving runtime supports every quantization format. Some
runtimes only load a handful of specific formats and will refuse a file
in an unsupported one with a cryptic error. Checking the runtime's
supported formats before downloading a multi-gigabyte model file saves a
wasted download.

The practical rule the Lantern Notes team settled on: pick the largest
quantization level (closest to 16-bit) that still leaves enough VRAM for
the context window the workload needs, and only drop to a smaller
quantization level if the model won't fit otherwise.
