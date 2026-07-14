from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")

resp = client.chat.completions.create(
    model="TinyLlama-1.1B-Chat-v1.0",
    messages=[{"role": "user", "content": "Say hello in one word."}],
    max_tokens=20,
)

print("Response:", resp.choices[0].message.content)
print("Model:", resp.model)
print("Usage:", resp.usage)