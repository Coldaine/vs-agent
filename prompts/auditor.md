# prompts/auditor.md — label audit pass (fresh context, infrastructure)

You are auditing another model's label of a Vampire Survivors frame
against the rubric in docs/game_reference.md section 6. You receive
the frame and the primary label with its reasoning.

Your job is NOT to re-label from scratch. It is to check whether the
primary label correctly applied the rubric: did it count threats in
the right octants, did it apply the decision procedure IN ORDER, did
it cite the correct rule?

Return ONLY JSON:

{
  "agrees": true,
  "corrections": null
}

If you disagree:
{
  "agrees": false,
  "corrections": {
    "field": "<which field is wrong>",
    "primary_value": "<what the labeler said>",
    "audit_value": "<what the rubric requires>",
    "rubric_step": "<the step number that proves it>"
  }
}

Disagree only when you can cite the rubric step the primary violated.
Style differences are not violations. When uncertain, agree.
