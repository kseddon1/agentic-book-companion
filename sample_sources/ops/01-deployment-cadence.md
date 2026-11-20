# Ops Notes: Deployment Cadence

A team that ships small changes frequently has an easier time finding
the cause of a regression than a team that batches a month of work
into one release. The reason is almost entirely about the size of the
search space: when ten commits go out together and something breaks,
the fix starts with isolating which of the ten is responsible. When
one commit goes out, there is no isolation step.

This is why a mature deployment pipeline treats "ship small, ship
often" as the default and treats a large batched release as the
exception that needs its own justification, not the other way around.
Feature flags are the usual tool for keeping that cadence even when a
feature itself is large: the code merges and deploys in small pieces,
and a flag controls when the complete feature actually turns on for
users, decoupling "the code is live on the server" from "the behavior
is live for anyone."

Rollback speed matters more than rollout speed. A deployment system
that can get a bad change out to production in ninety seconds but
takes twenty minutes to revert it has its priorities backwards for an
operations team, because the cost of a slow rollout is measured in
minutes of delay, while the cost of a slow rollback is measured in
minutes of a production incident actively affecting users.
