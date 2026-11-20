# Ops Notes: Incident Response Basics

The first job during an active incident is narrowing down what changed,
not understanding why it changed. A responder who starts by reading
code to understand a subsystem deeply is solving a different, slower
problem than the one in front of them. The faster path is almost
always: what deployed, what config changed, and what traffic pattern
shifted, in roughly that order, cross-referenced against when the
symptom started.

Keeping a single incident channel, with one person clearly designated
to make the call on next steps, prevents the common failure mode where
three people each try a different fix at the same time and nobody can
tell afterward which action actually helped. That designated-owner
pattern matters more than any specific tool; a team using a shared
document and a phone bridge with a clear owner will out-perform a team
with a dedicated incident-management product and no agreed owner.

A postmortem that identifies a single root cause is usually
incomplete. Most real incidents have a trigger (the thing that changed)
and a set of conditions that let the trigger become user-visible (a
missing alert, a retry loop with no backoff, a dependency with no
fallback). Writing down only the trigger and skipping the conditions
means the same class of incident recurs under a different trigger.
