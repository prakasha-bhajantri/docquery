
import os
import re
from dotenv import load_dotenv
load_dotenv()

# HF Inference
from huggingface_hub import InferenceClient

HF_TOKEN = os.getenv("HF_TOKEN", None)
HF_MODEL = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")


def clean_reasoning(text: str) -> str:
    """Remove <think> ... </think> blocks if present."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

def generate_with_hf(
                system_prompt: str,
                prompt: str,
                max_new_tokens: int = 256,
                strip_reasoning: bool = True
            ) -> str:
    """
    Generate text using a HuggingFace Inference Client in chat mode.
    Returns only the assistant's content (string).
    """
    
    client = InferenceClient(api_key=HF_TOKEN)

    completion = client.chat.completions.create(
        model=HF_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_new_tokens
    )

    msg = completion.choices[0].message
    content = msg.content if hasattr(msg, "content") else str(msg)

    if strip_reasoning:
        content = clean_reasoning(content)

    return content

