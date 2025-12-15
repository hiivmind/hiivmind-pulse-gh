  - Routing guide: Decisions + search keywords
  - Corpus index: Locations + matching keywords
  - Source docs: Actual syntax (always current from upstream)


  So the model is:

  api-routing.md says:
  - "Milestones create → REST"
  - Search keywords: "milestones", "create", "REST", "POST"

  Corpus index says (after enhance with keywords):
  - Entry for milestone creation
  - Tagged with keywords: "milestones", "create", "REST", "CRUD"
  - Points to the source doc (which has the actual syntax)

  LLM flow:
  1. Read routing → "REST for create"
  2. Search corpus using keywords → finds entry
  3. Read the actual source doc → gets current syntax

  This way:
  - Routing guide: pure decisions + search keywords
  - Corpus index: locations + matching keywords
  - Source docs: actual syntax (always current)

  Let me update api-routing.md and draft enhance instructions.
