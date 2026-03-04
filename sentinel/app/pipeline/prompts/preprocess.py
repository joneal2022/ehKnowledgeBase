"""Transcript preprocessing prompt — local 7B, caption cleanup."""

PROMPT_TEMPLATE = """You are cleaning up an auto-generated YouTube transcript.

Auto-captions frequently have these issues:
- Missing punctuation and sentence boundaries
- Run-on sentences that span multiple thoughts
- Missing capitalization at sentence starts
- Filler words misheard or omitted mid-sentence

YOUR TASK:
- Add sentence boundaries (periods, question marks) where clearly missing
- Capitalize the first word of each sentence
- Do NOT remove or reword content — preserve every idea and phrase
- Do NOT summarize — return the full cleaned transcript
- Do NOT add your own commentary or interpretation

{few_shot_examples}

TRANSCRIPT TO CLEAN:
{transcript}

Return ONLY the cleaned transcript text, nothing else.
"""
