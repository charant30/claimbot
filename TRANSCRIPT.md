# ClaimBot Demo Video Script

Script for a demo video: configuration → claim submission → specialist review. Adjust ports (e.g. 3000, 3001, 3002) to match your setup.

**Roles:** Narrator (you); Sarah (policyholder); Mike (claims specialist).

---

## 0. Introduction [0:00 - 0:45]

**[Action: Open the Landing Page or Title Slide]**

**Narrator:** "Welcome to ClaimBot, an intelligent, multi-modal insurance claims automation platform. Today, we're going to show you how ClaimBot transforms the First Notice of Loss (FNOL) experience from a stressful, manual process into a seamless, AI-driven journey."

**Narrator:** "We will cover three key perspectives:
1.  **The Administrator:** Configuring the AI behavior and rules.
2.  **The Policyholder:** Filing a claim in minutes using natural language.
3.  **The Adjuster:** Reviewing pre-processed data for rapid decision-making."

---

## 1. System Configuration (Admin Portal) [0:45 - 2:30]

**[Action: Navigate to `localhost:3001` (Admin Dashboard)]**

**Narrator:** "We start in the **Admin Configuration Dashboard**. This is where we control the brain of ClaimBot."

**[Action: Click on 'LLM Settings' in the sidebar]**

**Narrator:** "ClaimBot is model-agnostic. In the **LLM Settings** tab, we can choose our intelligence provider.
*   Currently, we are using **OpenAI** with **GPT-4o-mini** for both text and vision tasks.
*   We can easily switch this to AWS Bedrock (Claude 3) or Ollama for local processing if data privacy requirements change."

**[Action: Demonstrate changing a setting, e.g., 'Vision Model' or toggling a feature, then click 'Save']**

**Narrator:** "Changes here take effect immediately across the platform."

**[Action: Click on 'Flow Rules' or 'Triage Configuration']**

**Narrator:** "Next, let's look at **Flow Rules**. This is the decision engine.
*   We've configured a **Confidence Threshold** of **0.7**.
*   We have **Auto-Approval Limits** set to **$5,000**.
*   We also have specific scoring rules: A 'hit-and-run' adds 50 points to the risk score, while 'glass-only' might reduce it."

**Narrator:** "With our system configured, let's see it in action."

---

## 2. The Customer Experience (FNOL Chat) [2:30 - 5:30]

**[Action: Switch to `localhost:3000` (Customer Portal). Recommended: Use browser DevTools to toggle 'Mobile View' (iPhone SE/12) to demonstrate responsiveness.]**

**Narrator:** "Meet Sarah. She was just involved in a minor two-vehicle collision. She’s safe, but stressed. She opens the insurance app on her phone."

**[Action: Click 'File a New Claim']**

**Narrator (Voiceover as Sarah):** "I need to file this quickly."

**[Action: The Chat Interface loads. Bot says: "Hello! I'm ClaimBot... are you safe?"]**

**Narrator:** "The agent's first priority is safety. This is a hard-coded strict state."

**[Voiceover / Action: Type/Select "Yes, everyone is safe." ]**

**[Action: Bot asks for incident details.]**

**Narrator:** "Now, instead of filling out rigid forms, Sarah can just talk."

**[Voiceover / Action: Type "I was driving on Main St and stopped at a red light. A car behind me didn't stop in time and rear-ended my Honda." ]**

**Narrator:** "Using **LangGraph** and an **Intent Classification** service, the bot understands:
1.  **Scenario:** Multi-vehicle collision.
2.  **Role:** Sarah was rear-ended (not at fault).
3.  **Location:** Main St."

**[Action: Bot asks for the other driver's info.]**

**Narrator:** "It dynamically loads the 'Two-Vehicle Collision' playbook, asking specific questions relevant to this scenario."

**[Voiceover / Action: Type "His name is John Doe, license ABC-123. He has State Farm insurance." ]**

**[Action: Bot asks for photos.]**

**Narrator:** "Here’s where the **Vision AI** shines. Sarah doesn't need to describe the damage manually."

**[Action: Upload 1-2 images of car damage (use sample images of a dented bumper).]**

**Narrator:** "The system uses **GPT-4o (Vision)** to analyze these images in real-time. It detects:
*   Damage location: Rear bumper.
*   Severity: Moderate.
*   Drivability: Likely drivable."

**[Action: Bot confirms receipt and generates a summary.]**

**Narrator:** "Within minutes, the claim is drafted. The system calculates a **Triage Score**.
*   Because it's a simple rear-end collision with no injuries, the score is **low risk**."

**[Action: Click 'Submit Claim'. Success screen appears with Claim Number.]**

---

## 3. The Specialist View (Celest Portal) [5:30 - 7:00]

**[Action: Switch to `localhost:3002` (Celest Portal)]**

**Narrator:** "Now we switch to Mike, the Claims Specialist. He logs into the **Celest Portal**."

**[Action: The Dashboard shows a queue of claims. Click on the new claim Sarah just filed.]**

**Narrator:** "Mike sees Sarah's claim in his queue. But he doesn't start from scratch."

**[Action: Scroll through the 'Claim Detail' view]**

**Narrator:** "Look at what he has:
1.  **Conversation Transcript:** Full context of what provided.
2.  **Extracted Data:** The AI has structured the unstructured chat into fields (Date, Time, Location, Other Party).
3.  **AI Analysis:** The Vision analysis of the bumper is already attached."

**[Action: Point mouse to the 'Triage Score' or 'Risk Assessment' widget]**

**Narrator:** "The AI suggests 'Approve for Estimate' because the data confirms the story."

**[Action: Click 'Approve Claim' / 'Send to repair shop']**

**Narrator:** "With one click, Mike approves the next step. Sarah gets a notification immediately."

---

## 4. Conclusion [7:00 - 7:30]

**[Action: Return to the Landing Page or Architecture Slide]**

**Narrator:** "And that is ClaimBot.
*   **For the User:** A fast, empathetic, 24/7 experience.
*   **For the Business:** Reduced operational costs and standardized data collection.
*   **Under the Hood:** A robust architecture powered by FastAPI, LangGraph, and Generative AI."

**Narrator:** "Thank you for watching."
