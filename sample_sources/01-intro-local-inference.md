# Local LLM Serving: Why Run Inference Yourself

Running a large language model on your own hardware means every prompt
and response stays on your machine instead of travelling to someone
else's API. For a hobby project called "Lantern Notes" — a small note-
taking assistant that never leaves a laptop — that privacy guarantee was
the whole point. Nothing about the user's notes should ever touch a
third-party server.

Local serving also removes the per-token bill. Once the model and the
serving software are installed, every request is free in dollar terms;
the only cost is the electricity and the wear on the GPU. That trade-off
favors local serving when request volume is high and the task doesn't
need the very largest frontier models.

The downside is capacity. A consumer GPU tops out well below what a
hosted frontier model can hold in memory, so local serving usually means
choosing a smaller model, a quantized version of a larger one, or
splitting work between local and hosted models depending on the task.
The Lantern Notes project ended up doing exactly that: simple note
tagging ran locally, and only the occasional "summarize my whole week"
request went to a hosted model.

A local serving stack has three moving pieces: a model file, a serving
runtime that loads it and exposes an API, and a context window large
enough for the task. Get any one of the three wrong — too big a model,
a runtime that doesn't support the quantization format, or a context
window too small for the conversation — and the whole thing either
refuses to start or runs so slowly it isn't worth it.
