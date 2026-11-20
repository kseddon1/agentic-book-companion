# Context Window Tuning for Local Serving

The context window is how much conversation and reference text a model
can "see" at once, measured in tokens. A larger context window lets the
model hold a longer conversation or a longer reference document, but it
also uses more memory, because the model keeps a cache (often called the
KV cache) proportional to both the context length and the number of
requests being served at the same time.

Most local serving runtimes pick a default context window based on
available VRAM rather than the model's maximum supported length. That
default is sometimes too small for an agent-style workload, which tends
to need a larger window to hold tool definitions, conversation history,
and retrieved reference text all at once. On the Lantern Notes project,
the default window was large enough for plain chat but had to be raised
for the note-tagging workflow, which fed in several retrieved notes
alongside the running conversation.

Raising the context window is not free: doubling it roughly doubles the
KV cache's memory use for a single request. Serving more than one
request at a time multiplies that further, since each concurrent request
gets its own cache. A common fix for a memory-constrained setup is to
limit the server to one request at a time, so the full context budget is
available to whichever request is running.

If the context window is set too small for what a client actually sends,
behavior varies by runtime: some truncate the oldest part of the
conversation silently, others return an error. Silent truncation is the
more dangerous failure mode for an agent-style workload, because the
model can lose track of instructions given early in a session without
any visible warning.
