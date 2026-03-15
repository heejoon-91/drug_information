# OTC safety-check refactor

## Changed behavior
- Removed symptom-to-drug recommendation flow from the user experience.
- Symptom input now produces a follow-up step asking the user to enter a product name or active ingredient directly.
- Product/ingredient input is now the only path that performs contraindication, interaction, and caution checks.
- Product checks now include user-profile-aware flags using:
  - current medications
  - allergies / chronic diseases (displayed in the profile snapshot)
  - pregnancy / breastfeeding flag
- Ingredient-only fallback was added so generic ingredients like `ibuprofen` can still be checked even when a branded product row is not found.

## Files changed
- `otc_info/chat/views.py`
- `otc_info/graph_agent/state.py`
- `otc_info/graph_agent/builder_v2.py`
- `otc_info/graph_agent/nodes_v2.py`
- `otc_info/prompts/answer_prompts_v2.py`
- `otc_info/templates/index.html`
- `otc_info/templates/symptom_result.html`
- `otc_info/templates/symptom_products_page.html`
- `otc_info/templates/search_result.html`
- `otc_info/templates/general_result.html`
- `otc_info/templates/profile.html`

## Notes
- Existing routes were preserved where possible.
- `api/symptom-products/` is now usable as a direct safety-check API instead of symptom-based product recommendation logic.
