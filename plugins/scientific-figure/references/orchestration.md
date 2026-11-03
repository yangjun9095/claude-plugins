# Orchestrating figure agents without losing work

Four collisions in one session, all from the same root cause: more than one agent owning a
file. None was caught by a check; every one was caught by an agent noticing its file had
moved and stopping to ask.

## Rails

**One writer per file, per phase.** Not a convention — a constraint the orchestration
enforces. Participants cannot detect the conflict from inside.

**Agents cannot see each other, and neither can you.** `ListAgents` does **not** list
workflow-internal agents. Two agents were editing one file while the only running subagent
the listing showed was one of them. An agent cannot even reliably identify its own row.

**A message to a finished agent is a resurrection.** This is the trap that caused three of
the four. Messaging a completed agent revives it *outside the loop's sequencing*, so it races
whatever round started after it. Sending one "stop editing this file" woke it up and it wrote
more — the write was caused by the instruction to stop.

> Findings go to the CURRENT owner. Never to the finished agent.

**`TaskStop` stops an agent; a message does not.** If the writer is workflow-internal and
unaddressable, stop the workflow. That is the only lever that reaches it.

**Anchored edits only when concurrency is possible.** An anchored replacement fails safely if
the anchor is gone. A whole-file `Write` from a stale in-memory copy silently drops the other
agent's work, and is the one unrecoverable operation.

**Do not launch a second workflow over files the first still owns.** Stop the first.

## When a collision happens

1. Confirm with `TaskStop`, not by reasoning. "No task found" is proof; a listing is not.
2. **Get the stopped agent's measurements as TEXT before it dies.** These handovers were the
   most valuable artifacts of the session: measured tone thresholds, geometry read at 1200
   dpi, traps found the expensive way, and lists of what failed and must not be retried.
3. Check whether the merged file builds. Interleaved edits are often coherent.
4. Keep both agents' work where it does not conflict. Reverting one wholesale discards real
   measurement.
5. Tell the survivor what the dead agent found, and that it is now sole owner.

## What to put in a build brief

The mandate, the measurements already taken, and what NOT to retry. An agent that has to
rediscover a tone threshold or a geometric impossibility spends its round on it. Items like
"this label is 45 pt against a 20 pt window" or "three bars inside a 0.63 mm pitch are the
smear we removed earlier" save a whole round each.
