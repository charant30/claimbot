# ClaimBot Incident Flow & Agent Management Plan

This document outlines the end-to-end flow for the guided incident experience, document intake, and agent handoff, along with the recommended implementation sequence.

## 1) Guided Intake (Customer Chat UI)

**Goal:** When a user selects an intent like **File a Claim**, the chatbot opens a guided form for the minimal, required fields.

### UI Flow
1. **Intent Selection**
   - User selects `file_claim`.
   - UI transitions to a structured form based on product line (auto/home/medical).
2. **Required Fields Form**
   - Auto: date, location, incident type, description, estimated damage, vehicle info.
   - Home: date, location, incident type, description, affected areas, estimated damage.
3. **Submit + Validate**
   - Client-side validation for empty fields.
   - Send structured payload in `metadata` to backend.

### Backend Expectations
1. Accept intent/product from metadata (skip re-classification).
2. Use required fields map to determine missing fields.
3. Validate dates/amounts server-side before continuing.

## 2) First-Step Verification

**Goal:** Ensure the initial claim details and policy coverage are consistent before requesting documents.

### Steps
1. Load policy by user/policy ID.
2. Normalize + validate user-provided data.
3. Compare incident type + coverage in policy.
4. If mismatch or missing info, ask follow-ups.

## 3) Document + Image Intake

**Goal:** Collect police report, incident images, or other documents.

### Steps
1. Request document upload in chat UI.
2. Store files in object storage with metadata (`claim_id`, `document_type`).
3. Send image to OCR/vision model for extraction.

### Model Support (Ollama)
1. Download and run an OCR-capable model (e.g., LLaVA or a specialized OCR pipeline).
2. Send image + prompt to extract structured fields.
3. Store extracted report in case packet.

## 4) Multi-Agent Decisioning

**Goal:** Use one agent to evaluate the user report and another agent to evaluate documents, then reconcile.

### Steps
1. **Agent A**: validate user-provided details (timeline, location, incident type).
2. **Agent B**: validate document OCR results (police report, images).
3. **Supervisor Agent**: reconcile differences and determine next action.

### Outputs
1. **Approve**: proceed to payout calculation.
2. **Request More Info**: ask for missing/contradictory details.
3. **Escalate**: send to human agent.

## 5) Policy-Based Payouts

**Goal:** Calculate deductible + payout from policy data, not constants.

### Steps
1. Pull policy coverage limits, deductibles, and exclusions.
2. Use deterministic calculation engine.
3. Return breakdown to the user.

## 6) Human Handoff (Celest)

**Goal:** Provide a reliable escalation path to an agent.

### Steps
1. Create a `case` with `claim_id` and full `case_packet`.
2. Update case status to `ESCALATED`.
3. Allow agents to lock, take over, request info, or resolve.

## 7) Admin-Configurable Flows

**Goal:** Allow admins to modify escalation thresholds, required fields, and routing rules.

### Settings to Expose
1. Intent list
2. Product-specific required fields
3. Escalation thresholds (confidence, amount)
4. Document requirements

## Implementation Sequence

1. **Backend**: Accept metadata-driven intent/product to skip re-classification.
2. **Backend**: Align required fields with payout needs.
3. **Backend**: Use admin-configured flow thresholds.
4. **Backend**: Add claim creation + handoff creation on escalation.
5. **Frontend**: Add guided form on intent selection.
6. **Frontend**: Document upload in chat with status + preview.
7. **AI**: Wire OCR/vision model into document analysis pipeline.
8. **Admin**: Make flows editable and persisted in `SystemSettings`.
