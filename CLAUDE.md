## Development Workflow (Mandatory)
For any new feature, refactor, or architecture change, NEVER write implementation code immediately. You MUST automatically run the Spec Kit workflow in order:
1. Run `/speckit-specify` to draft `spec.md` from my request.
2. Run `/speckit-clarify` if any requirements are ambiguous, and pause for my answers.
3. Once clarified, run `/speckit-plan` to generate the technical architecture.
4. Run `/speckit-tasks` to break the plan into an ordered checklist.
5. Only after tasks are generated (and approved if requested), run `/speckit-implement`.
6. When a new feature is ready to be merged, do `/code-review` and `security-review` before suggesting to commite and merge.